#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-render.py — Sprint 4a：把 published Event 渲成靜態站（純規則模板，零 LLM）。

等價 agent-pulse 的 export.ts + static-site：讀 Events/*.md 中 status=published 的，
輸出 dist/index.html（自帶樣式、單檔、無外部依賴、可直接丟 GitHub Pages）+ dist/data/timeline.json。
確定性：同一份 vault → 同一份 HTML。blocked / review 事件不渲染（不上公開站）。

用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-render.py [--out dist]
依賴：PyYAML。
"""
import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import parse_note  # noqa: E402

LAYERS = ["事實", "脈絡", "影響", "判斷", "下一個訊號"]
CAT_LABEL = {"model-capability": "模型能力", "product": "產品", "research": "研究",
             "infra": "基礎設施", "capital": "資本", "policy": "政策"}


def section(body, heading):
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S)
    return (m.group(1).strip() if m else "")


def esc(s):
    return html.escape(str(s or ""))


CSS = """
:root{--bg:#fbfbfa;--fg:#1a1a1a;--mut:#6b6b6b;--card:#fff;--line:#e6e6e3;--accent:#2f6f4f;--warn:#9a6b00;--chip:#eef0ee}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e9e9e7;--mut:#9a9a97;--card:#1e1e1e;--line:#2c2c2c;--accent:#6fca97;--warn:#e0b34a;--chip:#262826}}
*{box-sizing:border-box}html{font-size:16px}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,"Segoe UI","PingFang TC","Noto Sans TC",system-ui,sans-serif;line-height:1.75}
.wrap{max-width:760px;margin:0 auto;padding:2.5rem 1.2rem 4rem}
header h1{font-size:1.9rem;margin:0 0 .2rem;letter-spacing:-.01em}
.tag{color:var(--mut);font-size:.95rem;margin:0}
.meta-line{color:var(--mut);font-size:.85rem;margin-top:.9rem;border-top:1px solid var(--line);padding-top:.9rem}
.daygrp{margin-top:2.4rem}
.day{font-size:.8rem;font-weight:600;color:var(--mut);letter-spacing:.04em;text-transform:uppercase;margin:0 0 .8rem}
article{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.3rem 1.4rem;margin-bottom:1.1rem}
article h2{font-size:1.2rem;line-height:1.4;margin:.35rem 0 .5rem}
.chips{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
.chip{font-size:.72rem;padding:.12rem .5rem;border-radius:999px;background:var(--chip);color:var(--mut)}
.chip.co{color:var(--fg);font-weight:600}
.chip.warn{background:transparent;border:1px solid var(--warn);color:var(--warn)}
.lead{font-size:1.02rem;color:var(--fg);margin:.2rem 0 .9rem}
.layers{border-top:1px dashed var(--line);padding-top:.7rem}
.layers h3{font-size:.78rem;color:var(--accent);margin:.85rem 0 .15rem;font-weight:700}
.layers p{margin:.1rem 0;font-size:.96rem}
.ev{margin:.9rem 0 0;padding:0;list-style:none;font-size:.85rem}
.ev li{margin:.2rem 0}.ev a{color:var(--accent);text-decoration:none;word-break:break-all}.ev a:hover{text-decoration:underline}
.score{color:var(--mut);font-size:.75rem;font-variant-numeric:tabular-nums;margin-top:.8rem}
footer{color:var(--mut);font-size:.8rem;margin-top:3rem;border-top:1px solid var(--line);padding-top:1rem}
"""


def render(events, generated):
    n = len(events)
    by_date = defaultdict(list)
    for e in events:
        by_date[e["date"]].append(e)
    parts = [f"""<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Pulse — AI 產業情報</title>
<meta name="description" content="去 AI 口吻的 AI 產業情報：判斷走規則，敘述過 speak-human-tw。">
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>AI Pulse</h1>
<p class="tag">AI 產業情報 · 判斷走規則、敘述去 AI 口吻</p>
<p class="meta-line">{n} 則已發布事件 · 更新於 {esc(generated)} · 每則附一手證據連結，單一來源標「待證實」</p></header>"""]
    for d in sorted(by_date, reverse=True):
        parts.append(f'<div class="daygrp"><p class="day">{esc(d)}</p>')
        for e in by_date[d]:
            chips = [f'<span class="chip co">{esc(e["company"])}</span>']
            if e["category"]:
                chips.append(f'<span class="chip">{esc(CAT_LABEL.get(e["category"], e["category"]))}</span>')
            if (e["independent"] or 0) < 2:
                chips.append('<span class="chip warn">待證實</span>')
            layers = "".join(
                f"<h3>{esc(h)}</h3><p>{esc(e['layers'][h])}</p>"
                for h in LAYERS if e["layers"].get(h))
            ev = "".join(
                f'<li><a href="{esc(u)}" rel="noopener">{esc(sid)}</a></li>'
                for sid, u in e["evidence"])
            parts.append(f"""<article>
<div class="chips">{''.join(chips)}</div>
<h2>{esc(e['title'])}</h2>
<p class="lead">{esc(e['summary'])}</p>
<div class="layers">{layers}</div>
<ul class="ev">證據：{ev}</ul>
<p class="score">confidence {e['confidence']} · heat {e['heat']} · {e['track'] or ''}</p>
</article>""")
        parts.append("</div>")
    parts.append(f'<footer>由 pulse-render.py 確定性產生（同 vault → 同 HTML）。'
                 f'判斷 0 LLM；敘述由 Cowork 依 speak-human-tw 潤稿。generated {esc(generated)}</footer>')
    parts.append("</div></body></html>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    out = vault / args.out
    (out / "data").mkdir(parents=True, exist_ok=True)

    events = []
    for p in sorted((vault / "Events").glob("*.md")):
        fm, body = parse_note(p.read_text("utf-8"))
        if fm.get("status") != "published":
            continue
        events.append({
            "id": fm.get("id"), "title": fm.get("title", ""), "date": str(fm.get("date") or ""),
            "company": fm.get("company", ""), "category": fm.get("category") or "",
            "track": fm.get("track") or "", "summary": fm.get("summary") or "",
            "confidence": fm.get("confidence", 0), "heat": fm.get("heat", 0),
            "independent": fm.get("independent_sources", 0),
            "layers": {h: section(body, h) for h in LAYERS},
            "evidence": [(e.get("source_id"), e.get("url")) for e in (fm.get("evidence") or [])],
        })
    events.sort(key=lambda x: x["date"], reverse=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    (out / "index.html").write_text(render(events, generated), encoding="utf-8")
    (out / "data" / "timeline.json").write_text(
        json.dumps({"generated": generated, "count": len(events),
                    "events": [{k: e[k] for k in ("id", "title", "date", "company", "category",
                                                  "summary", "confidence", "heat")} for e in events]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pulse-render  published={len(events)}  → {out/'index.html'}  + data/timeline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
