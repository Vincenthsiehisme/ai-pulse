#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-render.py — Sprint 4a：把 vault 渲成多頁靜態站（純規則模板，零 LLM）。

移植 agent-pulse-main/web/public 的多頁結構與設計語言，全部 server-side 靜態產生：

  dist/index.html              關鍵變化（home）
  dist/lines/index.html        領域趨勢（lines）
  dist/timeline/index.html     事件時間軸（timeline）
  dist/signals/index.html      來源更新（signals）
  dist/events/<slug>/index.html 每則事件詳情頁（dossier：發展歷程 + 六層 + 評分理由 + 相關）
  dist/assets/app.css / app.js 共用樣式與輕量增強
  dist/data/timeline.json      事件索引

確定性：同一份 vault → 同一份輸出。只有 status=published 進公開頁。
發展歷程從 _corpus 解析每筆證據的標題/日期/來源角色（純規則分型）；評分理由讀 score_factors。

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
from lib import tracks as tracks_lib  # noqa: E402  主線對照表單一真相源
from lib import zhtext  # noqa: E402  譯文驗章單一真相源，見 lib/zhtext.py
from lib.sources import SECTIONS  # noqa: E402  分節清單單一真相源
from lib.quality import parse_dt  # noqa: E402
from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md

import yaml  # noqa: E402

LAYERS = ["事實", "脈絡", "影響", "判斷", "下一個訊號"]
LAYER_META = {
    "事實":     ("fact",     "FACT",     True),
    "脈絡":     ("analysis", "CONTEXT",  False),
    "影響":     ("impact",   "IMPACT",   False),
    "判斷":     ("accent",   "VERDICT",  True),
    "下一個訊號": ("forecast", "NEXT SIGNAL", False),
}
CAT_LABEL = {"model-capability": "模型能力", "product": "產品", "research": "研究",
             "infra": "基礎設施", "capital": "資本", "policy": "政策"}
# 對照表搬到 lib/tracks.py（單一真相源），理由見該檔開頭。
TRACKS = list(tracks_lib.TRACKS)
TRACK_BY_NAME = dict(tracks_lib.BY_NAME)
TRACK_ALIASES = dict(tracks_lib.ALIAS)
NAV = [("home", "關鍵變化", ""), ("lines", "領域趨勢", "lines/"),
       ("timeline", "事件時間軸", "timeline/"), ("signals", "來源更新", "signals/"),
       ("github", "GitHub 動能", "github/")]

# 發展歷程分型（純規則）：type -> (中文標籤, css class)
DEV_LABEL = {"origin": ("起點", "fact"), "official": ("官方", "accent"),
             "discussion": ("討論", "forecast"), "response": ("後續", "impact")}
# 10 維評分因子的中文標籤與顯示上限（用來畫比例條）
FACTOR_META = [
    ("authority", "權威", 100), ("corroboration", "佐證", 100), ("primaryEvidence", "一手證據", 100),
    ("independentSources", "獨立來源", 5), ("uniqueAuthors", "獨立作者", 8),
    ("platformBreadth", "平台廣度", 5), ("regionBreadth", "地域廣度", 4),
    ("velocity", "傳播速度", 100), ("freshness", "新鮮度", 100),
    ("propagationSignals", "傳播訊號", 4),
]

# heat 可以是 None：一項傳播訊號都沒量到時 scoring.py 不編一個數字出來
# （紅線 8，規格見 references/readiness-gate.md）。前台印「未量測」不印 0——
# 0 會被讀成「量過了，很冷」，那比不印更糟。
HEAT_UNMEASURED = "未量測"


def heat_text(v):
    return HEAT_UNMEASURED if v is None else v

BRAND = '<span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>'
ARROW = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
BACK = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>'
EXT = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M18 14v5H5V6h5"/></svg>'
SEARCH = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>'
SUN = ('<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
       '<path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>')


# 站上每一個日期都是台北日（fmt_date / date_display）。這行字要跟著它們一起出現：
# 一個沒有時區標示的日期，讀者會預設是自己的——而 52 則裡有 12 則那個預設是錯的。
TZ_LABEL = clock.DISPLAY_TZ_LABEL


def esc(s):
    return html.escape(str(s or ""))


