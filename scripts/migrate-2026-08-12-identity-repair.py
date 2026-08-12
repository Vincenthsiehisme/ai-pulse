#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性遷移：把身分被搞混的那些證據放回它們該在的地方。

規格與完整帳目：references/incidents/2026-08-12-identity-repair.md。
先讀那份再讀這支（紅線 9）。

## 它在修什麼

`/news/claude-opus-4-5` 的標題是從 URL 推導的（sitemap 沒有標題欄位），
而 URL 的 `-` 同時是斷詞符與小數點，於是還原成「Claude Opus 4 5」。
小數點掉了之後：

  event_fingerprint()  只吃到 opus:4     → 4.5 / 4.6 / 4.7 / 4.8 塌成同一個鍵
  title_tokens()       丟掉單字元         → 「Claude Opus 4 5」與「Claude Opus 5」
                                            的相似度變成 1.00

`fix/identity-beats-similarity` 修好了規則，但**歷史資料不會自己變好**：
語料裡存的還是舊標題，Event 裡掛的還是舊證據。這支補那一段。

## 四件事，順序不能換

  1. 語料層：sitemap 來源的 title 依 URL 重新推導（否則第 4 步會再錯一次）
  2. Event 標題：標題本身掉了版號的那幾則，連 fingerprint 一起改
  3. 錯掛的證據：搬回同指紋的既有 Event；沒有既有 Event 的，補寫一則
  4. 受影響的 Event 重算分數

## 補寫的 Event 會自己承認它是補寫的

  recovered_by: identity-repair-2026-08-12

**不是 `coverage: backfilled`。** 那一格已經有意思了——它說的是「事情發生時
我們的來源還沒開始觀測」，是 lib/coverage.py 每班重算的推導欄位。
一個欄位兩個意思，正是這個 repo 一直在抓的病。

補寫的 Event 走 `status: review`，不給 published：**機器補的事件不該自己升到
已發布**，跟「升到 active 只有人能做」是同一條線。

用法：
  VAULT_DIR=/path/to/AI-Pulse python3 scripts/migrate-2026-08-12-identity-repair.py [--apply]
預設 dry-run。可重跑（idempotent）：跑第二次應該什麼都不做。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from lib import clock, cluster  # noqa: E402
from lib import coverage as coverage_lib  # noqa: E402
from lib import sources as srcmod  # noqa: E402
from lib.atomicwrite import atomic_write_text  # noqa: E402

import yaml  # noqa: E402

_ps = importlib.util.spec_from_file_location(
    "pulse_probe", os.path.join(_HERE, "pulse-probe.py"))
_pp = importlib.util.module_from_spec(_ps)
_ps.loader.exec_module(_pp)
_cs = importlib.util.spec_from_file_location(
    "pulse_cluster", os.path.join(_HERE, "pulse-cluster.py"))
_cm = importlib.util.module_from_spec(_cs)
_cs.loader.exec_module(_cm)

TAG = "identity-repair-2026-08-12"


def old_slug_to_title(url):
    """修正**之前**的還原法。只用來認出「這個標題是那樣長出來的」。

    不能拿新的還原法去比對——那樣會把人手改過的標題也一起蓋掉。
    只有「現值等於舊還原法的產出」才證明這一格是機器推導的、沒有人碰過。
    """
    seg = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    seg = re.sub(r"\.(html?|php|aspx?)$", "", seg)
    words = [w for w in re.split(r"[-_]+", seg) if w]
    return " ".join(w if (w.isupper() or any(c.isdigit() for c in w))
                    else w.capitalize() for w in words)


def refresh_relevance(title, evidence):
    """`relevance` 是**相對於這則 Event 標題**算出來的，換了標題就不再有效。

    pulse-cluster 裡唯一寫這一格的地方是
    `rel = int(round(title_similarity(訊號標題, ev.title) * 100))`，
    也就是說這一格的不變式是「等於證據標題與事件標題的相似度」。

    搬家與改標題都會打破它：把一筆 relevance=33 的證據從
    「Claude Sonnet 5」搬到「Claude Opus 5」之後，那個 33 是對**舊**標題算的，
    而它對新標題其實是 100。不重算的話，那個數字會留在 frontmatter 裡當一個
    看起來有意義、其實在講另一件事的值——比空著更糟。
    """
    for e in evidence:
        e["relevance"] = int(round(
            cluster.title_similarity(e.get("title") or "", title) * 100))


