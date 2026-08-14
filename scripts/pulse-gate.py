#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-gate.py — Sprint 3d：readiness gate + auto-publish（純規則，零 LLM）。

移植 agent-pulse pipeline/readiness.ts 的 blocker 清單 + auto-publish.ts：
對每個 status=review 的 Event 逐條檢查硬門禁，全過（0 blocker）→ status: published；
否則把 blockers[] 寫進 frontmatter（blocked 佇列看得到原因）。門檻讀 _config/gate.yaml。

紅線：這一層是**判斷**——由規則決定發不發，零 LLM。未 enrich 的事件必被 placeholder_content
擋住（body 還有「待編輯」佔位），所以雜訊不會混上線。佔位詞的正則放在 lib/notes.py，
與產生端共用一份；那邊同時認得簡體舊寫法，理由見該檔註解。

status 值域（2026-07-25 起三個）：
  review     等門禁。每次跑都重審，blockers[] 會被重寫。
  published  過了門禁。之後只做新鮮度重審，陳舊會被降級退回 review。
  dropped    **人工判定不追。** 這一層直接跳過它，不重審、不改 blockers、不改 status。
             enrich-prep / render / monitor 也都不看它。設計上它是隱形的，
             所以 pulse-dashboard.py 會另外產一頁 `_dashboards/dropped.md` 把它們
             連理由一起列出來——人工按掉可以，靜默丟棄不行。
             要復活就把 status 改回 review，下一班門禁自己會重跑。
             按掉時請一併寫 dropped_at / dropped_by / drop_reason，沒理由的 drop
             跟資料不見了沒有區別。
用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-gate.py [--dry-run]
依賴：PyYAML。
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import availability  # noqa: E402  「沒有內容」的三種原因，見 references/evidence-availability.md
from lib import sources as _srcmod  # noqa: E402  來源索引的單一真相源
from lib.notes import PLACEHOLDER_RE, dump_frontmatter, parse_note  # noqa: E402

import yaml  # noqa: E402

GENERIC_ENTITY = {"industry", "unknown", "other", "其他", "未知", ""}

# 「內容太薄」有三種原因，各自要不同的人去做不同的事，所以是三個 blocker 而不是
# 一個。門檻是同一個 thin_fact_min_chars；分岔的是那一則的證據拿不拿得到內文。
# 規格：references/evidence-availability.md〈門禁那一邊〉。
#
# thin_by_policy 是**終端狀態**——沒有人有事可做，它會永遠擋著。所以
# pulse-monitor.TERMINAL_BLOCKERS 必須同時認得它，否則那幾則會繼續躺在
# 「待處理卡關」裡，只是名字更精確地說明了它們為什麼修不好。兩份清單一起改。
THIN_BLOCKER = {
    availability.HAS_TEXT: "thin_fact",        # 內容在手上，是寫得薄 → 潤稿端
    availability.UNFETCHED: "thin_unfetched",  # 該抓到而沒抓到 → 抓取端
    availability.WITHHELD: "thin_by_policy",   # 政策不取 → 沒有人，把話寫對就好
}


def section(body, heading):
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S)
    return (m.group(1).strip() if m else "")


