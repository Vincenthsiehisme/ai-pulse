#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-render.py — Sprint 4a：把 published Event 渲成靜態站（純規則模板，零 LLM）。

等價 agent-pulse 的 export.ts + static-site：讀 Events/*.md 中 status=published 的，
輸出 dist/index.html（自帶樣式、單檔、無外部依賴、可直接丟 GitHub Pages）+ dist/data/timeline.json。
確定性：同一份 vault → 同一份 HTML。blocked / review 事件不渲染（不上公開站）。

視覺語言移植自 agent-pulse-main/web/public/assets/app.css：
  暗色 editorial / terminal 調、pulse 標記、等寬技術標籤、六層「推理層」各自語意色
  （事實=mint / 脈絡=purple / 影響=orange / 判斷=accent / 下一個訊號=amber），
  事實與判斷帶左側色條；淺色主題走 agent-pulse 的米色 light tokens。

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
# 每層的語意色 class + 英文小標（等寬標籤用），對映 agent-pulse 的 fact/analysis/impact/forecast
LAYER_META = {
    "事實":     ("fact",     "FACT",     True),
    "脈絡":     ("analysis", "CONTEXT",  False),
    "影響":     ("impact",   "IMPACT",   False),
    "判斷":     ("accent",   "VERDICT",  True),
    "下一個訊號": ("forecast", "NEXT SIGNAL", False),
}
CAT_LABEL = {"model-capability": "模型能力", "product": "產品", "research": "研究",
             "infra": "基礎設施", "capital": "資本", "policy": "政策"}


def section(body, heading):
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S)
    return (m.group(1).strip() if m else "")


def esc(s):
    return html.escape(str(s or ""))


CSS = """
:root{
  --canvas:#080a0f;--surface:#10141d;--surface-2:#151b26;--surface-soft:#0c1017;
  --text:#f2f1ec;--muted:#9aa3b2;--quiet:#697383;--border:#29313e;--border-soft:#1b222d;
  --accent:#ad91ff;--accent-strong:#8f6dff;
  --fact:#4ee4ba;--analysis:#9b8cff;--forecast:#f2bf62;--impact:#ff8b6b;--danger:#ff766c;
  --shadow:0 28px 80px rgb(0 0 0 / 34%);
  --radius-sm:9px;--radius-md:15px;--radius-lg:23px;
  --font:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang TC","Noto Sans TC","Microsoft JhengHei",Arial,sans-serif;
  --mono:ui-monospace,"SFMono-Regular","Cascadia Code","Roboto Mono",Menlo,Consolas,monospace;
  --shell:940px;
  color-scheme:dark;
}
@media(prefers-color-scheme:light){:root{
  --canvas:#eeece5;--surface:#fbfaf6;--surface-2:#fff;--surface-soft:#e7e3da;
  --text:#15171c;--muted:#5e6875;--quiet:#858b90;--border:#c9c4ba;--border-soft:#ddd8cf;
  --accent:#6550b7;--accent-strong:#51399f;
  --fact:#087e70;--analysis:#6550b7;--forecast:#94610d;--impact:#bd4b34;--danger:#b53f39;
  --shadow:0 28px 65px rgb(56 49 38 / 14%);
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--canvas);color:var(--text);font-family:var(--font);line-height:1.72;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit}
.shell{width:min(var(--shell),calc(100% - 44px));margin-inline:auto}

/* topbar */
.topbar{position:sticky;z-index:70;top:0;display:flex;align-items:center;height:66px;
  border-bottom:1px solid var(--border-soft);
  background:color-mix(in srgb,var(--canvas) 86%,transparent);backdrop-filter:blur(22px) saturate(1.3)}
.topbar .shell{display:flex;align-items:center}
.brand{display:flex;align-items:center;gap:11px;text-decoration:none}
.brand-mark{display:flex;align-items:center;justify-content:center;gap:2px;width:34px;height:34px;
  border:1px solid var(--border);border-radius:50%;background:var(--surface-soft)}
