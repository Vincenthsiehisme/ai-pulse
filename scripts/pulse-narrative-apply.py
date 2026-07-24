#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-narrative-apply.py — 把重寫後的 now/next 寫回 narratives.yaml（確定性後洗）。

- 只覆寫 result 指定主線的 now / next（thesis、lenses、其他主線一律不動）。
- 每段過 lib.voice_clean（去中國用語、全形標點）——敘述的最後一道確定性防線。
- 更新 narratives.yaml 的 updated；把 prep 產的 signatures 轉存為 narrative-state.json
  （下次 prep 才知道這批已處理、不再重寫）。

result JSON 格式：{ "<track-slug>": { "now": "...", "next": "..." }, ... }
（也接受 "thesis"，但預設半夜只重寫 now/next。）

用法：VAULT_DIR=... python scripts/pulse-narrative-apply.py --in narrative-result.json [--dry-run]
依賴：PyYAML。
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import voice_clean  # noqa: E402

import yaml  # noqa: E402

HEADER = ("# narratives.yaml —— 每條主線的編輯性敘事層（thesis / now / next + 決策鏡）。\n"
          "# 這一層是「敘述」，人為維護、可過 speak-human-tw，刻意獨立於 0-LLM 抓取管線；\n"
          "# 夜間鏈只在某主線有新事件時重寫該條 now / next（thesis、lenses 不動）。\n")
FIELDS = ("now", "next", "thesis")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    narr_file = vault / "_config" / "narratives.yaml"
    if not narr_file.exists():
        print("[fatal] 無 _config/narratives.yaml", file=sys.stderr)
        return 2
    doc = yaml.safe_load(narr_file.read_text("utf-8")) or {}
    doc.setdefault("version", 1)
    tracks = doc.setdefault("tracks", {})

    result = json.loads(Path(args.infile).read_text("utf-8"))
    changed = 0
    total_clean = 0
    for slug, fields in result.items():
        if slug not in tracks:
            print(f"  [skip] narratives.yaml 無此主線：{slug}")
            continue
        touched = []
        for k in FIELDS:
            v = fields.get(k)
            if v is None or str(v).strip() == "":
                continue
            cleaned, ch = voice_clean.clean(str(v))
            tracks[slug][k] = cleaned
            total_clean += len(ch)
            touched.append(k)
        if touched:
            changed += 1
            print(f"  ● {slug}：更新 {', '.join(touched)}")

    doc["updated"] = date.today().isoformat()

    if args.dry_run:
        print(f"\n[dry-run] 會更新 {changed} 條主線、{total_clean} 處後洗；未寫檔。")
        return 0

    body = yaml.dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
    narr_file.write_text(HEADER + body, encoding="utf-8")

    sig_file = vault / "_probe" / "narrative-signatures.json"
    if sig_file.exists():
        (vault / "_probe" / "narrative-state.json").write_text(
            sig_file.read_text("utf-8"), encoding="utf-8")

    print(f"\n共更新 {changed} 條主線、{total_clean} 處機械後洗。已寫回 narratives.yaml（updated={doc['updated']}）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
