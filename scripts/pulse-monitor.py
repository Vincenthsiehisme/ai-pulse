#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-monitor.py — 無人值守健康監看（純規則、零 LLM）。

無人值守最怕的不是出錯，是**靜默沒動**：昨晚 Cowork 跑在 Actions 前面、worklist 是空的，
整條鏈看起來一切正常，其實有事件卡在 review 沒人管。這支就是那個 dead-man's switch。

只讀不寫、不判斷該不該發（那是 gate 的事），只把「現在卡住什麼」算成數字：
  1. 資料新鮮度：最新 _corpus/<date>/ 是不是今天；最後一次 probe 幾天前
  2. 卡關佇列：status=review 的事件數、最久卡幾天、blocker 分佈
  3. 未 enrich：review 且 body 仍含「待编辑」的（＝ enrich 沒跑到）
  4. 敘事鮮度：_probe/narrative-state.json 的簽章數
  5. **覆蓋範圍**：必盯實體多久沒被看見、可跑來源多久沒產出（見下）

第 5 項是 2026-07-24 漏抓 Claude Opus 5 之後補的。前四項回答的都是同一個問題——
「這條鏈有沒有在動」——那晚它們全綠，`probe_lag_days: 0`，因為鏈確實在動。
真正發生的事是：鏈跑得很完美，只是它什麼都看不見。sources.yaml 裡根本沒有 Anthropic。

**靜默死掉**跟**靜默瞎掉**是兩種病。前者有死人開關，後者在此之前沒有任何人在看。
覆蓋率看門狗不問「有沒有跑」，問「跑出來的東西涵蓋了誰」，並且分三層數：

    看見了嗎（corpus 命中）→ 產出了嗎（Event）→ 上線了嗎（published）

三個數字擺在一起才分得出是哪一層破的：全零＝來源根本沒這條線（Opus 5 那次）；
有 corpus 沒 Event＝聚類沒認出來；有 Event 沒 published＝門禁擋著（那是設計，不是故障）。

用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-monitor.py            # 人看的報告
  VAULT_DIR=... python scripts/pulse-monitor.py --json                   # 機器讀
  VAULT_DIR=... python scripts/pulse-monitor.py --alert-days 2           # 卡超過 2 天 → exit 1
  VAULT_DIR=... python scripts/pulse-monitor.py --alert-coverage         # 必盯實體沉默太久 → exit 1
依賴：PyYAML。**刻意不 import pulse-probe**——死人開關不該因為 requests 沒裝就叫不出聲。
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import parse_note  # noqa: E402

PLACEHOLDER = "待编辑"

# 這些 blocker 是「設計上就該永遠擋著」的（歷史存檔倒貨被新鮮度閘擋下），
# 不是漏跑、也修不好——算警報會天天狼來了，所以只計數、不觸警。
TERMINAL_BLOCKERS = {"stale_backfill"}


def _as_date(v):
    if not v:
        return None
    s = str(v).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


RUN_LIFECYCLES = {"active", "degraded", "probing"}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"\s+", " ", s).strip().lower()


def _alias_pattern(terms):
    """別名清單 → 一條正規式。ASCII 詞加詞界，CJK 不加（中文沒有詞界）。

    詞界是必要的：沒有它，alias「Scale」會命中 scaling、「Meta」會命中 metadata，
    看門狗就會在沒東西的時候安靜下來——**假陽性會讓警報失效**，比沒有警報更糟。
    但詞界擋不掉 meta-learning 這種真的用到那個字的句子，所以 --json 會把
    「哪個 alias 命中幾筆」攤開，讓人一眼看出這個數字是不是靠爛 alias 撐起來的。
    """
    parts = []
    for t in terms:
        n = _norm(t)
        if not n:
            continue
        esc = re.escape(n)
        if re.match(r"^[a-z0-9]", n) and re.search(r"[a-z0-9]$", n):
            esc = rf"\b{esc}\b"
        parts.append(esc)
    return re.compile("|".join(parts)) if parts else None