.brand-mark i{width:3px;border-radius:3px;background:var(--accent)}
.brand-mark i:nth-child(1){height:8px}.brand-mark i:nth-child(2){height:17px}.brand-mark i:nth-child(3){height:11px}
.brand strong{display:block;font-size:12px;letter-spacing:.16em}
.brand small{display:block;color:var(--muted);font:9px/1.4 var(--mono);letter-spacing:.04em}
.top-meta{margin-left:auto;color:var(--muted);font:11px var(--mono);letter-spacing:.04em}

/* hero */
.hero{padding:clamp(44px,6vw,72px) 0 clamp(28px,4vw,40px);border-bottom:1px solid var(--border-soft)}
.hero .kicker{color:var(--fact);font:10px var(--mono);letter-spacing:.18em;margin:0 0 14px}
.hero h1{font-size:clamp(2rem,5vw,2.9rem);line-height:1.06;letter-spacing:-.02em;margin:0 0 .5rem;font-weight:680}
.hero p{color:var(--muted);font-size:1.05rem;max-width:58ch;margin:.2rem 0 0}
.hero .stat{display:flex;flex-wrap:wrap;gap:22px;margin-top:26px;color:var(--quiet);font:11px var(--mono);letter-spacing:.05em}
.hero .stat b{color:var(--text);font-weight:600}

/* day groups */
main{padding:clamp(30px,4vw,44px) 0 clamp(72px,9vw,110px)}
.daygrp{margin-top:clamp(30px,4vw,44px)}
.daygrp:first-child{margin-top:0}
.day{display:flex;align-items:center;gap:12px;color:var(--muted);font:11px var(--mono);letter-spacing:.1em;margin:0 0 16px}
.day::after{content:"";flex:1;height:1px;background:var(--border-soft)}

/* event card */
article{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);
  padding:clamp(22px,3vw,30px);margin-bottom:18px;box-shadow:0 1px 0 rgb(0 0 0/6%);transition:border-color .16s,transform .16s}
article:hover{border-color:var(--border);transform:translateY(-1px)}
.chips{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:12px}
.chip{font:10px var(--mono);letter-spacing:.06em;padding:4px 9px;border-radius:999px;
  border:1px solid var(--border-soft);background:var(--surface-soft);color:var(--muted)}
.chip.co{color:var(--text);border-color:var(--border);font-weight:600}
.chip.warn{color:var(--forecast);border-color:color-mix(in srgb,var(--forecast) 45%,var(--border));
  background:color-mix(in srgb,var(--forecast) 8%,transparent)}
article h2{font-size:clamp(1.22rem,2.4vw,1.5rem);line-height:1.34;letter-spacing:-.01em;margin:.1rem 0 .55rem;font-weight:640}
.lead{color:var(--muted);font-size:1.02rem;margin:0 0 4px}

/* reasoning layers */
.layers{margin-top:20px;display:flex;flex-direction:column;gap:16px}
.layer .lbl{font:10px var(--mono);letter-spacing:.1em}
.layer p{margin:7px 0 0;font-size:.99rem;color:var(--text)}
.layer.fact .lbl{color:var(--fact)}
.layer.analysis .lbl{color:var(--analysis)}
.layer.impact .lbl{color:var(--impact)}
.layer.accent .lbl{color:var(--accent)}
.layer.forecast .lbl{color:var(--forecast)}
.layer.block{padding:15px 18px;border-radius:var(--radius-sm);background:var(--surface-soft)}
.layer.block.fact{border-left:3px solid var(--fact)}
.layer.block.accent{border-left:3px solid var(--accent)}
.layer.block p{margin-top:6px}

/* evidence + score */
.ev{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:22px 0 0;padding:0;list-style:none;
  color:var(--quiet);font:11px var(--mono);letter-spacing:.04em}
.ev .lbl{color:var(--muted)}
.ev a{display:inline-flex;padding:4px 9px;border-radius:7px;text-decoration:none;
  border:1px solid color-mix(in srgb,var(--fact) 34%,var(--border));color:var(--fact);
  background:color-mix(in srgb,var(--fact) 6%,var(--surface-soft));word-break:break-all}