def parse_fm(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    return yaml.safe_load(text[3:end]) or {}, text[end + 4:]


def retitle(url, current, adapter):
    """這一格該不該改、改成什麼。→ 新標題或 None。"""
    if adapter != "sitemap" or not url:
        return None
    if old_slug_to_title(url) != (current or ""):
        return None                      # 人碰過，或本來就不是推導來的
    new = _pp._slug_to_title(url)
    return new if new != current else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    cfg = vault / "_config"

    raw = yaml.safe_load((cfg / "sources.yaml").read_text("utf-8")) or {}
    adapter = {str(s.get("id")): s.get("adapter") for s in srcmod.iter_sources(raw)}
    sources = _cm.load_sources(cfg)
    entities = _cm.load_entities(cfg)
    tc_cfg = _cm.load_translation_chain_cfg(cfg)
    vr_cfg = _cm.load_verbatim_repost_cfg(cfg)
    ent_table = _cm.load_entity_table(cfg)
    first_fetch = _cm.load_first_fetch(vault / "_probe")
    # rescore 的 ref_now 用**真正的現在**，不用 happened_at。
    #
    # 拿 happened_at 當 now 會讓 freshness 變成 100、value 跟著虛漲——
    # 而那個漲跟這次修復一點關係都沒有。用真正的現在，寫出來的年齡相關欄位
    # 就跟「今晚那班如果碰到這則會寫的值」一致，不是這支腳本自己發明的。
    #
    # 代價是 diff 裡會同時出現兩種變動：**因為修復而變的**（confidence /
    # primary_evidence / independent_sources）與**因為時間而變的**
    # （freshness / heat / value）。輸出把兩者分開印，不要混在一起看。
    now = datetime.now(timezone.utc)

    report = {"tag": TAG, "corpus": [], "titles": [], "moved": [],
              "created": [], "rescored": []}
    writes = {}          # path -> text

    # ── 1. 語料層 ─────────────────────────────────────────────────────────
    # 先做這一步：第 3 步要靠 URL 去語料查 first_observed_at，而補寫的 Event
    # 的標題也從這裡來。語料還是舊的話，補出來的 Event 標題會是舊形狀。
    observed = {}        # url -> first_observed_at
    hits = {}            # url -> entity_hits（補寫 Event 的 company 要用）
    for p in sorted(list((vault / "_corpus").glob("20*/*.jsonl"))
                    + list((vault / "_probe").glob("20*/signals-*.jsonl"))):
        lines = p.read_text("utf-8").splitlines()
        out, changed = [], 0
        for line in lines:
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            u = rec.get("url") or ""
            if u and rec.get("first_observed_at"):
                observed.setdefault(u, rec["first_observed_at"])
            if u and rec.get("entity_hits"):
                # **聯集，不是取第一筆**。同一個 URL 在語料裡出現過幾十次
                # （每天重抓），命中的實體會因為字典當天的狀態而不同。
                # 取第一筆等於押寶在某一天的字典版本上。
                hits.setdefault(u, set()).update(rec["entity_hits"])
            new = retitle(u, rec.get("title"), adapter.get(str(rec.get("source_id"))))
            if new:
                report["corpus"].append({"file": str(p.relative_to(vault)),
                                         "url": u, "from": rec.get("title"), "to": new})
                rec["title"] = new
                changed += 1
                out.append(json.dumps(rec, ensure_ascii=False))
            else:
                out.append(line)
        if changed:
            writes[p] = "\n".join(out) + "\n"

    # ── 讀 Events ─────────────────────────────────────────────────────────
    events = {}
    for p in sorted((vault / "Events").glob("*.md")):
        fm, body = parse_fm(p.read_text("utf-8"))
        if fm.get("id"):
            events[fm["id"]] = [p, fm, body]

    # ── 2. Event 標題本身掉了版號 ─────────────────────────────────────────
    # touched 要在這裡就存在：標題改了、證據標題改了，那個檔就得重寫。
    # 第一版把 touched 放在第 3 步才建立，於是「只改了標題、沒有錯掛證據」的
    # 那兩則**改在記憶體裡、沒有寫出去**——跑第二次還會再報一次同樣的改動。
    # 抓到它的是冪等性檢查（跑兩次，第二次應該什麼都不做），不是任何一條斷言。
    touched = set()
    for eid, (p, fm, _b) in events.items():
        for e in (fm.get("evidence") or []):
            new = retitle(e.get("url") or "", fm.get("title"),
                          adapter.get(str(e.get("source_id"))))
            if new:
                report["titles"].append({"id": eid, "from": fm["title"], "to": new,
                                         "fingerprint_from": fm.get("fingerprint"),
                                         "fingerprint_to": cluster.event_fingerprint(new)})
                fm["title"] = new
                fm["fingerprint"] = cluster.event_fingerprint(new)
                touched.add(eid)
                break

    # ── 證據標題也重新推導（判斷用欄位，錯的話下游全錯）────────────────────
    for eid, (p, fm, _b) in events.items():
        for e in (fm.get("evidence") or []):
            new = retitle(e.get("url") or "", e.get("title"),
                          adapter.get(str(e.get("source_id"))))
            if new:
                e["title"] = new
                touched.add(eid)

    # ── 3. 身分衝突的證據：搬家或補寫 ─────────────────────────────────────
    by_fp = {}
    for eid, (p, fm, _b) in events.items():
        f = cluster.event_fingerprint(fm.get("title") or "")
        if f:
            by_fp.setdefault(f, eid)

    homeless = {}        # fingerprint -> [evidence dict]
    for eid, (p, fm, _b) in sorted(events.items()):
        efp = cluster.event_fingerprint(fm.get("title") or "")
        if not efp:
            continue
        keep, move = [], []
        for e in (fm.get("evidence") or []):
            sfp = cluster.event_fingerprint(e.get("title") or "")
            (move if (sfp and sfp != efp) else keep).append((sfp, e))
        if not move:
            continue
        fm["evidence"] = [e for _f, e in keep]
        touched.add(eid)
        for sfp, e in move:
            dest = by_fp.get(sfp)
            report["moved"].append({"from": eid, "to": dest, "fingerprint": sfp,
                                    "url": e.get("url"), "title": e.get("title")})
            if dest and dest != eid:
                d_fm = events[dest][1]
                if not any(x.get("url") == e.get("url")
                           for x in (d_fm.get("evidence") or [])):
                    d_fm.setdefault("evidence", []).append(dict(e))
                    touched.add(dest)
            elif not dest:
                homeless.setdefault(sfp, []).append(dict(e))

    # ── 補寫沒有家的那幾則 ────────────────────────────────────────────────
    for fp, rows in sorted(homeless.items()):
        rows.sort(key=lambda e: str(e.get("published") or ""))
        head = rows[0]
        title = head.get("title") or fp
        facet = cluster.event_facet(title)
        # id 的算法跟 pulse-cluster 一致（同鍵同日 → 同 id），不另立一套。
        h = hashlib.sha1(f"{fp}|{facet}".encode("utf-8")).hexdigest()[:6]
        hd = _cm.parse_dt(head.get("published") or "")
        hdate = clock.utc_date(hd).isoformat() if hd else str(head.get("published"))[:10]
        eid = f"evt-{hdate}-{h}"
        if eid in events:
            for e in rows:                       # 重跑：已經補過了，只補證據
                d_fm = events[eid][1]
                if not any(x.get("url") == e.get("url")
                           for x in (d_fm.get("evidence") or [])):
                    d_fm.setdefault("evidence", []).append(dict(e))
                    touched.add(eid)
            continue
        ev = _cm.Event(eid, f"{_cm.slugify(title)}-{h[:4]}", title,
                       head.get("published") or "", fp, facet)
        # 我們**看過**這幾則，只是歸錯檔。所以 ingested_at 用語料裡真的第一次
        # 看到的時刻，不是今天——寫今天等於謊報這是新發現的。
        ev.ingested_at = observed.get(head.get("url")) or head.get("published")
        # company 走跟 pulse-cluster 同一支 infer_company。查不到就是 "industry"
        # ——那會觸發 generic_entity blocker，而這些 Event 本來就是 status: review，
        # 由人補。**這裡不猜**：拿來源的 owner 去填看起來會對，但那是「誰發布的」
        # 不是「這件事關於誰」，兩者在媒體來源上會分岔。
        ev.company = _cm.infer_company(sorted(hits.get(head.get("url")) or []),
                                       entities)
        ev.keywords = cluster.keyword_tokens(title, 8)
        ev.recovered_by = TAG
        for e in rows:
            # add_evidence 依 (source_id, url) 去重：同一個 URL 從兩則事件被搬
            # 過來時只留一筆。所以帳目要記 len(ev.evidence) 而不是 len(rows)
            # ——後者會報出一個比實際多的證據數，而報告多報比少報更難發現。
            ev.add_evidence(e.get("source_id"), e.get("url"), e.get("title"),
                            e.get("relevance"), e.get("published"))
        refresh_relevance(title, ev.evidence)
        _cm.rescore(ev, sources, now, tc_cfg, ent_table, first_fetch, vr_cfg)
        _cm.apply_coverage(ev, first_fetch)
        path = vault / "Events" / f"{eid}.md"
        writes[path] = _cm.event_markdown(ev)
        report["created"].append({"id": eid, "title": title, "fingerprint": fp,
                                  "evidence": len(ev.evidence),
                                  "confidence": ev.scores["confidence"],
                                  "recovered_by": TAG})

    # ── 4. 受影響的 Event 重算 ────────────────────────────────────────────
    for eid in sorted(touched):
        p, fm, body = events[eid]
        ev = _cm.Event(eid, fm.get("slug") or eid, fm.get("title") or eid,
                       fm.get("happened_at") or "", fm.get("fingerprint"),
                       fm.get("facet"))
        ev.evidence.extend(_cm.evidence_from_frontmatter(fm.get("evidence") or []))
        refresh_relevance(fm.get("title") or "", ev.evidence)
        _cm.rescore(ev, sources, now, tc_cfg, ent_table, first_fetch, vr_cfg)
        s = ev.scores
        before = {k: fm.get(k) for k in ("primary_evidence", "independent_sources",
                                         "suspected_reposts", "confidence",
                                         "heat", "value")}
        fm["evidence"] = _cm.evidence_frontmatter(ev.evidence)
        for k in ("tier_evidence", "independent_sources", "suspected_reposts",
                  "primary_evidence", "confidence", "heat", "impact", "value"):
            fm[k] = s[k]
        fm["score_factors"] = s["factors"]
        report["rescored"].append({"id": eid, "title": fm.get("title"),
                                   "before": before,
                                   "after": {k: fm.get(k) for k in before}})
        front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                               default_flow_style=False).rstrip()
        b = body if body.startswith("\n") else "\n" + body
        writes[p] = f"---\n{front}\n---{b}"

    # ── 輸出 ──────────────────────────────────────────────────────────────
    print(f"語料標題重新推導：{len(report['corpus'])} 筆"
          f"（{len({r['file'] for r in report['corpus']})} 個檔）")
    for r in report["titles"]:
        print(f"Event 標題：{r['id']}  「{r['from']}」→「{r['to']}」"
              f"   指紋 {r['fingerprint_from']} → {r['fingerprint_to']}")
    print(f"錯掛的證據：{len(report['moved'])} 筆")
    for r in report["moved"]:
        print(f"   {r['fingerprint']:<30} {r['from']} → {r['to'] or '（補寫）'}")
    print(f"補寫的 Event：{len(report['created'])} 則")
    for r in report["created"]:
        print(f"   {r['id']}  「{r['title']}」  證據 {r['evidence']} 筆  "
              f"confidence={r['confidence']}  status=review  recovered_by={TAG}")
    print(f"重算的 Event：{len(report['rescored'])} 則")
    for r in report["rescored"]:
        print(f"   {r['id']}「{r['title']}」")
        for k in ("primary_evidence", "independent_sources", "suspected_reposts",
                  "confidence"):
            b, a = r["before"][k], r["after"][k]
            print(f"      修復    {k:<20} {str(b):>4} → {str(a):>4}"
                  f"{'   ←' if b != a else ''}")
        for k in ("heat", "value"):
            b, a = r["before"][k], r["after"][k]
            print(f"      時間    {k:<20} {str(b):>4} → {str(a):>4}"
                  f"{'   （年齡重算，與本次修復無關）' if b != a else ''}")
    print(f"要寫的檔：{len(writes)}")

    if not args.apply:
        print("\n（dry-run。加 --apply 才會寫。）")
        return 0
    # 沒事可做就**連帳目都不寫**。
    #
    # 這一格是 2026-08-12 真的踩到的：資料層是冪等的（第二次跑什麼都不改），
    # 但帳目原本寫在 --apply 的無條件路徑上，於是第二次跑——那一次它正確地
    # 什麼都沒做——把上一次的紀錄整份覆蓋成全 0。
    #
    # 後果是一個寫著「這次遷移什麼都沒做」的檔案，躺在一個改了 53 個檔的
    # commit 旁邊。**那比沒有帳目更糟**：沒有帳目的時候人會去翻 diff，
    # 有一份說謊的帳目時人會相信它。
    #
    # 冪等要冪等到帳目那一層才算數。
    if not writes:
        print("\n沒有東西要寫。帳目不動——一次沒做事的重跑，不該把上一次的紀錄洗掉。")
        return 0
    for path, text in sorted(writes.items()):
        atomic_write_text(path, text)
    atomic_write_text(vault / "_probe" / f"{TAG}.json",
                      json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\n已寫 {len(writes)} 個檔，帳目寫進 _probe/{TAG}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