def coverage(vault, today, sources_cfg, entities_cfg):
    """→ 覆蓋範圍快照。純計數，不判斷、不寫檔。"""
    watch_cfg = sources_cfg.get("coverage_watch") or {}
    window = int(watch_cfg.get("window_days", 30))
    default_silent = int(watch_cfg.get("max_silent_days", 14))
    watch_list = watch_cfg.get("must_watch") or []

    canon = {}
    for sec in ("companies", "product_lines", "infrastructure"):
        for item in entities_cfg.get(sec) or []:
            canon[item["id"]] = [item["canonical"], *(item.get("aliases") or [])]

    watched = []
    for w in watch_list:
        eid = w["entity_id"]
        terms = canon.get(eid) or [w.get("label") or eid]
        watched.append({
            "entity_id": eid,
            "label": w.get("label") or (terms[0] if terms else eid),
            "max_silent_days": int(w.get("max_silent_days", default_silent)),
            "pending": bool(w.get("pending")),
            "terms": terms,
            "_re": _alias_pattern(terms),
            "sources": [], "corpus_hits": 0, "events": 0, "published": 0,
            "last_seen": None, "alias_hits": {},
        })

    # ---------------------------------------------------------------- corpus 層
    corpus = vault / "_corpus"
    all_days = sorted(d.name for d in corpus.iterdir() if d.is_dir()) if corpus.exists() else []
    in_window, per_source = [], {}
    for name in all_days:
        d = _as_date(name)
        if not d or (today - d).days > window or d > today:
            continue
        in_window.append(d)
        for f in sorted((corpus / name).glob("*.jsonl")):
            sid = f.stem
            for line in f.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                s = per_source.setdefault(sid, {"items": 0, "last": None})
                s["items"] += 1
                s["last"] = max(s["last"], d) if s["last"] else d
                # 優先用 probe 寫下的 entity_hits——那是 entities.yaml 字典的實際判定，
                # 跟聚類用的是同一把尺。這裡自己再 regex 一次只是舊語料的退路，
                # 兩把尺量出不同數字的話，該信的是聚類那把。
                hits = row.get("entity_hits")
                blob = _norm(f"{row.get('title', '')} {row.get('summary', '')}")
                for w in watched:
                    if isinstance(hits, list):
                        matched = w["entity_id"] in hits
                    else:
                        matched = bool(w["_re"] and w["_re"].search(blob))
                    if not matched:
                        continue
                    w["corpus_hits"] += 1
                    w["last_seen"] = max(w["last_seen"], d) if w["last_seen"] else d
                    if w["_re"]:
                        for hit in set(w["_re"].findall(blob)):
                            w["alias_hits"][hit] = w["alias_hits"].get(hit, 0) + 1

    # ----------------------------------------------------------------- 事件層
    events = vault / "Events"
    for p in sorted(events.glob("*.md")) if events.exists() else []:
        fm, _ = parse_note(p.read_text("utf-8"))
        d = _as_date(fm.get("date")) or _as_date(fm.get("happened_at"))
        if not d or (today - d).days > window:
            continue
        company = _norm(fm.get("company"))
        for w in watched:
            if w["_re"] and company and w["_re"].search(company):
                w["events"] += 1
                if fm.get("status") == "published":
                    w["published"] += 1

    # 語料期間比沉默門檻還短的時候，「從沒見過」是理所當然的，不是異常。
    # 新 vault 第一天就對著 30 條必盯清單狂叫，只會教人把警報關掉。
    history_days = (today - min(in_window)).days + 1 if in_window else 0

    runnable = [s for sec in ("official_sources", "kol_sources", "aggregator_sources")
                for s in (sources_cfg.get(sec) or [])
                if s.get("lifecycle") in RUN_LIFECYCLES]

    # 結構層：有沒有任何一條「會跑的」來源是衝著這家公司來的。
    # 這是四個數字裡唯一在第一天就有答案的——不必等語料累積，缺就是缺。
    # 2026-07-24 那晚 Anthropic 這一格是 0，而當時沒有任何東西在看這一格。
    for w in watched:
        w["sources"] = [s["id"] for s in runnable
                        if w["_re"] and w["_re"].search(_norm(s.get("owner")))]

    for w in watched:
        w.pop("_re")
        w["silent_days"] = (today - w["last_seen"]).days if w["last_seen"] else None
        w["last_seen"] = w["last_seen"].isoformat() if w["last_seen"] else None
        # 兩種警報，成因完全不同，不可混為一談：
        #   no_source  結構破洞——沒人在看這家。跟語料多寡無關，第一天就該叫。
        #   silent     有來源卻長期沒東西——來源死了、改版了、或門檻設得太緊。
        #              語料期間短於門檻時不判，否則新 vault 一開機就滿螢幕紅字。
        w["reason"] = None
        if not w["sources"]:
            w["reason"] = "no_source"
        elif ((w["silent_days"] is None or w["silent_days"] >= w["max_silent_days"])
                and history_days >= w["max_silent_days"]):
            w["reason"] = "silent"
        # pending＝設定檔裡白紙黑字承認「這家我們還沒補來源」。照樣印在表上，
        # 但不觸 exit code。理由不是它不重要，是**天天紅的燈等於沒有燈**：
        # 待辦事項每晚讓 CI 失敗一次，人只會學會忽略 CI，連帶忽略真正的回歸。
        # 要把待辦也當硬門檻的話，加 --alert-no-source。
        w["alerting"] = bool(w["reason"]) and not (w["pending"] and w["reason"] == "no_source")

    src_rows = []
    for s in sorted(runnable, key=lambda s: s["id"]):
        st = per_source.get(s["id"]) or {"items": 0, "last": None}
        src_rows.append({
            "id": s["id"], "track": s.get("track"), "owner": s.get("owner"),
            "lifecycle": s.get("lifecycle"), "items": st["items"],
            "last_item": st["last"].isoformat() if st["last"] else None,
            "silent_days": (today - st["last"]).days if st["last"] else None,
        })

    return {
        "window_days": window,
        "history_days": history_days,
        "corpus_days_in_window": len(in_window),
        "runnable_sources": len(runnable),
        "silent_sources": [r["id"] for r in src_rows if r["items"] == 0],
        "sources": src_rows,
        "must_watch": watched,
        "no_source": [w["label"] for w in watched if w["reason"] == "no_source"],
        "pending": [w["label"] for w in watched if w["pending"]],
        "silent": [w["label"] for w in watched if w["reason"] == "silent"],
        "alerting": [w["label"] for w in watched if w["alerting"]],
    }