.ev a:hover{border-color:var(--fact)}
.score{margin:16px 0 0;color:var(--quiet);font:11px var(--mono);letter-spacing:.05em;
  font-variant-numeric:tabular-nums;display:flex;flex-wrap:wrap;gap:16px}
.score b{color:var(--text);font-weight:600}

footer{border-top:1px solid var(--border-soft);padding:26px 0 60px;color:var(--quiet);
  font:11px var(--mono);letter-spacing:.04em;line-height:1.7}
footer .accent{color:var(--fact)}
"""

BRAND = '<span class="brand-mark"><i></i><i></i><i></i></span>'


def layer_html(heading, text):
    cls, label, block = LAYER_META[heading]
    b = " block" if block else ""
    return (f'<div class="layer {cls}{b}"><span class="lbl">{esc(label)} · {esc(heading)}</span>'
            f'<p>{esc(text)}</p></div>')


def render(events, generated):
    n = len(events)
    companies = len({e["company"] for e in events if e["company"]})
    by_date = defaultdict(list)
    for e in events:
        by_date[e["date"]].append(e)
    parts = [f"""<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Pulse — AI 產業情報</title>
<meta name="description" content="去 AI 口吻的 AI 產業情報：判斷走規則，敘述過 speak-human-tw。每則附一手證據。">
<meta name="color-scheme" content="dark light">
<style>{CSS}</style></head><body>
<header class="topbar"><div class="shell">
<a class="brand" href="#top">{BRAND}<span><strong>AI PULSE</strong><small>0 LLM 判斷 · speak-human-tw 敘述</small></span></a>
<span class="top-meta">{n} EVENTS · {esc(generated)}</span></div></header>
<a id="top"></a>
<section class="hero"><div class="shell">
<p class="kicker">DETERMINISTIC AI INTELLIGENCE</p>
<h1>AI 產業情報，<br>判斷走規則、敘述去 AI 口吻</h1>
<p>抓取、評分、收斂成事件、發布——全程可審計、可重現。判斷這一層零 LLM；敘述由 Cowork 依 speak-human-tw 潤稿，每則附一手證據，單一來源標「待證實」。</p>
<div class="stat"><span><b>{n}</b> 則已發布</span><span><b>{companies}</b> 家主體</span><span>更新 <b>{esc(generated)}</b></span></div>
</div></section>
<main><div class="shell">"""]
    for d in sorted(by_date, reverse=True):
        parts.append(f'<div class="daygrp"><p class="day">{esc(d)}</p>')
        for e in by_date[d]:
            chips = [f'<span class="chip co">{esc(e["company"])}</span>']
            if e["category"]:
                chips.append(f'<span class="chip">{esc(CAT_LABEL.get(e["category"], e["category"]))}</span>')
            if (e["independent"] or 0) < 2:
                chips.append('<span class="chip warn">待證實</span>')
            layers = "".join(layer_html(h, e["layers"][h]) for h in LAYERS if e["layers"].get(h))
            ev = "".join(
                f'<a href="{esc(u)}" rel="noopener" target="_blank">{esc(sid)}</a>'
                for sid, u in e["evidence"] if u)
            ev_block = (f'<ul class="ev"><span class="lbl">證據</span>{ev}</ul>' if ev else "")
            track = f'<span>{esc(e["track"])}</span>' if e["track"] else ""
            parts.append(f"""<article>
<div class="chips">{''.join(chips)}</div>
<h2>{esc(e['title'])}</h2>
<p class="lead">{esc(e['summary'])}</p>
<div class="layers">{layers}</div>
{ev_block}
<div class="score"><span>confidence <b>{esc(e['confidence'])}</b></span><span>heat <b>{esc(e['heat'])}</b></span>{track}</div>
</article>""")
        parts.append("</div>")
    parts.append(f"""</div></main>
<footer><div class="shell">由 <span class="accent">pulse-render.py</span> 確定性產生（同 vault → 同 HTML）。
判斷 0 LLM；敘述由 Cowork 依 speak-human-tw 潤稿。generated {esc(generated)}</div></footer>
</body></html>""")
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
