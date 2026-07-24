#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-score.py — Sprint 3a：訊號品質分 + 聚類鍵（fingerprint/facet）。純規則、零 LLM。

讀 _corpus/<day>/*.jsonl（pulse-probe 產）+ _config/{sources,gate}.yaml，
逐筆算五維品質分、掛 event_fingerprint / event_facet，
低於 gate.yaml.quality.discard_below 者丟棄（但記數，不靜默），
其餘寫 _probe/<day>/signals-scored.jsonl（3b 聚類的輸入）。

用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-score.py            # 跑最新一天
  VAULT_DIR=... python scripts/pulse-score.py --day 2026-07-24
  VAULT_DIR=... python scripts/pulse-score.py --dry-run                # 不寫檔
依賴：PyYAML（與 pulse-probe 相同）。lib/ 為純 stdlib。
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cluster, quality  # noqa: E402

import yaml  # noqa: E402


def load_sources(cfg):
    raw = yaml.safe_load((cfg / "sources.yaml").read_text("utf-8"))
    out = {}
    for key in ("official_sources", "kol_sources", "aggregator_sources"):
        for s in (raw.get(key) or []):
            if isinstance(s, dict) and s.get("id"):
                out[s["id"]] = s
    return out


def latest_day(corpus_dir):
    days = sorted(p.name for p in corpus_dir.iterdir() if p.is_dir())
    return days[-1] if days else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None, help="覆寫輸出路徑")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    cfg = vault / "_config"
    corpus_dir = vault / "_corpus"
    if not corpus_dir.exists():
        print(f"[fatal] 無 _corpus 目錄：{corpus_dir}", file=sys.stderr)
        return 2

    day = args.day or latest_day(corpus_dir)
    if not day:
        print("[fatal] _corpus 下沒有任何日期目錄", file=sys.stderr)
        return 2
    day_dir = corpus_dir / day
    if not day_dir.exists():
        print(f"[fatal] 無此日期：{day_dir}", file=sys.stderr)
        return 2

    sources = load_sources(cfg)
    gate = yaml.safe_load((cfg / "gate.yaml").read_text("utf-8"))
    q = gate.get("quality", {})
    thresholds = q.get("grade_thresholds", {"A": 85, "B": 70, "C": 55, "D": 40})
    discard_below = q.get("discard_below", 40)
    run_now = datetime.now(timezone.utc)  # 僅在 record 無 first_observed_at 時 fallback

    kept = []
    discarded = 0
    skipped_dormant = 0
    grade_dist = Counter()
    facet_dist = Counter()
    flag_dist = Counter()
    fp_hits = 0
    missing_source = Counter()

    files = sorted(day_dir.glob("*.jsonl"))
    for fp in files:
        for line in fp.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            sid = rec.get("source_id") or fp.stem
            src = sources.get(sid)
            if src and src.get("lifecycle") == "dormant":
                skipped_dormant += 1   # dormant 來源的既有 corpus 不再進 pipeline（如已判死的源）
                continue
            if src is None:
                missing_source[sid] += 1
                src = {"track": rec.get("track"), "tier": rec.get("tier"),
                       "role": None, "source_category": None}
            sc = quality.score_signal(rec, src, run_now, thresholds)
            title = rec.get("title") or ""
            fingerprint = cluster.event_fingerprint(title)
            facet = cluster.event_facet(title)
            if fingerprint:
                fp_hits += 1
            grade_dist[sc["grade"]] += 1
            facet_dist[facet] += 1
            for fl in sc["flags"]:
                flag_dist[fl] += 1
            if sc["total"] < discard_below:
                discarded += 1
                continue
            rec2 = dict(rec)
            rec2["quality"] = sc["total"]
            rec2["grade"] = sc["grade"]
            rec2["quality_dims"] = sc["dimensions"]
            rec2["quality_flags"] = sc["flags"]
            rec2["effective_role"] = sc["effective_role"]
            rec2["fingerprint"] = fingerprint
            rec2["facet"] = facet
            kept.append(rec2)

    total = len(kept) + discarded
    print(f"pulse-score  day={day}  files={len(files)}  signals={total}")
    print(f"  kept={len(kept)}  discarded(<{discard_below})={discarded}  skipped(dormant來源)={skipped_dormant}")
    print("  grade:", dict(sorted(grade_dist.items())))
    pct = (100 * fp_hits // total) if total else 0
    print(f"  fingerprint 命中: {fp_hits}/{total}  ({pct}%)")
    print("  facet:", dict(facet_dist.most_common()))
    if flag_dist:
        print("  top flags:", dict(flag_dist.most_common(5)))
    if missing_source:
        print("  [warn] sources.yaml 查無來源:", dict(missing_source))

    if args.dry_run:
        print("  [dry-run] 未寫檔")
        return 0
    out_path = Path(args.json) if args.json else (vault / "_probe" / day / "signals-scored.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  → {out_path}  ({len(kept)} 筆)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