def _parse_iso(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load_corpus_index(vault):
    """讀 _corpus 全量一次，回 (first_observed, summaries)，兩個都以 url / url_canonical 為鍵。

    `first_observed` 給事件新鮮度閘用；`summaries` 給「這一筆手上到底有沒有內文」用。
    分成兩支函式的話會把 337 個 jsonl 走兩遍，而且第二遍很容易被人加上一個
    「只在需要時才讀」的條件——那正是新鮮度閘現在的長相（`if recency`），
    而薄的判定不能有那個條件：讀不到語料時每一則都會變成「沒有內文」。
    """
    import json as _json
    first_obs, summaries = {}, {}
    corpus = vault / "_corpus"
    if not corpus.exists():
        return first_obs, summaries
    for day_dir in sorted(corpus.iterdir()):
        if not day_dir.is_dir():
            continue
        for f in day_dir.glob("*.jsonl"):
            for line in f.read_text("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = _json.loads(line)
                except ValueError:
                    continue
                fo = r.get("first_observed_at")
                su = r.get("summary") or ""
                for u in (r.get("url"), r.get("url_canonical")):
                    if not u:
                        continue
                    if u not in first_obs:
                        first_obs[u] = fo
                    # 摘要取第一個非空的：同一個 url 可能在多天的語料裡出現，
                    # 早期那一筆可能是空的、後來補抓到了。往「有內容」倒。
                    if not summaries.get(u):
                        summaries[u] = su
    return first_obs, summaries


def event_lead_days(fm, first_obs):
    """事件新鮮度 lead = min(證據 first_observed) − happened_at（天）；算不出→None。"""
    hp = _parse_iso(fm.get("happened_at") or fm.get("date"))
    if hp is None:
        return None
    leads = []
    for e in (fm.get("evidence") or []):
        d = _parse_iso(first_obs.get(e.get("url")))
        if d is not None:
            leads.append((d - hp).days)
    return min(leads) if leads else None


def thin_blocker(fm, srcs, summaries):
    """這一則薄，該掛哪一個 blocker。三選一，判準見 lib/availability.thin_reason。

    `srcs` 是 source_id → 來源設定；`summaries` 是 url → 語料裡那一筆的摘要。
    """
    rows = [(srcs.get(e.get("source_id")), summaries.get(e.get("url")) or "")
            for e in (fm.get("evidence") or [])]
    return THIN_BLOCKER[availability.thin_reason(rows)]


def evaluate(fm, body, gate, srcs, summaries):
    """回 (blockers, warnings)。純函式：不讀時鐘、不讀網路、不讀磁碟。

    `srcs` / `summaries` **故意沒有預設值**。給了 None 預設之後，忘了傳的呼叫端
    會靜靜退回舊行為（薄的一律判 thin_fact），而沒有任何測試會紅——變異清單記過
    五次的病（M198 / M274 / M283 / M291 / M296：釘了判準沒釘消費端）。
    必填參數讓「忘了傳」變成 TypeError。規格 references/readiness-gate.md。
    """
    r = gate.get("readiness", {})
    min_conf = r.get("min_confidence", 60)
    thin_min = r.get("thin_fact_min_chars", 20)
    heat_th = r.get("heat_threshold", 70)
    heat_min_ind = r.get("heat_min_independent_sources", 2)
    heat_min_plat = r.get("heat_min_platform_breadth", 2)

    blockers = []
    fact = section(body, "事實")
    summary = (fm.get("summary") or "").strip()

    # placeholder：body 任一處還有佔位詞 → 未 enrich
    if PLACEHOLDER_RE.search(body):
        blockers.append("placeholder_content")
    if len(fact) < thin_min or len(summary) < thin_min:
        # 薄的原因分三種，名字不同、要人做的動作也不同（其中一種是「什麼都不用做」）。
        blockers.append(thin_blocker(fm, srcs, summaries))
    # thin_research_analysis：research 類需有實質分析
    if str(fm.get("category") or "").lower() in ("research", "paper"):
        if len(section(body, "影響")) < 40 or len(section(body, "脈絡")) < 30:
            blockers.append("thin_research_analysis")
    if str(fm.get("company") or "").strip().lower() in GENERIC_ENTITY:
        blockers.append("generic_entity")
    cat = str(fm.get("category") or "").strip()
    if not cat or cat == "industry":
        blockers.append("missing_category")
    if not (fm.get("keywords") or []):
        blockers.append("missing_keywords")
    if not (fm.get("track") or ""):
        blockers.append("missing_track")
    if not (fm.get("evidence") or []):
        blockers.append("missing_evidence")
    if not (fm.get("primary_evidence") or 0):
        blockers.append("missing_primary_evidence")
    if (fm.get("confidence") or 0) < min_conf:
        blockers.append("low_confidence")
    factors = fm.get("score_factors") or {}
    # heat 有數字就必須有傳播證據撐著（紅線 4：禁止把手工分數包裝成已測量熱度）。
    # 2026-07-26 之前這件事沒有人守：四項傳播輸入全是 0，heat 照樣印出 8–32，
    # 敘述層甚至已經開始拿那個數字當論據（_config/narratives.yaml）。
    # scoring.py 現在在源頭就回 None，這條是它的執法點——手改 frontmatter、
    # 遷移腳本寫壞、或者哪天有人把無條件計算加回去，都會在這裡紅。
    # 規格見 references/readiness-gate.md。
    if fm.get("heat") is not None and int(factors.get("propagationSignals", 0) or 0) <= 0:
        blockers.append("unmeasured_heat")
    # 休眠中、不是裝飾：heat 現在只有真的量到傳播訊號才有數字，所以這一關要等
    # 社群線（M3）接上才走得到。留著是因為它語意正確且 selftest 正反兩面都釘住了，
    # 那天它會是活的碼，不是一段兩個月沒跑過的碼。
    if (fm.get("heat") or 0) >= heat_th and (
        (factors.get("independentSources", 0) < heat_min_ind)
        or (factors.get("platformBreadth", 0) < heat_min_plat)
    ):
        blockers.append("unsupported_heat")

    warnings = []
    if (fm.get("independent_sources") or 0) < 2:
        warnings.append("single-source fact; cross-source corroboration pending")
    return blockers, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    gate = yaml.safe_load((vault / "_config" / "gate.yaml").read_text("utf-8"))
    if not events_dir.exists():
        print("[fatal] 無 Events/ 目錄", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc).isoformat()
    recency = (gate.get("quality") or {}).get("recency_max_lead_days", 0)
    # 語料**無條件**讀：新鮮度閘可以在 recency=0 時不讀（那是它自己的開關），
    # 薄的判定不行——讀不到語料等於每一則都「沒有內文」，而那會讓一批本來
    # 可以寫厚的事件被判成政策終端，然後從監看裡消失。
    first_obs, summaries = load_corpus_index(vault)
    if not recency:
        first_obs = {}
    srcs = _srcmod.source_index(
        yaml.safe_load((vault / "_config" / "sources.yaml").read_text("utf-8")) or {})
    if not summaries:
        # 空語料是合法的（全新的 vault），但它會讓薄的原因只能靠來源設定判。
        # 說出來，不要讓它變成一個看不見的降級。
        print("[warn] 語料索引是空的，薄的原因只能靠 sources.yaml 判", file=sys.stderr)
    reviewed = published = blocked = demoted = 0
    blocker_hist = {}
    published_titles = []

    def _write(path, fm, body):
        if not args.dry_run:
            path.write_text(f"---\n{dump_frontmatter(fm)}\n---{body if body.startswith(chr(10)) else chr(10)+body}",
                            encoding="utf-8")

    for p in sorted(events_dir.glob("*.md")):
        fm, body = parse_note(p.read_text("utf-8"))
        status = fm.get("status")
        if status not in ("review", "published"):
            continue
        lead = event_lead_days(fm, first_obs) if recency else None
        stale = bool(recency) and lead is not None and lead > recency

        # 已上線的事件：只做新鮮度重審。陳舊（歷史存檔倒貨）→ 降級退回 review。
        if status == "published":
            if stale:
                fm["status"] = "review"
                bl = list(fm.get("blockers") or [])
                if "stale_backfill" not in bl:
                    bl.append("stale_backfill")
                fm["blockers"] = bl
                demoted += 1
                blocked += 1
                blocker_hist["stale_backfill"] = blocker_hist.get("stale_backfill", 0) + 1
                _write(p, fm, body)
            continue

        # status == review：正常門禁 + 新鮮度閘
        reviewed += 1
        blockers, warnings = evaluate(fm, body, gate, srcs, summaries)
        if stale and "stale_backfill" not in blockers:
            blockers = blockers + ["stale_backfill"]
        fm["blockers"] = blockers
        fm["warnings"] = warnings
        if not blockers:
            fm["status"] = "published"
            fm["published_at"] = now
            fm["tags"] = [("published" if t == "review" else t) for t in (fm.get("tags") or [])]
            published += 1
            published_titles.append(fm.get("title", fm.get("id")))
        else:
            blocked += 1
            for b in blockers:
                blocker_hist[b] = blocker_hist.get(b, 0) + 1
        _write(p, fm, body)

    print(f"pulse-gate  reviewed={reviewed}  published={published}  blocked={blocked}  demoted(陳舊退回)={demoted}"
          f"{'  [dry-run]' if args.dry_run else ''}")
    if published_titles:
        print("  ── published ──")
        for t in published_titles:
            print(f"    ✓ {t[:72]}")
    if blocker_hist:
        print("  ── blocker 分佈 ──")
        for b, n in sorted(blocker_hist.items(), key=lambda x: -x[1]):
            print(f"    {n:3}  {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