def section(body, heading):
    m = re.search(rf"^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, flags=re.M | re.S)
    return (m.group(1).strip() if m else "")


def fmt_date(s):
    """→ **台北**日期字串。這是給人看的那一層。

    儲存層一律 UTC（`evt-<日期>-` 的 id、`date` 欄位都是），但讀者在台北：
    UTC 16:00–24:00 發生的事對他來說已經是隔天。2026-07-27 實測 52 則 Event
    有 12 則（23%）差這一天。規格見 references/timezones.md。

    解不開的時候退回原字串前十碼——那是儲存層的 UTC 日期，會差一天，但
    「顯示一個可能差一天的日期」比「顯示 —」有用。
    """
    d = parse_dt(s) if s else None
    return clock.display_date_str(d) if d else (str(s)[:10] if s else "—")


def prettify_source(sid):
    s = re.sub(r"^src-", "", str(sid or ""))
    s = s.replace("-", " ").replace("_", " ").strip()
    fix = {"deepmind": "DeepMind", "openai": "OpenAI", "arxiv": "arXiv", "hn": "Hacker News",
           "ai": "AI", "eu": "EU", "itre": "ITRE", "kol": "KOL", "blog": "Blog", "rss": "RSS",
           "nvidia": "NVIDIA", "the": "The", "decoder": "Decoder", "infoq": "InfoQ"}
    return " ".join(fix.get(w.lower(), w.capitalize()) for w in s.split()) or "來源"


def tier_label(t):
    return {1: "一手權威", 2: "次級來源", 3: "社群 / 聚合"}.get(int(t) if t else 0, "來源")


def ev_href(prefix, slug):
    return f"{prefix}events/{esc(slug)}/"


# ─────────────────────────── CSS ───────────────────────────
CSS = """
:root{
  --canvas:#080a0f;--surface:#10141d;--surface-2:#151b26;--surface-soft:#0c1017;
  --text:#f2f1ec;--muted:#9aa3b2;--quiet:#697383;--border:#29313e;--border-soft:#1b222d;
  --accent:#ad91ff;--accent-strong:#8f6dff;
  --fact:#4ee4ba;--analysis:#9b8cff;--forecast:#f2bf62;--impact:#ff8b6b;--danger:#ff766c;--blue:#6fb1ff;
  --radius-sm:9px;--radius-md:15px;--radius-lg:23px;--shell:1120px;
  --font:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang TC","Noto Sans TC","Microsoft JhengHei",Arial,sans-serif;
  --mono:ui-monospace,"SFMono-Regular","Cascadia Code","Roboto Mono",Menlo,Consolas,monospace;
  color-scheme:dark;
}
@media(prefers-color-scheme:light){:root:not([data-theme]){
  --canvas:#eeece5;--surface:#fbfaf6;--surface-2:#fff;--surface-soft:#e7e3da;
  --text:#15171c;--muted:#5e6875;--quiet:#858b90;--border:#c9c4ba;--border-soft:#ddd8cf;
  --accent:#6550b7;--accent-strong:#51399f;--fact:#087e70;--analysis:#6550b7;--forecast:#94610d;--impact:#bd4b34;--danger:#b53f39;--blue:#2f6bbf;
  color-scheme:light;
}}
:root[data-theme=light]{
  --canvas:#eeece5;--surface:#fbfaf6;--surface-2:#fff;--surface-soft:#e7e3da;
  --text:#15171c;--muted:#5e6875;--quiet:#858b90;--border:#c9c4ba;--border-soft:#ddd8cf;
  --accent:#6550b7;--accent-strong:#51399f;--fact:#087e70;--analysis:#6550b7;--forecast:#94610d;--impact:#bd4b34;--danger:#b53f39;--blue:#2f6bbf;
  color-scheme:light;
}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--canvas);color:var(--text);font-family:var(--font);line-height:1.72;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit;text-decoration:none}
.ic{width:1em;height:1em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;vertical-align:-.12em}
.shell{width:min(var(--shell),calc(100% - 44px));margin-inline:auto}
.kicker{display:inline-block;color:var(--fact);font:10px var(--mono);letter-spacing:.18em;margin:0 0 12px}

.topbar{position:sticky;z-index:70;top:0;display:flex;align-items:center;gap:20px;height:64px;padding-inline:22px;border-bottom:1px solid var(--border-soft);background:color-mix(in srgb,var(--canvas) 85%,transparent);backdrop-filter:blur(22px) saturate(1.3)}
.brand{display:flex;align-items:center;gap:11px}
.brand-mark{display:flex;align-items:center;justify-content:center;gap:2px;width:34px;height:34px;border:1px solid var(--border);border-radius:50%;background:var(--surface-soft)}
.brand-mark i{width:3px;border-radius:3px;background:var(--accent)}
.brand-mark i:nth-child(1){height:8px}.brand-mark i:nth-child(2){height:17px}.brand-mark i:nth-child(3){height:11px}
.brand strong{display:block;font-size:12px;letter-spacing:.16em}
.brand small{display:block;color:var(--muted);font:9px/1.4 var(--mono);letter-spacing:.03em}
.desktop-nav{display:flex;gap:24px;margin-left:14px}
.desktop-nav a{position:relative;display:flex;align-items:center;min-height:44px;color:var(--muted);font-size:13px;transition:color .15s}
.desktop-nav a:hover,.desktop-nav a[aria-current=page]{color:var(--text)}
.desktop-nav a[aria-current=page]::after{position:absolute;right:0;bottom:14px;left:0;height:2px;background:var(--accent);content:""}
.top-actions{margin-left:auto;display:flex;align-items:center;gap:10px}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;font-size:16px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);cursor:pointer}
.icon-btn:hover{color:var(--text);border-color:var(--accent)}
.gh{display:inline-flex;align-items:center;gap:7px;height:38px;padding:0 14px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);font:11px var(--mono);letter-spacing:.05em}
.gh:hover{color:var(--text);border-color:var(--accent)}

.hero{padding:clamp(46px,6vw,78px) 0 clamp(28px,4vw,40px);border-bottom:1px solid var(--border-soft)}
.hero.compact{padding:clamp(38px,5vw,58px) 0 clamp(22px,3vw,32px)}
.hero h1{font-size:clamp(2rem,5vw,3rem);line-height:1.05;letter-spacing:-.02em;margin:0 0 .5rem;font-weight:680}
.hero p{color:var(--muted);font-size:1.06rem;max-width:60ch;margin:.2rem 0 0}
.statline{display:flex;flex-wrap:wrap;gap:22px;margin-top:24px;color:var(--quiet);font:11px var(--mono);letter-spacing:.05em}
.statline b{color:var(--text);font-weight:600}
/* masthead — 極簡刊頭（靠左，與內文共用同一條左軸）*/
.masthead{padding:clamp(56px,9vw,116px) 0 clamp(30px,5vw,52px);border-bottom:1px solid var(--border-soft)}
.mh-rule{border:0;height:1px;background:var(--border-soft);margin:0}
.mh-eyebrow{display:block;color:var(--fact);font:10px var(--mono);letter-spacing:.3em;margin:clamp(30px,4vw,48px) 0 clamp(18px,2.5vw,28px)}
.mh-title{font-size:clamp(2.3rem,6.5vw,4.6rem);line-height:1.02;letter-spacing:-.03em;font-weight:720;margin:0;max-width:20ch;text-wrap:balance}
.mh-sub{color:var(--muted);font:13px/1.7 var(--mono);letter-spacing:.05em;margin:clamp(22px,3vw,34px) 0 clamp(30px,4vw,48px);max-width:64ch}
.mh-meta{color:var(--quiet);font:11px var(--mono);letter-spacing:.06em;margin:clamp(20px,3vw,30px) 0 0}
.mh-meta b{color:var(--text);font-weight:600}
.empty-lines{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.empty-line{font:11px var(--mono);letter-spacing:.05em;color:var(--quiet);border:1px solid var(--border-soft);border-left:3px solid var(--tc,var(--border));border-radius:7px;padding:6px 12px}

.section{padding:clamp(34px,5vw,56px) 0}
.section-tint{background:var(--surface-soft);border-block:1px solid var(--border-soft)}
.section-head{margin:0 0 22px}
.section-head .kicker{color:var(--muted)}
.section-head h2{font-size:clamp(1.3rem,2.6vw,1.7rem);letter-spacing:-.01em;margin:.1rem 0 .3rem;font-weight:640}
.section-head p{color:var(--muted);margin:.2rem 0 0;max-width:64ch}
.text-link{display:inline-flex;align-items:center;gap:6px;margin-top:20px;color:var(--accent);font:12px var(--mono);letter-spacing:.05em}
.text-link:hover{text-decoration:underline}

article.event{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:clamp(20px,3vw,28px);margin-bottom:16px;transition:border-color .16s,transform .16s}
article.event:hover{border-color:var(--border);transform:translateY(-1px)}
.chips{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:11px}
.chip{font:10px var(--mono);letter-spacing:.06em;padding:4px 9px;border-radius:999px;border:1px solid var(--border-soft);background:var(--surface-soft);color:var(--muted)}
.chip.co{color:var(--text);border-color:var(--border);font-weight:600}
.chip.warn{color:var(--forecast);border-color:color-mix(in srgb,var(--forecast) 45%,var(--border));background:color-mix(in srgb,var(--forecast) 8%,transparent)}
.chip.track{color:var(--tc,var(--muted));border-color:color-mix(in srgb,var(--tc,var(--border)) 40%,var(--border))}
article.event h2{font-size:clamp(1.2rem,2.4vw,1.5rem);line-height:1.34;letter-spacing:-.01em;margin:.1rem 0 .5rem;font-weight:640}
article.event h2 a:hover{color:var(--accent)}
.lead{color:var(--muted);font-size:1.01rem;margin:0}
.layers{margin-top:18px;display:flex;flex-direction:column;gap:14px}
.layer .lbl{font:10px var(--mono);letter-spacing:.1em}
.layer p{margin:6px 0 0;font-size:.98rem}
.layer.fact .lbl{color:var(--fact)}.layer.analysis .lbl{color:var(--analysis)}.layer.impact .lbl{color:var(--impact)}
.layer.accent .lbl{color:var(--accent)}.layer.forecast .lbl{color:var(--forecast)}
.layer.block{padding:14px 17px;border-radius:var(--radius-sm);background:var(--surface-soft)}
.layer.block.fact{border-left:3px solid var(--fact)}.layer.block.accent{border-left:3px solid var(--accent)}
.ev{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:20px 0 0;padding:0;list-style:none;color:var(--quiet);font:11px var(--mono)}
.ev .lbl{color:var(--muted)}
.ev a{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border-radius:7px;border:1px solid color-mix(in srgb,var(--fact) 34%,var(--border));color:var(--fact);background:color-mix(in srgb,var(--fact) 6%,var(--surface-soft));word-break:break-all}
.ev a:hover{border-color:var(--fact)}
.score{margin:14px 0 0;color:var(--quiet);font:11px var(--mono);letter-spacing:.05em;font-variant-numeric:tabular-nums;display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.score b{color:var(--text)}
.detail-link{margin-left:auto;color:var(--accent)}

.rows{display:flex;flex-direction:column;gap:2px}
.row{display:grid;grid-template-columns:96px 1fr auto;gap:16px;align-items:baseline;padding:14px 8px;border-bottom:1px solid var(--border-soft)}
.row:hover{background:var(--surface-soft)}
.row time{color:var(--quiet);font:11px var(--mono)}
.row .rt{font-size:1rem;font-weight:560;line-height:1.4}
/* 原文永遠印在中文下面一行：譯文是二手的，讀者要能看到一手的那句。 */
.row .rt-src{font-size:.82rem;font-weight:400;line-height:1.35;opacity:.62;margin-top:.15rem}
.title-src{font-size:.9rem;opacity:.6;margin:.25rem 0 0;font-weight:400}
.row .rm{color:var(--muted);font:10px var(--mono);letter-spacing:.05em;white-space:nowrap}

.line-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.line-block{background:var(--surface);border:1px solid var(--border-soft);border-top:3px solid var(--tc,var(--accent));border-radius:var(--radius-md);padding:20px 22px}
.line-block h3{font-size:1.12rem;margin:.1rem 0 .3rem;letter-spacing:-.01em}
.line-block .lc{color:var(--quiet);font:10px var(--mono);letter-spacing:.06em}
.line-block ul{margin:14px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:9px}
.line-block li{font-size:.93rem;line-height:1.45;color:var(--muted);display:flex;gap:9px}
.line-block li time{flex:none;color:var(--quiet);font:10px var(--mono)}
.line-block li b{color:var(--text);font-weight:520}
.line-empty{color:var(--quiet);font-size:.9rem;margin-top:12px}
.line-section h2{display:flex;align-items:center;gap:10px;font-size:1.3rem;margin:0 0 4px}
.line-section h2::before{content:"";width:12px;height:12px;border-radius:3px;background:var(--tc,var(--accent))}
.line-meta{color:var(--quiet);font:11px var(--mono);letter-spacing:.05em;margin:0 0 18px}
.line-thesis{color:var(--muted);font-size:.9rem;line-height:1.6;margin:10px 0 0;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.narrative{background:var(--surface);border:1px solid var(--border-soft);border-left:3px solid var(--tc,var(--accent));border-radius:var(--radius-md);padding:20px 24px;margin:0 0 18px}
.narrative .thesis{font-size:1.08rem;line-height:1.7;margin:0;color:var(--text)}
.narrative .nn{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:16px}
@media(max-width:640px){.narrative .nn{grid-template-columns:1fr}}
.narrative .nn .lbl{display:block;font:9px var(--mono);letter-spacing:.12em;color:var(--tc,var(--accent));margin-bottom:5px}
.narrative .nn p{margin:0;font-size:.95rem;color:var(--muted);line-height:1.65}
.lens-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:0 0 22px}
.lens{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:18px 20px}
.lens-role{display:inline-block;font:9px var(--mono);letter-spacing:.1em;color:var(--tc,var(--accent));border:1px solid color-mix(in srgb,var(--tc,var(--accent)) 40%,var(--border));border-radius:999px;padding:3px 9px;margin-bottom:11px}
.lens-q{font-size:.98rem;font-weight:580;line-height:1.45;margin:0 0 8px}
.lens-a{font-size:.9rem;color:var(--muted);line-height:1.6;margin:0 0 10px}
.lens-w{font:10px var(--mono);color:var(--quiet);line-height:1.55;margin:0;display:flex;gap:6px}
.lens-w span{color:var(--tc,var(--accent));flex:none}
.line-sub{font:11px var(--mono);letter-spacing:.1em;color:var(--muted);margin:4px 0 14px;text-transform:uppercase}

.tl-controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 26px}
.chip-row{display:flex;flex-wrap:wrap;gap:7px}
.chip-row button{font:11px var(--mono);letter-spacing:.04em;padding:6px 12px;border-radius:999px;border:1px solid var(--border-soft);background:var(--surface);color:var(--muted);cursor:pointer}
.chip-row button:hover{color:var(--text)}
.chip-row button.active{color:var(--canvas);background:var(--accent);border-color:var(--accent)}
.tl-count{margin-left:auto;color:var(--quiet);font:11px var(--mono)}
.tl-year{margin-bottom:30px}
.tl-year>h2{font:12px var(--mono);letter-spacing:.14em;color:var(--muted);margin:0 0 6px}
.tl-month{margin:0 0 20px;padding-left:20px;border-left:1px solid var(--border-soft)}
.tl-month>time{display:block;font:11px var(--mono);letter-spacing:.08em;color:var(--forecast);margin:0 0 12px}
.tl-card{position:relative;background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-sm);padding:15px 18px;margin-bottom:10px}
.tl-card::before{content:"";position:absolute;left:-25px;top:20px;width:9px;height:9px;border-radius:50%;background:var(--tc,var(--accent));box-shadow:0 0 0 4px color-mix(in srgb,var(--tc,var(--accent)) 14%,transparent)}
.tl-card time{color:var(--quiet);font:10px var(--mono)}
.tl-card h3{font-size:1.02rem;line-height:1.4;margin:5px 0 5px;font-weight:560}
.tl-card h3 a:hover{color:var(--accent)}
.tl-card p{color:var(--muted);font-size:.92rem;margin:0}
.tl-card .tl-meta{margin-top:9px;display:flex;flex-wrap:wrap;gap:10px;color:var(--quiet);font:10px var(--mono);letter-spacing:.04em}
.tl-hide{display:none!important}

.sig-stream{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.sig-card{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:18px 20px;transition:border-color .16s,transform .16s}
.sig-card:hover{border-color:var(--border);transform:translateY(-1px)}
.sig-card.research{border-left:3px solid var(--analysis)}
.sig-card.high{border-left:3px solid var(--fact)}
.sig-meta{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:9px}
.sig-tags{display:flex;flex-wrap:wrap;gap:6px}
.sig-tag{font:9px var(--mono);letter-spacing:.05em;padding:3px 7px;border-radius:6px;background:var(--surface-soft);color:var(--muted);border:1px solid var(--border-soft)}
.sig-card time{color:var(--quiet);font:10px var(--mono);white-space:nowrap}
.sig-card h2{font-size:1.02rem;line-height:1.4;margin:2px 0 6px;font-weight:560}
.sig-card p{color:var(--muted);font-size:.9rem;margin:0 0 12px;flex:1}
.sig-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;color:var(--quiet);font:10px var(--mono);letter-spacing:.04em;border-top:1px solid var(--border-soft);padding-top:10px}
.sig-foot .go{color:var(--fact);display:inline-flex;align-items:center;gap:4px}

/* page-status strip + signal toolbar */
.page-status{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin-top:26px;border:1px solid var(--border-soft);border-radius:var(--radius-md);overflow:hidden;background:var(--border-soft)}
.page-status div{background:var(--canvas);padding:14px 16px}
.page-status span{display:block;color:var(--quiet);font:9px var(--mono);letter-spacing:.1em;margin-bottom:4px}
.page-status b{font-size:1.15rem;font-weight:620;font-variant-numeric:tabular-nums}
@media(max-width:560px){.page-status{grid-template-columns:1fr}}
.sig-toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 22px}
.sig-search{display:flex;align-items:center;gap:8px;flex:1;min-width:220px;padding:0 14px;height:40px;border:1px solid var(--border-soft);border-radius:999px;background:var(--surface);color:var(--quiet)}
.sig-search input{flex:1;border:0;background:transparent;color:var(--text);font-size:13px;outline:none}
.sig-select{position:relative}
.sig-select select{appearance:none;-webkit-appearance:none;height:40px;padding:0 32px 0 14px;border:1px solid var(--border-soft);border-radius:999px;background:var(--surface);color:var(--muted);font:12px var(--mono);cursor:pointer}
.sig-select::after{content:"▾";position:absolute;right:13px;top:11px;color:var(--quiet);pointer-events:none}
.sig-count{margin-left:auto;color:var(--quiet);font:11px var(--mono)}
.sig-more{margin:24px auto 0;display:block;padding:9px 22px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);font:12px var(--mono);cursor:pointer}
.sig-more:hover{color:var(--text);border-color:var(--accent)}
.sig-none{display:none;color:var(--quiet);font:12px var(--mono);text-align:center;padding:36px}

/* ── event detail ── */
.crumb{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font:11px var(--mono);letter-spacing:.05em;margin-bottom:16px}
.crumb:hover{color:var(--text)}
.detail-grid{display:grid;grid-template-columns:1fr 320px;gap:28px;align-items:start}
@media(max-width:820px){.detail-grid{grid-template-columns:1fr}}
.detail-main h2,.detail-aside h3{font-size:.8rem;font:700 12px var(--mono);letter-spacing:.12em;color:var(--muted);margin:0 0 16px;text-transform:uppercase}
.detail-block{margin-bottom:34px}
.jn-note{color:var(--muted);font-size:.88rem;line-height:1.6;margin:0 0 14px;padding:9px 12px;border-left:2px solid var(--border-soft);background:color-mix(in srgb,var(--quiet) 6%,transparent)}
.journey{list-style:none;margin:0;padding:0 0 0 6px}
.journey li{position:relative;padding:0 0 20px 24px;border-left:2px solid var(--border-soft)}
.journey li:last-child{border-left-color:transparent;padding-bottom:0}
.journey li::before{content:"";position:absolute;left:-7px;top:2px;width:12px;height:12px;border-radius:50%;background:var(--dc,var(--accent));box-shadow:0 0 0 4px color-mix(in srgb,var(--dc,var(--accent)) 16%,transparent)}
.jn-head{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.jn-type{font:9px var(--mono);letter-spacing:.08em;padding:2px 7px;border-radius:5px;color:var(--dc,var(--accent));border:1px solid color-mix(in srgb,var(--dc,var(--accent)) 40%,var(--border))}
.jn-head time{color:var(--quiet);font:10px var(--mono)}
.journey b{display:block;font-size:.98rem;font-weight:540;line-height:1.45;margin:6px 0 2px}
.journey small{color:var(--muted);font:10px var(--mono);letter-spacing:.04em}
.journey a.jn-open{color:var(--fact)}
.aside-box{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:20px}
.score-hero{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px}
.score-hero .sh{background:var(--surface-soft);border-radius:var(--radius-sm);padding:12px 14px}
.score-hero .sh span{display:block;color:var(--quiet);font:9px var(--mono);letter-spacing:.08em}
.score-hero .sh b{font-size:1.5rem;font-weight:660;font-variant-numeric:tabular-nums}
.factors{display:flex;flex-direction:column;gap:9px}
.factor{display:grid;grid-template-columns:74px 1fr 30px;gap:9px;align-items:center;font:10px var(--mono);color:var(--muted)}
.factor .bar{height:5px;border-radius:3px;background:var(--border-soft);overflow:hidden}
.factor .bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.factor b{color:var(--text);text-align:right;font-variant-numeric:tabular-nums}
.warnbox{margin-top:14px;padding:11px 13px;border-radius:var(--radius-sm);border:1px solid color-mix(in srgb,var(--forecast) 40%,var(--border));background:color-mix(in srgb,var(--forecast) 7%,transparent);color:var(--forecast);font:10px var(--mono);line-height:1.6}

.site-footer{border-top:1px solid var(--border-soft);background:var(--surface-soft);margin-top:20px}
.footer-grid{display:grid;grid-template-columns:1.4fr 1fr;gap:28px;padding:40px 0 26px}
.footer-brand strong{display:block;font-size:12px;letter-spacing:.16em;margin-bottom:8px}
.footer-brand p{color:var(--muted);font-size:.92rem;margin:0;max-width:44ch}
.footer-links{display:flex;gap:44px;justify-content:flex-end}
.footer-links nav{display:flex;flex-direction:column;gap:9px}
.footer-links span{color:var(--quiet);font:10px var(--mono);letter-spacing:.1em;margin-bottom:2px}
.footer-links a{color:var(--muted);font-size:.9rem}.footer-links a:hover{color:var(--text)}
.footer-meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;padding:16px 0 40px;border-top:1px solid var(--border-soft);color:var(--quiet);font:11px var(--mono);letter-spacing:.04em}
.mobile-nav{position:fixed;z-index:80;bottom:0;left:0;right:0;display:none;justify-content:space-around;background:color-mix(in srgb,var(--canvas) 92%,transparent);backdrop-filter:blur(20px);border-top:1px solid var(--border-soft)}
.mobile-nav a{display:flex;flex-direction:column;align-items:center;gap:3px;padding:9px 0;color:var(--quiet);font:9px var(--mono);letter-spacing:.05em;flex:1}
.mobile-nav a[aria-current=page]{color:var(--accent)}
@media(max-width:720px){.desktop-nav{display:none}.mobile-nav{display:flex}body{padding-bottom:58px}.row{grid-template-columns:1fr;gap:4px}.row .rm{white-space:normal}}
"""

JS = """
(function(){
  var root=document.documentElement;
  var btn=document.querySelector('[data-theme-toggle]');
  if(btn){btn.addEventListener('click',function(){
    var cur=root.getAttribute('data-theme');
    var next=cur==='light'?'dark':(cur==='dark'?'light':(matchMedia('(prefers-color-scheme: light)').matches?'dark':'light'));
    root.setAttribute('data-theme',next);
  });}
  var row=document.querySelector('[data-filter-row]');
  if(row){var cards=[].slice.call(document.querySelectorAll('[data-track]'));
    row.addEventListener('click',function(e){
      var b=e.target.closest('button[data-filter]');if(!b)return;
      row.querySelectorAll('button').forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');var f=b.getAttribute('data-filter');
      var n=0;cards.forEach(function(c){var ok=f==='all'||c.getAttribute('data-track')===f;
        c.classList.toggle('tl-hide',!ok);if(ok)n++;});
      var cnt=document.querySelector('[data-count]');if(cnt)cnt.textContent=n+' 則事件';
    });
  }
  // signals 搜尋 / 來源類型 / 地域篩選 + 分頁（漸進增強：無 JS 時前 36 條照顯示）
  var sb=document.querySelector('[data-sig]');
  if(sb){
    var scards=[].slice.call(sb.querySelectorAll('.sig-card'));
    var q=sb.querySelector('[data-sig-q]'),kind=sb.querySelector('[data-sig-kind]'),region=sb.querySelector('[data-sig-region]');
    var moreBtn=sb.querySelector('[data-sig-more]'),countEl=sb.querySelector('[data-sig-count]'),noneEl=sb.querySelector('[data-sig-none]');
    var CAP=36,expanded=false;
    function apply(){
      var term=(q&&q.value||'').trim().toLowerCase(),k=kind?kind.value:'all',r=region?region.value:'all';
      var active=term||k!=='all'||r!=='all';
      var matched=scards.filter(function(c){
        if(k!=='all'&&c.getAttribute('data-kind')!==k)return false;
        if(r!=='all'&&c.getAttribute('data-region')!==r)return false;
        if(term&&c.getAttribute('data-s').indexOf(term)<0)return false;
        return true;
      });
      scards.forEach(function(c){c.style.display='none';});
      matched.forEach(function(c,i){if(active||expanded||i<CAP)c.style.display='';});
      if(countEl)countEl.textContent=matched.length+' / '+scards.length;
      if(noneEl)noneEl.style.display=matched.length?'none':'block';
      if(moreBtn)moreBtn.style.display=(!active&&!expanded&&matched.length>CAP)?'block':'none';
    }
    [q,kind,region].forEach(function(el){if(el){el.addEventListener('input',apply);el.addEventListener('change',apply);}});
    if(moreBtn)moreBtn.addEventListener('click',function(){expanded=true;apply();});
    apply();
  }
})();
"""


# ─────────────────────── shared layout ───────────────────────
def page_layout(active, title, desc, body, depth, generated):
    prefix = "" if depth == 0 else "../" * depth
    CUR = ' aria-current="page"'

    def _nav():
        return "".join('<a href="' + prefix + r + '"' + (CUR if k == active else "") + '>' + esc(lbl) + '</a>'
                       for k, lbl, r in NAV)
    nav = _nav()
    foot_links = "".join(f'<a href="{prefix}{r}">{esc(lbl)}</a>' for k, lbl, r in NAV)
    return f"""<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="color-scheme" content="dark light"><meta name="theme-color" content="#080a0f">
<link rel="stylesheet" href="{prefix}assets/app.css">
<script defer src="{prefix}assets/app.js"></script>
</head><body data-page="{active}">
<header class="topbar">
<a class="brand" href="{prefix}" aria-label="AI Pulse 首頁">{BRAND}<span><strong>AI PULSE</strong><small>0 LLM 判斷 · 去 AI 口吻</small></span></a>
<nav class="desktop-nav" aria-label="主導覽">{nav}</nav>
<div class="top-actions">
<button class="icon-btn" data-theme-toggle type="button" aria-label="切換淺／深色">{SUN}</button>
<a class="gh" href="https://github.com/Vincenthsiehisme/ai-pulse" target="_blank" rel="noopener">GitHub</a>
</div></header>
<main id="main">{body}</main>
<footer class="site-footer"><div class="shell footer-grid">
<div class="footer-brand"><strong>AI PULSE</strong><p>去 AI 口吻的 AI 產業情報。判斷這一層零 LLM、走規則；敘述由 Cowork 依 speak-human-tw 潤稿。全程可審計、可重現、零 API 成本。</p></div>
<div class="footer-links"><nav><span>探索</span>{foot_links}</nav></div>
</div><div class="shell footer-meta">
<span>判斷走規則 · 敘述去 AI 口吻 · 同 vault → 同輸出</span><span>全站日期為{esc(TZ_LABEL)} · 更新於 {esc(generated)}</span>
</div></footer>
<nav class="mobile-nav" aria-label="主導覽">{nav}</nav>
</body></html>"""


def hero(kicker, h1, p, extra="", cls=""):
    return (f'<section class="hero {cls} shell"><div><span class="kicker">{esc(kicker)}</span>'
            f'<h1>{h1}</h1><p>{esc(p)}</p>{extra}</div></section>')


def section_head(kicker, title, desc=""):
    d = f"<p>{esc(desc)}</p>" if desc else ""
    return (f'<div class="section-head"><span class="kicker">{esc(kicker)}</span>'
            f'<h2>{esc(title)}</h2>{d}</div>')


def page_status(cells):
    inner = "".join(f'<div><span>{esc(l)}</span><b>{esc(v)}</b></div>' for l, v in cells)
    return f'<div class="page-status">{inner}</div>'


SIG_KINDS = [("all", "全部來源"), ("official", "官方 / 政策"), ("research", "研究 / 專家"),
             ("media", "媒體 / 社群"), ("aggregator", "聚合")]


def signal_kind(s, sources):
    src = sources.get(s.get("source_id")) or {}
    cat = (src.get("source_category") or "").lower()
    role = (s.get("effective_role") or "").lower()
    sid = str(s.get("source_id") or "").lower()
    if cat == "aggregator" or src.get("track") == "aggregator":
        return "aggregator"
    if cat == "research" or "research" in role or "arxiv" in sid:
        return "research"
    if cat in ("vendor", "official", "policy") or src.get("track") == "official":
        return "official"
    return "media"


def signal_region(s, sources):
    return (sources.get(s.get("source_id")) or {}).get("region") or "global"


def narrative_block(narr):
    thesis = (narr or {}).get("thesis")
    if not thesis:
        return ""
    now = (narr or {}).get("now")
    nxt = (narr or {}).get("next")
    nn = ""
    if now or nxt:
        cells = ""
        if now:
            cells += f'<div><span class="lbl">現況 NOW</span><p>{esc(now)}</p></div>'
        if nxt:
            cells += f'<div><span class="lbl">接下來看 NEXT</span><p>{esc(nxt)}</p></div>'
        nn = f'<div class="nn">{cells}</div>'
    return f'<div class="narrative"><p class="thesis">{esc(thesis)}</p>{nn}</div>'


def lens_grid(lenses):
    if not lenses:
        return ""
    cards = []
    for L in lenses:
        watch = f'<p class="lens-w"><span>觀察</span>{esc(L.get("watch"))}</p>' if L.get("watch") else ""
        cards.append(f"""<article class="lens"><span class="lens-role">{esc(L.get("role"))}</span>
<p class="lens-q">{esc(L.get("question"))}</p><p class="lens-a">{esc(L.get("answer"))}</p>{watch}</article>""")
    return f'<div class="lens-grid">{"".join(cards)}</div>'


def track_of(ev):
    name = TRACK_ALIASES.get((ev.get("track") or "").strip())
    return TRACK_BY_NAME.get(name) if name else None


# ─────────────────────── components ───────────────────────
def layer_html(heading, text):
    cls, label, block = LAYER_META[heading]
    b = " block" if block else ""
    return (f'<div class="layer {cls}{b}"><span class="lbl">{esc(label)} · {esc(heading)}</span>'
            f'<p>{esc(text)}</p></div>')


def event_chips(ev):
    chips = [f'<span class="chip co">{esc(ev["company"])}</span>']
    if ev["category"]:
        chips.append(f'<span class="chip">{esc(CAT_LABEL.get(ev["category"], ev["category"]))}</span>')
    tr = track_of(ev)
    if tr:
        chips.append(f'<span class="chip track" style="--tc:{tr[2]}">{esc(tr[1])}</span>')
    if (ev["independent"] or 0) < 2:
        chips.append('<span class="chip warn">待證實</span>')
    return "".join(chips)


def event_card(ev, prefix, full=True):
    href = ev_href(prefix, ev["slug"])
    layers = "".join(layer_html(h, ev["layers"][h]) for h in LAYERS if ev["layers"].get(h)) if full else ""
    ev_links = "".join(f'<a href="{esc(u)}" rel="noopener" target="_blank">{esc(sid)} {EXT}</a>'
                       for sid, u in ev["evidence"] if u)
    ev_block = f'<ul class="ev"><span class="lbl">證據</span>{ev_links}</ul>' if (ev_links and full) else ""
    tr = track_of(ev)
    track_span = f'<span>{esc(tr[1])}</span>' if tr else ""
    return f"""<article class="event">
<div class="chips">{event_chips(ev)}</div>
<h2><a href="{href}">{esc(ev.get('title_zh') or ev['title'])}</a></h2>
{f'<p class="title-src">{esc(ev["title"])}</p>' if ev.get('title_zh') else ''}
<p class="lead">{esc(ev['summary'])}</p>
{('<div class="layers">' + layers + '</div>') if layers else ''}
{ev_block}
<div class="score"><span>confidence <b>{esc(ev['confidence'])}</b></span><span>heat <b>{esc(heat_text(ev['heat']))}</b></span>{track_span}<a class="detail-link" href="{href}">看完整事件 {ARROW}</a></div>
</article>"""


def title_html(ev, cls_zh="rt", cls_src="rt-src"):
    """事件標題的 HTML：**中文在上、原文在下**，沒有中文就只有原文。

    原文永遠留著，跟榜單描述同一條規矩：譯文是二手的，讀者要能看到一手的那句
    （紅線 2 的延伸）。這不是版面潔癖——標題是最容易被翻歪的一句，而讀者無法
    從一句中文回推它翻自什麼。
    """
    zh = (ev.get("title_zh") or "").strip()
    src = esc(ev.get("title") or "")
    if not zh:
        return f'<div class="{cls_zh}">{src}</div>'
    return (f'<div class="{cls_zh}">{esc(zh)}</div>'
            f'<div class="{cls_src}">{src}</div>')


def recent_row(ev, prefix):
    tr = track_of(ev)
    meta = tr[1] if tr else (ev["company"] or "")
    href = ev_href(prefix, ev["slug"])
    return (f'<a class="row" href="{href}"><time>{esc(ev["date_display"])}</time>'
            + title_html(ev)
            + f'<div class="rm">{esc(ev["company"])} · {esc(meta)}</div></a>')


# ─────────────────────── journey + score grid ───────────────────────
#: 證據區塊的標題與說明，由 coverage 與證據筆數決定。
#: 規格見 references/event-timestamps.md〈第三個現場：呈現層〉。
JOURNEY_HEADING = "發展歷程"
EVIDENCE_HEADING = "證據"
COVERAGE_NOTE = {
    "backfilled": "這些證據是首抓時撈回的存量——事情發生時，我們還沒有在看。",
    # 「確定是回填」跟「不知道」是兩件事，所以不共用同一句。共用的話，
    # 讀者會把「我們沒紀錄」讀成「我們確定沒在看」，那是把不知道講成知道。
    "unknown": "這則的來源何時開始被抓取，我們沒有紀錄。",
}
#: 語料裡查不到時印這個，**不得**退回來源名或事件日。跟 HEAT_UNMEASURED 同一條規矩：
#: 印一個看起來合理的值，會被讀成「這就是那筆證據的標題／日期」。
TITLE_UNKEPT = "標題未留存"
DATE_UNKEPT = "日期未留存"


def journey_shape(coverage, n_items):
    """→ (區塊標題, 說明句 or None, 第一項要不要標「起點」)。

    「起點」是一個關於**世界**的宣稱（這件事從這裡開始），所以只在我們真的能主張
    它的時候才印。修正前的判準是 `if is_first`——那是關於**我們資料排序位置**的
    事實，而 2026-07-27 實測 36 則已發布事件裡有 32 則只有一筆證據：那個「第一」
    同時也是「唯一」，卻被標成起點。
    """
    if n_items <= 1 or coverage != "observed":
        return EVIDENCE_HEADING, COVERAGE_NOTE.get(coverage), False
    return JOURNEY_HEADING, None, True


def classify_dev(sid, sources, is_first):
    if is_first:
        return "origin"
    s = sources.get(sid) or {}
    cat = (s.get("source_category") or "").lower()
    tier = s.get("tier")
    if cat in ("vendor", "research") or tier == 1:
        return "official"
    if cat == "aggregator" or (s.get("track") == "aggregator"):
        return "discussion"
    return "response"


def journey_html(ev, corpus_idx, sources):
    """→ (區塊標題, HTML)。標題不是固定字串——見 journey_shape()。"""
    items = []
    for sid, url in ev["evidence"]:
        rec = corpus_idx.get(url) or {}
        # 查不到就說查不到。退回來源名／事件日的話，畫面上會出現一筆「標題是
        # 來源名」的證據，或一整串「全部同一天」的證據——後者尤其傷，因為那正是
        # 讀者用來判斷這件事怎麼發展的唯一線索。
        items.append({"sid": sid, "url": url,
                      "title": rec.get("title") or TITLE_UNKEPT,
                      "date": rec.get("date") or None})
    # 沒有日期的排**最後**，不是排最前。原本是「解不出日期就當 1970」，而 1970
    # 早於任何真實日期——所以一筆我們承認不知道日期的證據會保證排第一，然後拿到
    # 「起點」。日期退路拿掉（不再退回事件日）之後這條路才真的走得到，而它印出來
    # 的那一行是「起點／日期未留存／標題未留存」：一個關於世界的宣稱，貼在一筆
    # 我們承認什麼都不知道的證據上。複合鍵讓缺值永遠贏不過已知值。
    items.sort(key=lambda x: (0 if parse_dt(x["date"]) else 1,
                              parse_dt(x["date"]) or datetime(1970, 1, 1, tzinfo=timezone.utc)))
    heading, note, show_origin = journey_shape(ev.get("coverage"), len(items))
    # 連第一筆的日期都不知道就沒有資格說「起點」——排序位置在這裡不構成主張。
    show_origin = show_origin and bool(items and items[0]["date"])
    if not items:
        return heading, '<p class="line-empty">尚無可展開的證據鏈。</p>'
    lis = []
    for i, it in enumerate(items):
        dt = classify_dev(it["sid"], sources, show_origin and i == 0)
        zh, cls = DEV_LABEL[dt]
        color = {"fact": "var(--fact)", "accent": "var(--accent)",
                 "forecast": "var(--forecast)", "impact": "var(--impact)"}[cls]
        link = (f'<a class="jn-open" href="{esc(it["url"])}" target="_blank" rel="noopener">{esc(prettify_source(it["sid"]))} {EXT}</a>'
                if it["url"] else esc(prettify_source(it["sid"])))
        when = fmt_date(it["date"]) if it["date"] else DATE_UNKEPT
        lis.append(f"""<li style="--dc:{color}"><div class="jn-head"><span class="jn-type">{esc(zh)}</span><time>{esc(when)}</time></div>
<b>{esc(it["title"])}</b><small>{link}</small></li>""")
    note_html = f'<p class="jn-note">{esc(note)}</p>' if note else ""
    return heading, f'{note_html}<ol class="journey">{"".join(lis)}</ol>'


def score_grid_html(ev):
    sf = ev.get("score_factors") or {}
    heroes = [("confidence", ev["confidence"]), ("heat", heat_text(ev["heat"])),
              ("impact", ev.get("impact", 0)), ("value", ev.get("value", 0))]
    hero_html = "".join(f'<div class="sh"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in heroes)
    facs = []
    for key, label, cap in FACTOR_META:
        raw = sf.get(key, 0) or 0
        try:
            pct = max(0, min(100, round(float(raw) / cap * 100)))
        except (TypeError, ValueError):
            pct = 0
        shown = raw if cap != 100 else f"{int(round(float(raw)))}" if isinstance(raw, (int, float)) else raw
        facs.append(f'<div class="factor"><span>{esc(label)}</span><div class="bar"><i style="width:{pct}%"></i></div><b>{esc(shown)}</b></div>')
    warn = ""
    if (ev["independent"] or 0) < 2:
        warn = '<div class="warnbox">單一獨立來源，暫標「待證實」——待跨來源佐證後升級。</div>'
    return f"""<div class="aside-box">
<h3>評分理由</h3>
<div class="score-hero">{hero_html}</div>
<div class="factors">{"".join(facs)}</div>
{warn}</div>"""


# ─────────────────────── pages ───────────────────────
def build_home(events, narratives, generated):
    n = len(events)
    companies = len({e["company"] for e in events if e["company"]})
    hero_html = f"""<section class="masthead"><div class="shell">
<hr class="mh-rule">
<span class="mh-eyebrow">DETERMINISTIC AI INTELLIGENCE</span>
<h1 class="mh-title">看清 AI 產業的關鍵變化</h1>
<p class="mh-sub">判斷走規則、零 LLM · 敘述去 AI 口吻 · 每則附一手證據</p>
<hr class="mh-rule">
<p class="mh-meta"><b>{n}</b> 則已發布　·　<b>{companies}</b> 家主體　·　更新 {esc(generated)}</p>
</div></section>"""
    latest = events[0] if events else None
    latest_html = (f'<section class="section shell">{section_head("LATEST MATERIAL SHIFT", "最新重大變化")}'
                   f'{event_card(latest, "", full=True)}</section>') if latest else ""
    recent = events[1:9]
    recent_html = ""
    if recent:
        rows = "".join(recent_row(e, "") for e in recent)
        recent_html = f"""<section class="section section-tint"><div class="shell">
{section_head("ALSO WORTH KNOWING", "近期變化", "通過門禁、已發布的其餘事件。")}
<div class="rows">{rows}</div>
<a class="text-link" href="timeline/">看完整事件時間軸 {ARROW}</a></div></section>"""
    by_track = defaultdict(list)
    for e in events:
        tr = track_of(e)
        if tr:
            by_track[tr[0]].append(e)
    blocks = []
    for slug, name, color in sorted(TRACKS, key=lambda t: -len(by_track.get(t[0], []))):
        evs = by_track.get(slug, [])
        th = (narratives.get(slug) or {}).get("thesis")
        if th:
            inner = f'<p class="line-thesis">{esc(th)}</p>'
        elif evs:
            inner = "".join(f'<li><time>{esc(e["date_display"])}</time><span><b>{esc(e["company"])}</b> {esc(e["title"])}</span></li>'
                            for e in evs[:2])
            inner = f"<ul>{inner}</ul>"
        else:
            inner = '<p class="line-empty">暫無已發布事件</p>'
        blocks.append(f'<div class="line-block" style="--tc:{color}"><span class="lc">{len(evs)} 則事件</span><h3>{esc(name)}</h3>{inner}</div>')
    lines_html = f"""<section class="section shell">
{section_head("SIX INDUSTRY TRENDS", "六大領域趨勢", "把事件收斂進六條主線，看產業往哪走。")}
<div class="line-grid">{''.join(blocks)}</div>
<a class="text-link" href="lines/">進入領域趨勢 {ARROW}</a></section>"""
    manifesto = ('<section class="section section-tint"><div class="shell">'
                 + section_head("為什麼是這個系統", "一個追蹤 AI 的系統，證明自己不靠 LLM 也能跑",
                                "判斷這一層零 LLM——由規則決定一則消息夠不夠格發、熱度可不可信。"
                                "敘述由 Cowork 依 speak-human-tw 潤稿、去 AI 口吻。全程可審計、可重現、零 API 成本、可離線。")
                 + '</div></section>')
    body = hero_html + latest_html + recent_html + lines_html + manifesto
    return page_layout("home", "AI Pulse — 看清 AI 產業的關鍵變化",
                       "去 AI 口吻的 AI 產業情報：判斷走規則、敘述過 speak-human-tw，每則附一手證據。",
                       body, 0, generated)


def build_lines(events, narratives, generated):
    by_track = defaultdict(list)
    for e in events:
        tr = track_of(e)
        if tr:
            by_track[tr[0]].append(e)
    active_tracks = sum(1 for slug, _, _ in TRACKS if by_track.get(slug))
    latest = events[0]["date_display"] if events else "—"
    stat = page_status([("主線", f"{active_tracks} / 6"), ("已收事件", len(events)), ("最新", latest)])
    h = hero("六大主線", "領域趨勢", "把事件收斂進六條主線——每條看得到相關事件、最新進展與獨立來源數。",
             extra=stat, cls="compact")
    secs = []
    empties = []
    # 有事件的主線在前、依事件數多寡排序；沒事件的收成底部一條 compact strip
    for slug, name, color in sorted(TRACKS, key=lambda t: -len(by_track.get(t[0], []))):
        evs = by_track.get(slug, [])
        if not evs:
            empties.append((slug, name, color))
            continue
        narr = narratives.get(slug) or {}
        cards = "".join(event_card(e, "../", full=False) for e in evs)
        meta = f"{len(evs)} 則事件 · 最新 {evs[0]['date']}"
        secs.append(f"""<section class="section shell line-section" style="--tc:{color}">
<h2>{esc(name)}</h2><p class="line-meta">{esc(meta)}</p>
{narrative_block(narr)}{lens_grid(narr.get("lenses"))}<p class="line-sub">相關事件</p>{cards}</section>""")
    empty_strip = ""
    if empties:
        chips = "".join(f'<span class="empty-line" style="--tc:{c}">{esc(nm)}</span>' for _, nm, c in empties)
        empty_strip = (f'<section class="section shell"><p class="line-sub">尚無已發布事件的主線</p>'
                       f'<div class="empty-lines">{chips}</div></section>')
    body = h + "".join(secs) + empty_strip
    return page_layout("lines", "領域趨勢 — AI Pulse",
                       "六大主線的事件收斂：模型能力、Agent、產品、基礎設施、資本、全球版圖。", body, 1, generated)


def build_timeline(events, generated):
    by_ym = defaultdict(lambda: defaultdict(list))
    for e in events:
        # 用**顯示日**分年月，不是儲存日：卡片上印台北日期、卻按 UTC 日期歸月，
        # 會出現一張寫著 8/01 的卡片躺在「7 月」底下。
        d = e["date_display"] or e["date"] or "0000-00"
        by_ym[d[:4]][d[5:7]].append(e)
    present_tracks = {track_of(e)[0] for e in events if track_of(e)}
    filters = "".join(f'<button type="button" data-filter="{slug}">{esc(name)}</button>'
                      for slug, name, _ in TRACKS if slug in present_tracks)
    MONTH_TW = {f"{i:02d}": f"{i} 月" for i in range(1, 13)}
    years_html = []
    for y in sorted(by_ym, reverse=True):
        months = []
        for m in sorted(by_ym[y], reverse=True):
            cards = []
            for e in by_ym[y][m]:
                tr = track_of(e)
                tc = tr[2] if tr else "var(--accent)"
                tslug = tr[0] if tr else ""
                tname = tr[1] if tr else ""
                href = ev_href("../", e["slug"])
                cards.append(f"""<div class="tl-card" data-track="{esc(tslug)}" style="--tc:{tc}">
<time>{esc(e['date_display'])}</time><h3><a href="{href}">{esc(e['title'])}</a></h3><p>{esc(e['summary'])}</p>
<div class="tl-meta"><span>{esc(e['company'])}</span>{f'<span>{esc(tname)}</span>' if tname else ''}<span>confidence {esc(e['confidence'])}</span></div></div>""")
            months.append(f'<div class="tl-month"><time>{esc(y)} · {MONTH_TW.get(m, m)}</time>{"".join(cards)}</div>')
        years_html.append(f'<section class="tl-year"><h2>{esc(y)}</h2>{"".join(months)}</section>')
    companies = len({e["company"] for e in events if e["company"]})
    latest = events[0]["date_display"] if events else "—"
    tl_stat = page_status([("事件", len(events)), ("主體", companies), ("最新", latest)])
    body = f"""{hero("EVENT TIMELINE", "事件時間軸", "已發布事件依時間排列，最新在前。點主線標籤可篩選、點標題看完整事件。", extra=tl_stat, cls="compact")}
<section class="section shell">
<div class="tl-controls" data-filter-row>
<div class="chip-row"><button type="button" class="active" data-filter="all">全部</button>{filters}</div>
<span class="tl-count" data-count>{len(events)} 則事件</span></div>
<div class="tl-chrono">{''.join(years_html)}</div></section>"""
    return page_layout("timeline", "事件時間軸 — AI Pulse",
                       "已發布 AI 產業事件的時間軸，依年月分組、可依主線篩選。", body, 1, generated)


def build_signals(signals, sources, generated):
    src_count = len({s.get("source_id") for s in signals})
    latest = fmt_date(signals[0].get("published") or signals[0].get("first_observed_at")) if signals else "—"
    regions = sorted({signal_region(s, sources) for s in signals})
    cards = []
    for s in signals:
        url = s.get("url")
        if not url or not str(url).startswith(("http://", "https://")):
            continue
        facet = s.get("facet") or "update"
        tier = s.get("tier")
        grade = s.get("grade") or ""
        role = (s.get("effective_role") or "")
        kind = signal_kind(s, sources)
        region = signal_region(s, sources)
        tone = "research" if (facet in ("benchmark", "paper") or "research" in role
                              or "arxiv" in str(s.get("source_id", "")).lower()) else ("high" if tier == 1 else "")
        date = fmt_date(s.get("published") or s.get("first_observed_at"))
        summ = (s.get("summary") or "").strip()
        if len(summ) > 160:
            summ = summ[:158].rstrip() + "…"
        srcname = prettify_source(s.get("source_id"))
        search = " ".join([s.get("title") or "", srcname, facet, region, kind]).lower()
        cards.append(f"""<a class="sig-card {tone}" href="{esc(url)}" target="_blank" rel="noopener" data-kind="{esc(kind)}" data-region="{esc(region)}" data-s="{esc(search)}">
<div class="sig-meta"><span class="sig-tags"><span class="sig-tag">{esc(facet)}</span><span class="sig-tag">{esc(region)}</span>{f'<span class="sig-tag">{esc(grade)} 級</span>' if grade else ''}</span><time>{esc(date)}</time></div>
<h2>{esc(s.get('title'))}</h2>{f'<p>{esc(summ)}</p>' if summ else ''}
<div class="sig-foot"><span>{esc(srcname)} · {esc(tier_label(tier))}</span><span class="go">看原文 {EXT}</span></div></a>""")
    present_kinds = {signal_kind(s, sources) for s in signals}
    kind_opts = "".join(f'<option value="{esc(k)}">{esc(lbl)}</option>'
                        for k, lbl in SIG_KINDS if k == "all" or k in present_kinds)
    region_opts = '<option value="all">全部地域</option>' + "".join(
        f'<option value="{esc(r)}">{esc(r)}</option>' for r in regions)
    stat = page_status([("已收更新", len(signals)), ("來源", src_count), ("最新", latest)])
    toolbar = f"""<div class="sig-toolbar">
<label class="sig-search">{SEARCH}<input type="search" data-sig-q placeholder="搜尋標題、來源、分類或地域"></label>
<div class="sig-select"><select data-sig-kind aria-label="依來源類型篩選">{kind_opts}</select></div>
<div class="sig-select"><select data-sig-region aria-label="依地域篩選">{region_opts}</select></div>
<span class="sig-count" data-sig-count>{len(cards)} / {len(cards)}</span></div>"""
    body = f"""{hero("SOURCE UPDATES", "來源更新", "各來源剛發布的內容與原文連結。這裡只是待核驗線索，通過證據檢查後才會進入事件時間軸。", extra=stat, cls="compact")}
<section class="section section-tint"><div class="shell" data-sig>
{toolbar}
<div class="sig-stream">{''.join(cards)}</div>
<p class="sig-none" data-sig-none>沒有符合條件的更新。</p>
<button class="sig-more" type="button" data-sig-more>顯示更多</button>
</div></section>"""
    return page_layout("signals", "來源更新 — AI Pulse",
                       "各追蹤來源剛發布的待核驗線索，附原文連結。通過證據檢查後才進入事件時間軸。",
                       body, 1, generated)


def build_event_page(ev, all_events, corpus_idx, sources, generated):
    pfx = "../../"
    tr = track_of(ev)
    layers = "".join(layer_html(h, ev["layers"][h]) for h in LAYERS if ev["layers"].get(h))
    journey_heading, journey = journey_html(ev, corpus_idx, sources)
    scores = score_grid_html(ev)
    ev_links = "".join(f'<a href="{esc(u)}" rel="noopener" target="_blank">{esc(sid)} {EXT}</a>'
                       for sid, u in ev["evidence"] if u)
    ev_block = f'<div class="aside-box" style="margin-top:16px"><h3>證據</h3><ul class="ev">{ev_links}</ul></div>' if ev_links else ""
    # 相關事件：同主線或同公司，排除自己
    rel = [e for e in all_events if e["slug"] != ev["slug"]
           and (track_of(e) == tr and tr is not None or e["company"] == ev["company"])][:4]
    rel_html = ""
    if rel:
        rows = "".join(recent_row(e, pfx) for e in rel)
        rel_html = f'<section class="section shell"><div class="section-head"><span class="kicker">RELATED</span><h2 style="font:640 1.3rem var(--font);letter-spacing:-.01em;color:var(--text);text-transform:none">相關事件</h2></div><div class="rows">{rows}</div></section>'
    body = f"""<section class="hero compact shell"><div>
<a class="crumb" href="{pfx}timeline/">{BACK} 事件時間軸</a>
<div class="chips">{event_chips(ev)}</div>
<h1 style="font-size:clamp(1.6rem,3.4vw,2.3rem)">{esc(ev.get('title_zh') or ev['title'])}</h1>
{f'<p class="title-src">{esc(ev["title"])}</p>' if ev.get('title_zh') else ''}
<p class="lead" style="font-size:1.06rem;margin-top:.6rem">{esc(ev['summary'])}</p>
<div class="statline"><span>{esc(ev['date_display'])}</span>{f'<span>{esc(tr[1])}</span>' if tr else ''}<span>{esc(ev['company'])}</span></div>
</div></section>
<section class="section shell"><div class="detail-grid">
<div class="detail-main">
<div class="detail-block"><h2>{esc(journey_heading)}</h2>{journey}</div>
<div class="detail-block"><h2>六層分析</h2><div class="layers">{layers}</div></div>
</div>
<aside class="detail-aside">{scores}{ev_block}</aside>
</div></section>
{rel_html}"""
    return page_layout("timeline", f"{ev.get('title_zh') or ev['title']} — AI Pulse",
                       ev["summary"] or ev["title"], body, 2, generated)


# ─────────────────────── data loading ───────────────────────
def load_events(vault):
    events = []
    for p in sorted((vault / "Events").glob("*.md")):
        fm, body = parse_note(p.read_text("utf-8"))
        if fm.get("status") != "published":
            continue
        events.append({
            "id": fm.get("id"), "slug": fm.get("slug") or fm.get("id"),
            "title": fm.get("title", ""), "date": str(fm.get("date") or ""),
            # 中文標題只有**綁得上當下這句原文**時才算數；對不上就是 None，
            # 前台退回原文。掛一句在講舊標題的中文，比沒有中文糟得多。
            "title_zh": zhtext.valid_for(
                {"zh": fm.get("title_zh"), "src_hash": fm.get("title_zh_src")},
                fm.get("title", "")),
            "happened": str(fm.get("happened_at") or ""),
            # 儲存的 `date` 是 UTC 日（它進 id，不能動）；`date_display` 是同一個
            # 瞬間的台北日，畫面上只印這個。兩個都留著，才回答得出
            # 「為什麼站上是 7/24、Events/ 檔名卻是 7/23」。
            "date_display": (clock.display_date_str(parse_dt(fm.get("happened_at")))
                             or str(fm.get("date") or "")),
            "company": fm.get("company", ""), "category": fm.get("category") or "",
            "track": fm.get("track") or "", "summary": fm.get("summary") or "",
            # heat 不給預設 0：缺席與「量到 0」是兩件事，見 heat_text()。
            "confidence": fm.get("confidence", 0), "heat": fm.get("heat"),
            "impact": fm.get("impact", 0), "value": fm.get("value", 0),
            "independent": fm.get("independent_sources", 0),
            "score_factors": fm.get("score_factors") or {},
            "layers": {h: section(body, h) for h in LAYERS},
            "evidence": [(e.get("source_id"), e.get("url")) for e in (fm.get("evidence") or [])],
            # 事情發生時我們看不看得到。缺這一格（舊 note 還沒被重寫過）時是 None，
            # 而 journey_shape() 只有在它**正好等於** "observed" 時才印「起點」——
            # 所以缺格會倒向保守那一邊，不會因為欄位還沒長出來就開始亂宣稱。
            "coverage": fm.get("coverage"),
        })
    events.sort(key=lambda x: x["date"], reverse=True)
    return events


def load_signals(vault):
    probe = vault / "_probe"
    days = sorted((p.name for p in probe.iterdir() if p.is_dir()), reverse=True) if probe.exists() else []
    for day in days:
        f = probe / day / "signals-scored.jsonl"
        if f.exists():
            rows = []
            for line in f.read_text("utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            def _key(r):
                d = parse_dt(r.get("published") or r.get("first_observed_at") or "")
                return d.timestamp() if d else 0.0
            rows.sort(key=_key, reverse=True)
            return rows
    return []


def load_corpus_index(vault):
    """建 url -> {title, date, summary, source_id} 索引（給發展歷程解析證據）。"""
    idx = {}
    corpus = vault / "_corpus"
    if not corpus.exists():
        return idx
    for day_dir in sorted(corpus.iterdir()):
        if not day_dir.is_dir():
            continue
        for f in day_dir.glob("*.jsonl"):
            for line in f.read_text("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rec = {"title": r.get("title"),
                       "date": r.get("published") or r.get("first_observed_at"),
                       "summary": r.get("summary"), "source_id": r.get("source_id")}
                for u in (r.get("url"), r.get("url_canonical")):
                    if u and u not in idx:
                        idx[u] = rec
    return idx


def load_sources(vault):
    raw = yaml.safe_load((vault / "_config" / "sources.yaml").read_text("utf-8"))
    out = {}
    for key in SECTIONS:
        for s in (raw.get(key) or []):
            if isinstance(s, dict) and s.get("id"):
                out[s["id"]] = s
    return out


def load_narratives(vault):
    """讀編輯性敘事層（獨立於 pipeline，可缺）。回傳 track_slug -> {thesis,now,next,lenses}。"""
    f = vault / "_config" / "narratives.yaml"
    if not f.exists():
        return {}
    raw = yaml.safe_load(f.read_text("utf-8")) or {}
    return raw.get("tracks") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    out = vault / args.out
    for sub in ("assets", "data", "lines", "timeline", "signals", "events"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    events = load_events(vault)
    signals = load_signals(vault)
    corpus_idx = load_corpus_index(vault)
    sources = load_sources(vault)
    narratives = load_narratives(vault)
    # 頁尾「更新於」是給讀者看的 → 台北並標時區。data/timeline.json 的
    # `generated` 是給機器讀的 → 另外用 utc_stamp()，兩者刻意不同。
    generated = clock.display_stamp()

    (out / "assets" / "app.css").write_text(CSS, encoding="utf-8")
    (out / "assets" / "app.js").write_text(JS, encoding="utf-8")
    (out / "index.html").write_text(build_home(events, narratives, generated), encoding="utf-8")
    (out / "lines" / "index.html").write_text(build_lines(events, narratives, generated), encoding="utf-8")
    (out / "timeline" / "index.html").write_text(build_timeline(events, generated), encoding="utf-8")
    (out / "signals" / "index.html").write_text(build_signals(signals, sources, generated), encoding="utf-8")
    for ev in events:
        d = out / "events" / ev["slug"]
        d.mkdir(parents=True, exist_ok=True)
        d.joinpath("index.html").write_text(
            build_event_page(ev, events, corpus_idx, sources, generated), encoding="utf-8")
    (out / "data" / "timeline.json").write_text(
        json.dumps({"generated": clock.utc_stamp(), "count": len(events),
                    "events": [{k: e[k] for k in ("id", "slug", "title", "date", "company", "category",
                                                  "summary", "confidence", "heat")} for e in events]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pulse-render  published={len(events)}  signals={len(signals)}  events_pages={len(events)}  corpus_idx={len(corpus_idx)}")
    print(f"  → {out}/index.html + lines/ + timeline/ + signals/ + events/<slug>/ + assets/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
