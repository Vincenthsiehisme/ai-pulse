#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-cluster.py — Sprint 3b：signals → Event（純規則，零 LLM）。

讀 _probe/<day>/signals-scored.jsonl（3a 產）+ _config/{sources,entities,gate}.yaml，
依「同 fingerprint+facet+時間窗 / 或標題相似度 ≥0.46」把 signals 聚成 Event，
綁定證據、算 confidence/heat/independent_sources/primary_evidence，
寫 Events/<id>.md（六層標題 + 待編輯佔位；prose 留給 3c enrich 填）。
跨日：會讀既有 Events/*.md，新 signal 可 attach 到昨天的 Event 並重評分。

紅線：獨立數 = 「同人或同媒體集團就合併」的連通分量（框架規則第 5 條），
      比 agent-pulse 原碼嚴。實作見 lib/cluster.independent_voices()。
用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-cluster.py [--day YYYY-MM-DD] [--dry-run]
依賴：PyYAML。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cluster, entities as entities_lib, scoring  # noqa: E402
from lib.sources import SECTIONS  # noqa: E402  分節清單單一真相源
from lib.notes import PLACEHOLDER  # noqa: E402  單一來源，見 lib/notes.py
from lib.quality import authority_score_from_tier, parse_dt  # noqa: E402

import yaml  # noqa: E402


def load_sources(cfg):
    raw = yaml.safe_load((cfg / "sources.yaml").read_text("utf-8"))
    out = {}
    for key in SECTIONS:
        for s in (raw.get(key) or []):
            if isinstance(s, dict) and s.get("id"):
                out[s["id"]] = s
    return out


def load_entities(cfg):
    """id → (canonical, term_type)。用於 Event 的 company 初判。"""
    p = cfg / "entities.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    out = {}
    for key in ("companies", "product_lines", "products", "technologies", "policy"):
        for e in (raw.get(key) or []):
            if isinstance(e, dict) and e.get("id"):
                out[e["id"]] = (e.get("canonical") or e["id"], e.get("term_type"), e.get("parent"))
    return out


def load_translation_chain_cfg(cfg):
    """gate.yaml 的 evidence.translation_chain。缺檔／缺區塊 → 回空 dict。

    回空 dict 等於 `enabled` 不成立，也就是這條規則不判——跟設定檔明寫
    `enabled: false` 走同一條路。**設定檔讀不到不可以退回「照判」**：
    一條在設定檔壞掉時反而更積極扣分的規則，會在最沒人注意的那天改變結果。
    """
    p = cfg / "gate.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    return ((raw.get("evidence") or {}).get("translation_chain") or {})


def load_entity_table(cfg):
    """命名實體字典 → 比對表（lib/entities.build_matcher）。缺檔回空 list。"""
    p = cfg / "entities.yaml"
    if not p.exists():
        return []
    return entities_lib.build_matcher(yaml.safe_load(p.read_text("utf-8")) or {})


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(title):
    s = _SLUG_STRIP.sub("-", (title or "").lower()).strip("-")
    return s[:60] or "event"


def infer_company(entity_hits, entities):
    # 1) 直接命中 company 型別
    for hid in entity_hits or []:
        canon, ttype, _ = entities.get(hid, (None, None, None))
        if ttype == "company":
            return canon
    # 2) 命中 product_line/product → 往上解析到 parent 公司（例：gemini → Google DeepMind）
    for hid in entity_hits or []:
        canon, ttype, parent = entities.get(hid, (None, None, None))
        if parent:
            pcanon, pttype, _ = entities.get(parent, (None, None, None))
            if pttype == "company":
                return pcanon
    return "industry"  # 泛稱 → 會觸發 generic_entity blocker，待 enrich 修正


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[3:end]) or {}
    body = text[end + 4:]
    return fm, body


class Event:
    def __init__(self, eid, slug, title, happened_at, fingerprint=None, facet=None):
        self.id = eid
        self.slug = slug
        self.title = title
        self.happened_at = happened_at
        self.fingerprint = fingerprint
        self.facet = facet
        self.evidence = []  # list of {source_id, url, title, relevance}
        self.company = "industry"
        self.keywords = []
        self.dirty = True  # 需要寫檔
        self.scores = None
        self.path = None
        self.enriched = False   # 已 enrich（3c）→ 重寫時只更新 frontmatter 分數，不動 prose body
        self.orig_body = None   # reload 時保存的原 body（enriched 時用來保留潤好的 prose）
        self.fm = None          # reload 時保存的完整 frontmatter
        # 這則 Event **進到我們庫裡**的時刻，跟 happened_at（外面世界發生的時刻）
        # 是兩件事。寫一次就不再動；規格見 references/event-timestamps.md。
        self.ingested_at = None
        # 標題的中文譯文與它綁的原文雜湊，由潤稿端寫（pulse-title-apply.py）。
        # 跟 ingested_at 同樣是 sticky 欄位：event_markdown() 會整份重寫
        # frontmatter，沒被明確帶過去的欄位會被抹掉——那正是
        # fix/backfill-flag-erased-by-second-run 修的坑，這裡是第三個踩到它的欄位。
        self.title_zh = None
        self.title_zh_src = None

    def add_evidence(self, source_id, url, title, relevance, published=None):
        """新增一條證據。`title` 與 `published` 是**判斷用的欄位，不是展示用的**。

        規格見 references/evidence-tiers.md〈證據記錄要留下什麼〉。簡短版：
        跨語言轉載鏈判定要問「這兩條的標題實體重不重疊、發布時間差幾小時」，
        兩個問題都只有在證據記錄自己帶著 title 與 published 時才回答得出來。
        在此之前這兩個值只活在建立那一班的記憶體裡，重新讀檔就沒了。
        """
        if any(e["source_id"] == source_id and e["url"] == url for e in self.evidence):
            return
        self.evidence.append({"source_id": source_id, "url": url, "title": title,
                              "relevance": relevance, "published": published})
        self.dirty = True


_EVIDENCE_FIELDS = ("source_id", "url", "title", "relevance", "published",
                    "suspected_repost")


def evidence_frontmatter(evidence):
    """證據記錄 → frontmatter 的 list。欄位白名單，順序固定。

    規格見 references/evidence-tiers.md。白名單是刻意的：證據記錄不是語料的
    副本，只留下**判斷會用到的**那幾個欄位（紅線 6，原始內容只進 _evidence_raw/）。
    順序固定是為了 diff——欄位順序每跑一次換一次的話，`git diff` 上每則 Event
    都會看起來像被改過。
    """
    return [{k: e.get(k) for k in _EVIDENCE_FIELDS} for e in evidence]


def evidence_from_frontmatter(items):
    """frontmatter 的 `evidence[]` → 記憶體裡的證據記錄。跨日 attach 會走這條路。

    `title` 缺席時填 `None`，**不填 url**。舊版填的是 `e.get("url")`，於是重新
    讀檔之後每一條證據的「標題」都是它自己的網址：body 的證據清單會把同一個
    網址印兩次，而任何拿 `title` 做判斷的規則（轉載鏈的實體重疊）會拿到一串
    網址去比對，比出來的相似度是假的、而且看起來很正常。

    缺就是缺——量不到不可以寫成一個看起來像值的東西（紅線 8）。
    規格見 references/evidence-tiers.md〈證據記錄要留下什麼〉。
    """
    out = []
    for e in (items or []):
        out.append({"source_id": e.get("source_id"), "url": e.get("url"),
                    "title": e.get("title"), "relevance": e.get("relevance", 0),
                    "published": e.get("published")})
    return out


def evidence_line(e):
    """body 的〈證據〉那一行。標題缺席時只印網址，不把網址印成標題。

    舊版是 `— {title}（{url}）`，而重新讀檔之後 title 就是 url，於是同一個網址
    被印兩次、中間夾一個破折號，看起來像「這篇文章的標題就叫 https://…」。
    """
    title = (e.get("title") or "").strip()
    head = f"- [[Sources/{e['source_id']}|{e['source_id']}]] — "
    if not title or title == (e.get("url") or "").strip():
        return f"{head}（標題未留存）{e.get('url') or ''}"
    return f"{head}{title}（{e.get('url') or ''}）"


def mark_reposts(ev, sources, tc_cfg, ent_table):
    """在證據上標 `suspected_repost`。回傳被標記的 index 集合。

    規格見 references/evidence-tiers.md〈evidence.translation_chain〉。
    每一輪都重算並重寫這個欄位——它是判斷的產物，不是人填的事實，
    留著上一輪的結論會在字典或門檻改動之後變成一句沒人維護的舊話。
    """
    rows = []
    for e in ev.evidence:
        src = sources.get(e["source_id"], {}) or {}
        title = e.get("title") or ""
        rows.append({
            "lang": src.get("language"),
            "tier": src.get("tier"),
            "published": parse_dt(e.get("published")),
            # 實體集合走命名實體字典，不走 token 交集——中英文標題的 token
            # 交集趨近於零，而字典的 aliases 兩種語言都收。
            "entities": entities_lib.entity_ids(title, ent_table) if (title and ent_table) else frozenset(),
            "fingerprint": cluster.event_fingerprint(title) if title else None,
        })
    flagged = cluster.suspected_reposts(rows, tc_cfg)
    for idx, e in enumerate(ev.evidence):
        e["suspected_repost"] = idx in flagged
    return flagged


def rescore(ev, sources, ref_now, tc_cfg=None, ent_table=None):
    reposts = mark_reposts(ev, sources, tc_cfg, ent_table)
    # gate.yaml 的 excluded_from 真的被讀：把它寫成一個「改了也沒效果」的清單，
    # 就是這個 repo 一直在抓的假旋鈕。清單裡的 heat 今天是**由 independent_sources
    # 承擔的**（heat 的證據面輸入只有獨立來源數，metrics 還是 []），社群線接上那天
    # 要回來把它單獨接一次——那件事寫在 references/evidence-tiers.md。
    excluded = set((tc_cfg or {}).get("excluded_from") or [])
    authority_scores, tiers, voices, primary = [], [], [], 0
    for idx, e in enumerate(ev.evidence):
        src = sources.get(e["source_id"], {})
        tier = src.get("tier")
        try:
            tier = int(tier)
        except (TypeError, ValueError):
            tier = 3
        authority_scores.append(authority_score_from_tier(tier))
        tiers.append(tier)
        # 轉載鏈：被判成別人的翻譯的那一條，不進獨立性計算
        # （gate.yaml 的 excluded_from 第一項）。authority 與 primary 照算——
        # 那兩項不在排除清單裡，翻譯的權威性由它自己的 tier 表達。
        if not (idx in reposts and "independent_sources" in excluded):
            voices.append((e["source_id"], src))
        role = src.get("role")
        scat = src.get("source_category")
        if tier == 1 and role != "aggregator" and scat != "aggregator":
            primary += 1
    # 紅線第 5 條：source + author + media group。2026-07-26 之前這裡只算了
    # media group 那一半，同一個人在兩個站台發表會被當成兩個獨立來源。
    # 判定搬到 lib/cluster.independent_voices()（連通分量），理由寫在該函式上方。
    independent = cluster.independent_voices(voices)
    happened = parse_dt(ev.happened_at)
    age_hours = max(0.0, (ref_now - happened).total_seconds() / 3600.0) if (happened and ref_now) else 0.0
    ev.scores = scoring.score_event(authority_scores, primary, independent, metrics=[], age_hours=age_hours)
    ev.scores["tier_evidence"] = min(tiers) if tiers else None
    ev.scores["independent_sources"] = independent
    ev.scores["primary_evidence"] = primary
    # 印出來給人看：0 也要印。一個只在有東西時才出現的數字，看不見的時候
    # 有兩種意思（沒有轉載／這條規則沒跑）——那是這個 repo 一直在抓的形態。
    ev.scores["suspected_reposts"] = len(reposts)


def event_markdown(ev):
    s = ev.scores
    hd = parse_dt(ev.happened_at)
    date_str = hd.date().isoformat() if hd else (ev.happened_at[:10] if ev.happened_at else None)
    fm = {
        "id": ev.id,
        "slug": ev.slug,
        "title": ev.title,
        # 中文標題跟原文並排，原文永遠留著（跟榜單描述同一條規矩：譯文是二手的，
        # 讀者要能看到一手的那句）。沒有譯文時兩格都是 None，不是空字串——
        # 空字串會讓 prep 分不出「沒翻過」跟「翻出來是空的」。
        "title_zh": ev.title_zh,
        "title_zh_src": ev.title_zh_src,
        "date": date_str,
        "happened_at": hd.isoformat() if hd else ev.happened_at,
        # 監控佇列年紀只能看這個。拿 happened_at 去量「我們放了多久」，
        # 等於新增一條會補歷史的來源就讓 CI 立刻紅——2026-07-26 就是這樣紅的。
        "ingested_at": ev.ingested_at,
        "status": "review",
        "category": None,          # enrich 填
        "company": ev.company,
        "track": None,             # 敘事 Track，enrich 填
        "fingerprint": ev.fingerprint,
        "facet": ev.facet,
        "tier_evidence": s["tier_evidence"],
        "independent_sources": s["independent_sources"],
        "suspected_reposts": s["suspected_reposts"],
        "primary_evidence": s["primary_evidence"],
        "confidence": s["confidence"],
        "heat": s["heat"],
        "impact": s["impact"],
        "value": s["value"],
        "score_factors": s["factors"],
        "blockers": [],            # 3d gate 填
        "warnings": [],
        "keywords": ev.keywords,
        "next_signal": "",
        "evidence": evidence_frontmatter(ev.evidence),
        "tags": ["event", "review"],
    }
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
    ev_lines = "\n".join(evidence_line(e) for e in ev.evidence)
    body = f"""
## 事實
{PLACEHOLDER}：一句話講清楚發生了什麼（enrich 依證據填、過 speak-human-tw）。

## 證據
{ev_lines}

## 脈絡
{PLACEHOLDER}：這件事放在什麼背景下才看得懂。

## 影響
{PLACEHOLDER}：對能力 / 成本 / 競爭結構的影響。

## 判斷
{PLACEHOLDER}（規則標註）：{'單一獨立來源 → 待證實' if ev.scores['independent_sources'] < 2 else '多來源佐證'}。

## 下一個訊號
{PLACEHOLDER}：接下來要觀察哪個可驗證訊號。
"""
    return f"---\n{front}\n---\n{body}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    cfg = vault / "_config"
    probe = vault / "_probe"
    events_dir = vault / "Events"

    # 選日：預設用 _probe 下最新有 signals-scored 的那天
    if args.day:
        day = args.day
    else:
        days = sorted(p.name for p in probe.iterdir()
                      if p.is_dir() and (p / "signals-scored.jsonl").exists()) if probe.exists() else []
        day = days[-1] if days else None
    if not day:
        print("[fatal] 找不到 signals-scored.jsonl（先跑 pulse-score.py）", file=sys.stderr)
        return 2
    scored_path = probe / day / "signals-scored.jsonl"
    if not scored_path.exists():
        print(f"[fatal] 無 {scored_path}", file=sys.stderr)
        return 2

    sources = load_sources(cfg)
    entities = load_entities(cfg)
    # 轉載鏈判定要的兩樣東西：gate.yaml 的門檻，與命名實體字典的比對表。
    # 字典讀原始 yaml 不讀 load_entities()——後者是給 infer_company 用的縮減版，
    # 沒有 aliases，而 aliases 正是這條規則能跨語言的原因。
    tc_cfg = load_translation_chain_cfg(cfg)
    ent_table = load_entity_table(cfg)

    signals = [json.loads(x) for x in scored_path.read_text("utf-8").splitlines() if x.strip()]
    ref_now = max([parse_dt(s.get("first_observed_at")) for s in signals if parse_dt(s.get("first_observed_at"))],
                  default=datetime.now(timezone.utc))

    # 讀既有 Events（跨日 attach）
    events = []
    existing_by_id = {}
    if events_dir.exists():
        for p in sorted(events_dir.glob("*.md")):
            fm, body = parse_frontmatter(p.read_text("utf-8"))
            if not fm.get("id"):
                continue
            happened = fm.get("happened_at") or ((str(fm.get("date")) + "T00:00:00Z") if fm.get("date") else "")
            ev = Event(fm["id"], fm.get("slug") or p.stem, fm.get("title") or p.stem,
                       happened, fm.get("fingerprint"), fm.get("facet"))
            ev.company = fm.get("company", "industry")
            ev.keywords = fm.get("keywords", [])
            ev.enriched = bool(fm.get("enriched"))   # 3c 已潤 → 重寫時保 prose
            # sticky：event_markdown() 會整份重寫 frontmatter，沒帶過去的欄位
            # 會被抹掉（fix/backfill-flag-erased-by-second-run 修的就是這個坑）。
            ev.ingested_at = fm.get("ingested_at")
            ev.title_zh = fm.get("title_zh")
            ev.title_zh_src = fm.get("title_zh_src")
            ev.orig_body = body
            ev.fm = fm
            ev.evidence.extend(evidence_from_frontmatter(fm.get("evidence")))
            ev.dirty = False
            ev.path = p
            events.append(ev)
            existing_by_id[ev.id] = ev

    # 依 eventability 排序（高的先，能開新 Event）
    signals = [s for s in signals if (s.get("title") or "").strip()]
    signals.sort(key=lambda s: (eventability(s, sources), s.get("published") or ""), reverse=True)

    created = attached = deferred = 0
    for sig in signals:
        title = sig["title"]
        published = sig.get("published") or sig.get("first_observed_at") or ""
        ev = next((c for c in events if cluster.belongs_to_event(
            title, published, c.title, c.happened_at)), None)
        if ev is None:
            score = eventability(sig, sources)
            if score < 70:
                deferred += 1
                continue
            fp = sig.get("fingerprint")
            # id 用「事件發生日 + (fingerprint|facet) 雜湊」→ 跨日穩定、同鍵不同 facet 不撞
            hkey = f"{fp or title}|{sig.get('facet')}"
            h = hashlib.sha1(hkey.encode("utf-8")).hexdigest()[:6]
            hd = parse_dt(published)
            hdate = hd.date().isoformat() if hd else day
            eid = f"evt-{hdate}-{h}"
            if eid in existing_by_id:  # 同鍵同日 → 視為既有
                ev = existing_by_id[eid]
            else:
                slug = f"{slugify(title)}-{h[:4]}"
                ev = Event(eid, slug, title, published, fp, sig.get("facet"))
                # 建立這則 Event 的那個訊號，probe 是什麼時候第一次看到它的。
                ev.ingested_at = sig.get("first_observed_at")
                ev.company = infer_company(sig.get("entity_hits"), entities)
                # 曾經是 list(cluster.title_tokens(title))[:8]，那是 set → 順序隨機，
                # 同一個標題每跑一次就換一組關鍵詞。理由與實測見 lib/cluster.py。
                ev.keywords = cluster.keyword_tokens(title, 8)
                events.append(ev)
                existing_by_id[eid] = ev
                created += 1
        else:
            attached += 1
        rel = int(round(cluster.title_similarity(title, ev.title) * 100))
        ev.add_evidence(sig["source_id"], sig.get("url", ""), title, rel, published)

    # rescore 所有動到的 Event
    changed = [e for e in events if e.dirty]
    for ev in changed:
        rescore(ev, sources, ref_now, tc_cfg, ent_table)

    # 摘要
    conf = [e.scores["confidence"] for e in changed if e.scores]
    print(f"pulse-cluster  day={day}  signals={len(signals)}")
    print(f"  created={created}  attached={attached}  deferred(eventability<70)={deferred}")
    print(f"  events changed={len(changed)}  (total in vault={len(events)})")
    if conf:
        import statistics
        print(f"  confidence: min={min(conf)} median={int(statistics.median(conf))} max={max(conf)}")
    multi = [e for e in changed if e.scores and e.scores['independent_sources'] >= 2]
    print(f"  ≥2 獨立來源的 Event: {len(multi)}/{len(changed)}")

    if args.dry_run:
        print("  [dry-run] 未寫檔")
        return 0
    events_dir.mkdir(parents=True, exist_ok=True)
    for ev in changed:
        out = ev.path or (events_dir / f"{ev.id}.md")
        if ev.enriched and ev.orig_body is not None and ev.fm is not None:
            out.write_text(rescored_enriched_markdown(ev), encoding="utf-8")  # 保 prose，只更新分數
        else:
            out.write_text(event_markdown(ev), encoding="utf-8")
    print(f"  → 寫入 {len(changed)} 個 Events/*.md")
    return 0


def rescored_enriched_markdown(ev):
    """已 enrich 的 Event 拿到新證據時：只更新分數與 evidence frontmatter，保留潤好的 prose body。"""
    s = ev.scores
    fm = dict(ev.fm)
    fm["tier_evidence"] = s["tier_evidence"]
    fm["independent_sources"] = s["independent_sources"]
    fm["suspected_reposts"] = s["suspected_reposts"]
    fm["primary_evidence"] = s["primary_evidence"]
    fm["confidence"] = s["confidence"]
    fm["heat"] = s["heat"]
    fm["impact"] = s["impact"]
    fm["value"] = s["value"]
    fm["score_factors"] = s["factors"]
    fm["evidence"] = evidence_frontmatter(ev.evidence)
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
    body = ev.orig_body if ev.orig_body.startswith("\n") else "\n" + ev.orig_body
    return f"---\n{front}\n---{body}"


def eventability(sig, sources):
    return cluster.eventability_score(sig, sources.get(sig.get("source_id")))


if __name__ == "__main__":
    sys.exit(main())
