#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-enrich-prep.py — Sprint 3c 前置（確定性）：掃出要 enrich 的 Event，打包成 worklist。

只挑 status=review 且 body 仍含「待編輯」佔位的 Event（已 enrich 的跳過 → 冪等、成本封頂）。
佔位詞比對走 lib.notes.PLACEHOLDER_RE，不用字串 in：既有事件寫的是簡體舊寫法，
只認新寫法的話它們會永遠排不進潤稿佇列，而且不會有任何錯誤訊息。
把每個 Event 綁定的證據，從 _corpus 解析出真正的標題 + 摘要文字，湊成一份乾淨的 worklist，
交給 Cowork（或排程 Cowork 任務）依 references/enrich-runbook.md 逐個寫 prose。

輸出：_probe/enrich-worklist.json
用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-enrich-prep.py
依賴：PyYAML。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import PLACEHOLDER_RE, parse_note  # noqa: E402


def build_corpus_index(vault):
    """url → {title, summary}。跨所有 _corpus 日期。"""
    idx = {}
    corpus = vault / "_corpus"
    if not corpus.exists():
        return idx
    for day_dir in corpus.iterdir():
        if not day_dir.is_dir():
            continue
        for jf in day_dir.glob("*.jsonl"):
            for line in jf.read_text("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for key in (r.get("url"), r.get("url_canonical")):
                    if key:
                        idx.setdefault(key, {"title": r.get("title", ""), "summary": r.get("summary", "")})
    return idx


def main():
    vault = Path(os.environ["VAULT_DIR"])
    events_dir = vault / "Events"
    if not events_dir.exists():
        print("[fatal] 無 Events/ 目錄（先跑 pulse-cluster.py）", file=sys.stderr)
        return 2

    corpus = build_corpus_index(vault)
    worklist = []
    skipped_enriched = 0

    for p in sorted(events_dir.glob("*.md")):
        text = p.read_text("utf-8")
        fm, body = parse_note(text)
        if fm.get("status") != "review":
            continue
        if not PLACEHOLDER_RE.search(body):
            skipped_enriched += 1
            continue
        evidence = []
        for e in (fm.get("evidence") or []):
            url = e.get("url")
            c = corpus.get(url, {})
            evidence.append({
                "source_id": e.get("source_id"),
                "url": url,
                "title": c.get("title") or "",
                "summary": c.get("summary") or "",
            })
        worklist.append({
            "id": fm.get("id"),
            "path": p.name,
            "title": fm.get("title"),
            "fingerprint": fm.get("fingerprint"),
            "facet": fm.get("facet"),
            "company_guess": fm.get("company"),
            "independent_sources": fm.get("independent_sources"),
            "tier_evidence": fm.get("tier_evidence"),
            "evidence": evidence,
        })

    out = vault / "_probe" / "enrich-worklist.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(worklist, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pulse-enrich-prep  待 enrich={len(worklist)}  已 enrich 跳過={skipped_enriched}")
    print(f"  → {out}")
    if worklist:
        ev_counts = [len(w["evidence"]) for w in worklist]
        print(f"  證據/事件: min={min(ev_counts)} max={max(ev_counts)}；有摘要的證據佔比："
              f"{sum(1 for w in worklist for e in w['evidence'] if e['summary'])}"
              f"/{sum(ev_counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