def scan(vault, today):
    events = vault / "Events"
    review, published, unenriched = [], 0, 0
    blocker_hist = {}

    for p in sorted(events.glob("*.md")) if events.exists() else []:
        fm, body = parse_note(p.read_text("utf-8"))
        status = fm.get("status")
        if status == "published":
            published += 1
            continue
        if status != "review":
            continue
        d = _as_date(fm.get("happened_at")) or _as_date(fm.get("date"))
        age = (today - d).days if d else None
        blockers = list(fm.get("blockers") or [])
        for b in blockers:
            blocker_hist[b] = blocker_hist.get(b, 0) + 1
        if PLACEHOLDER in body:
            unenriched += 1
        # 只被 terminal blocker 擋著＝設計上的擋，不算「卡關待處理」
        terminal = bool(blockers) and set(blockers) <= TERMINAL_BLOCKERS
        review.append({
            "id": fm.get("id"),
            "file": p.name,
            "title": (fm.get("title") or "")[:70],
            "age_days": age,
            "blockers": blockers,
            "unenriched": PLACEHOLDER in body,
            "terminal": terminal,
        })

    # 資料新鮮度
    corpus = vault / "_corpus"
    days = sorted([d.name for d in corpus.iterdir() if d.is_dir()]) if corpus.exists() else []
    last_probe = _as_date(days[-1]) if days else None
    probe_lag = (today - last_probe).days if last_probe else None

    narr = vault / "_probe" / "narrative-state.json"
    tracks_tracked = len(json.loads(narr.read_text("utf-8"))) if narr.exists() else 0

    actionable = [e for e in review if not e["terminal"]]
    ages = [e["age_days"] for e in actionable if e["age_days"] is not None]
    # 「還沒 enrich 又放了幾天」＝ enrich 那條鏈根本沒跑到（不是門禁擋，是漏跑）
    stale_unenriched = [e["age_days"] for e in review
                        if e["unenriched"] and e["age_days"] is not None]
    return {
        "date": today.isoformat(),
        "last_probe_date": last_probe.isoformat() if last_probe else None,
        "probe_lag_days": probe_lag,
        "published_total": published,
        "review_total": len(review),
        "review_terminal": len(review) - len(actionable),
        "review_actionable": len(actionable),
        "review_unenriched": unenriched,
        "oldest_unenriched_days": max(stale_unenriched) if stale_unenriched else 0,
        "oldest_stuck_days": max(ages) if ages else 0,
        "blocker_hist": dict(sorted(blocker_hist.items(), key=lambda x: -x[1])),
        "tracks_tracked": tracks_tracked,
        "stuck": sorted(actionable, key=lambda e: -(e["age_days"] or 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="輸出 JSON（給機器 / 給排程摘要引用）")
    ap.add_argument("--alert-days", type=int, default=0,
                    help="待處理卡關最久天數 ≥ 此值 → exit 1（0＝不判警）")
    ap.add_argument("--alert-unenriched-days", type=int, default=0,
                    help="有事件未 enrich 且已放 ≥ 此天數 → exit 1（＝夜間 enrich 鏈漏跑的死人開關）")
    ap.add_argument("--alert-coverage", action="store_true",
                    help="必盯實體沉默超過門檻、或非 pending 的實體沒有來源 → exit 1")
    ap.add_argument("--alert-no-source", action="store_true",
                    help="連 pending（已知未覆蓋）的也算失敗——要把待辦逼到零時才開")
    ap.add_argument("--top", type=int, default=5, help="人看報告列出幾則卡最久的")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    today = datetime.now(timezone.utc).date()
    r = scan(vault, today)

    import yaml
    cfg = vault / "_config"
    r["coverage"] = coverage(
        vault, today,
        yaml.safe_load((cfg / "sources.yaml").read_text("utf-8")) or {},
        yaml.safe_load((cfg / "entities.yaml").read_text("utf-8")) or {})

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        lag = r["probe_lag_days"]
        lag_flag = "" if lag in (0, None) else ("  ⚠ 資料沒更新" if lag >= 2 else "  （昨天）")
        print(f"pulse-monitor  {r['date']}")
        print(f"  最後一次 probe: {r['last_probe_date']}（{lag} 天前）{lag_flag}")
        print(f"  已上線={r['published_total']}  review={r['review_total']}"
              f"（待處理={r['review_actionable']}／設計上擋著={r['review_terminal']}）"
              f"  未 enrich={r['review_unenriched']}  待處理最久={r['oldest_stuck_days']} 天")
        if r["blocker_hist"]:
            print("  ── blocker 分佈 ──")
            for b, n in r["blocker_hist"].items():
                print(f"    {n:3}  {b}")
        if r["stuck"]:
            print(f"  ── 待處理卡最久的 {min(args.top, len(r['stuck']))} 則 ──")
            for e in r["stuck"][:args.top]:
                mark = "未enrich" if e["unenriched"] else "已enrich"
                print(f"    [{e['age_days']}d/{mark}] {e['title']}")
                print(f"           {','.join(e['blockers']) or '(無 blocker 紀錄，gate 還沒跑過)'}")

        c = r["coverage"]
        print(f"  ── 覆蓋範圍（近 {c['window_days']} 天，實有語料 {c['history_days']} 天）──")
        if c["history_days"] < c["window_days"]:
            print(f"     （語料期間不足 {c['window_days']} 天，沉默天數僅供參考，"
                  "未達各自門檻前不觸警）")
        print(f"     {'必盯實體':<18} {'來源':>4} {'看見':>4} {'事件':>4} {'上線':>4}  最後看見")
        for w in c["must_watch"]:
            flag = {"no_source": "  ⚠ 沒有任何來源在看這家",
                    "silent": "  ⚠ 沉默過久"}.get(w["reason"], "")
            if w["pending"] and w["reason"] == "no_source":
                flag = "  ○ 已知未覆蓋（設定檔標 pending，不觸警）"
            silent = "從未" if w["silent_days"] is None else f"{w['silent_days']}d 前"
            print(f"     {w['label']:<18} {len(w['sources']):>4} {w['corpus_hits']:>4} "
                  f"{w['events']:>4} {w['published']:>4}  {silent}{flag}")
        dead = [s for s in c["sources"] if s["items"] == 0]
        print(f"     可跑來源 {c['runnable_sources']} 條，其中 {len(dead)} 條本窗口零產出"
              + ("：" + ", ".join(s["id"] for s in dead) if dead else ""))

    rc = 0
    cv = r["coverage"]
    if args.alert_coverage:
        gone = [w["label"] for w in cv["must_watch"] if w["reason"] == "no_source"
                and w["alerting"]]
        if gone:
            print(f"[alert] 必盯實體沒有任何來源在看：{'、'.join(gone)}"
                  "——2026-07-24 漏抓 Opus 5 就是這一格是 0", file=sys.stderr)
            rc = 1
        if cv["silent"]:
            print(f"[alert] 必盯實體沉默超過門檻：{'、'.join(cv['silent'])}"
                  "——來源可能已死或改版，鏈在跑但看不見這幾條線", file=sys.stderr)
            rc = 1
    if args.alert_no_source and cv["no_source"]:
        print(f"[alert] 尚無來源的必盯實體（含 pending）：{'、'.join(cv['no_source'])}",
              file=sys.stderr)
        rc = 1
    if args.alert_unenriched_days and r["oldest_unenriched_days"] >= args.alert_unenriched_days:
        print(f"[alert] 有事件未 enrich 已放 {r['oldest_unenriched_days']} 天"
              f"（門檻 {args.alert_unenriched_days}）——夜間潤稿那條鏈可能沒跑到", file=sys.stderr)
        rc = 1
    if args.alert_days and r["oldest_stuck_days"] >= args.alert_days:
        print(f"[alert] 有事件卡在 review 已 {r['oldest_stuck_days']} 天（門檻 {args.alert_days}）",
              file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
