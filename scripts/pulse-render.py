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
from datetime import date as _date, timedelta as _timedelta
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
  /* 字級級距。改版前站上有 24 個字級，其中 11 個擠在 0.8–1.15rem
     之間（.9/.92/.93/.95/.98…）——那不是級距，是噪音：1.01rem 跟 1.02rem
     沒有人看得出差別，但每次改版都要猜該用哪一個，而且 px 與 rem 混用。
     收成九級，比例大約 1.12–1.2。最小級從 9px 抬到 11px：
     9px 的中文與等寬字在一般螢幕上是用猜的不是用讀的，而站上有 27 處在用它。 */
  --fs-micro:.6875rem;--fs-mini:.75rem;--fs-tiny:.8125rem;--fs-sm:.875rem;
  --fs-base:.9375rem;--fs-md:1rem;--fs-lg:1.125rem;--fs-xl:1.375rem;--fs-2xl:1.625rem;
  /* 大標三級也進級距。改版前這四個是散在 CSS 裡的 clamp()：
       .section-head h2  clamp(1.3rem,2.6vw,1.7rem)
       article.event h2  clamp(1.2rem,2.4vw,1.5rem)
     兩者在首頁**上下緊鄰**（區塊標題「這幾則最值得看」＋底下那張卡的標題），
     1200px 視窗下一個 27.2px、一個 24px——看得出來不一樣大，而沒有任何理由
     要不一樣。收成 --fs-h2 一個 token，兩處共用。 */
  --fs-h2:clamp(1.35rem,2.6vw,1.7rem);
  --fs-h1:clamp(2rem,5vw,3rem);
  --fs-display:clamp(2.3rem,6.5vw,4.6rem);
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
.kicker{display:inline-block;color:var(--fact);font:var(--fs-micro) var(--mono);letter-spacing:.18em;margin:0 0 12px}

.topbar{position:sticky;z-index:70;top:0;display:flex;align-items:center;gap:20px;height:64px;padding-inline:22px;border-bottom:1px solid var(--border-soft);background:color-mix(in srgb,var(--canvas) 85%,transparent);backdrop-filter:blur(22px) saturate(1.3)}
.brand{display:flex;align-items:center;gap:11px}
.brand-mark{display:flex;align-items:center;justify-content:center;gap:2px;width:34px;height:34px;border:1px solid var(--border);border-radius:50%;background:var(--surface-soft)}
.brand-mark i{width:3px;border-radius:3px;background:var(--accent)}
.brand-mark i:nth-child(1){height:8px}.brand-mark i:nth-child(2){height:17px}.brand-mark i:nth-child(3){height:11px}
.brand strong{display:block;font-size:var(--fs-mini);letter-spacing:.16em}
.brand small{display:block;color:var(--muted);font:var(--fs-micro)/1.4 var(--mono);letter-spacing:.03em}
.desktop-nav{display:flex;gap:24px;margin-left:14px}
.desktop-nav a{position:relative;display:flex;align-items:center;min-height:44px;color:var(--muted);font-size:var(--fs-tiny);transition:color .15s}
.desktop-nav a:hover,.desktop-nav a[aria-current=page]{color:var(--text)}
.desktop-nav a[aria-current=page]::after{position:absolute;right:0;bottom:14px;left:0;height:2px;background:var(--accent);content:""}
.top-actions{margin-left:auto;display:flex;align-items:center;gap:10px}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;font-size:var(--fs-md);border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);cursor:pointer}
.icon-btn:hover{color:var(--text);border-color:var(--accent)}
.gh{display:inline-flex;align-items:center;gap:7px;height:38px;padding:0 14px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);font:var(--fs-micro) var(--mono);letter-spacing:.05em}
.gh:hover{color:var(--text);border-color:var(--accent)}

.hero{padding:clamp(46px,6vw,78px) 0 clamp(28px,4vw,40px);border-bottom:1px solid var(--border-soft)}
.hero.compact{padding:clamp(38px,5vw,58px) 0 clamp(22px,3vw,32px)}
.hero h1{font-size:var(--fs-h1);line-height:1.05;letter-spacing:-.02em;margin:0 0 .5rem;font-weight:680}
.hero p{color:var(--muted);font-size:var(--fs-md);max-width:60ch;margin:.2rem 0 0}
.statline{display:flex;flex-wrap:wrap;gap:22px;margin-top:24px;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.05em}
.statline b{color:var(--text);font-weight:600}
/* 首頁只跟其他頁差在「大一級」，其餘完全共用 hero。
   改版前首頁自成一套 .mh-*，六條規則裡沒有一條的 token 跟 hero 對得上——
   同一種東西（一頁的標頭）長成兩套，改一邊另一邊就悄悄分岔。 */
.hero.lead{padding:clamp(56px,7vw,96px) 0 clamp(34px,4.5vw,50px)}
.hero.lead h1{font-size:var(--fs-display);line-height:1.02;letter-spacing:-.03em;max-width:20ch;text-wrap:balance}
.empty-lines{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.empty-line{font:var(--fs-micro) var(--mono);letter-spacing:.05em;color:var(--quiet);border:1px solid var(--border-soft);border-left:3px solid var(--tc,var(--border));border-radius:7px;padding:6px 12px}

.section{padding:clamp(34px,5vw,56px) 0}
.section-tint{background:var(--surface-soft);border-block:1px solid var(--border-soft)}
.section-head{margin:0 0 22px}
.section-head .kicker{color:var(--muted)}
.section-head h2{font-size:var(--fs-h2);letter-spacing:-.01em;margin:.1rem 0 .3rem;font-weight:640}
.section-head p{color:var(--muted);margin:.2rem 0 0;max-width:64ch}
.text-link{display:inline-flex;align-items:center;gap:6px;margin-top:20px;color:var(--accent);font:var(--fs-mini) var(--mono);letter-spacing:.05em}
.text-link:hover{text-decoration:underline}

article.event{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:clamp(20px,3vw,28px);margin-bottom:16px;transition:border-color .16s,transform .16s}
article.event:hover{border-color:var(--border);transform:translateY(-1px)}
.chips{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:11px}
.chip{font:var(--fs-micro) var(--mono);letter-spacing:.06em;padding:4px 9px;border-radius:999px;border:1px solid var(--border-soft);background:var(--surface-soft);color:var(--muted)}
.chip.co{color:var(--text);border-color:var(--border);font-weight:600}
.chip.warn{color:var(--forecast);border-color:color-mix(in srgb,var(--forecast) 45%,var(--border));background:color-mix(in srgb,var(--forecast) 8%,transparent)}
.chip.track{color:var(--tc,var(--muted));border-color:color-mix(in srgb,var(--tc,var(--border)) 40%,var(--border))}
article.event h2{font-size:var(--fs-h2);line-height:1.34;letter-spacing:-.01em;margin:.1rem 0 .5rem;font-weight:640}
article.event h2 a:hover{color:var(--accent)}
/* 綁 p 不是裸的 .lead：`lead` 這個名字被兩個東西共用——事件摘要段落（這一條）與
   首頁 hero 的尺寸修飾詞（.hero.lead）。裸的 .lead 排在 .shell 之後、同權重，它的
   margin:0 於是蓋掉 .shell 的 margin-inline:auto。2026-07-28 實測：首頁整個 hero
   貼齊左邊界（x=0，其他四頁 x=323），h1 連 color 也一起吃到 --muted。
   綁上 p 之後它永遠命中不到 <section>。同框衝突由 selftest 機械檢查。 */
p.lead{color:var(--muted);font-size:var(--fs-md);margin:0}
.layers{margin-top:18px;display:flex;flex-direction:column;gap:14px}
.layer .lbl{font:var(--fs-micro) var(--mono);letter-spacing:.1em}
.layer p{margin:6px 0 0;font-size:var(--fs-base)}
.layer.fact .lbl{color:var(--fact)}.layer.analysis .lbl{color:var(--analysis)}.layer.impact .lbl{color:var(--impact)}
.layer.accent .lbl{color:var(--accent)}.layer.forecast .lbl{color:var(--forecast)}
.layer.block{padding:14px 17px;border-radius:var(--radius-sm);background:var(--surface-soft)}
.layer.block.fact{border-left:3px solid var(--fact)}.layer.block.accent{border-left:3px solid var(--accent)}
.ev{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:20px 0 0;padding:0;list-style:none;color:var(--quiet);font:var(--fs-micro) var(--mono)}
.ev .lbl{color:var(--muted)}
.ev a{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border-radius:7px;border:1px solid color-mix(in srgb,var(--fact) 34%,var(--border));color:var(--fact);background:color-mix(in srgb,var(--fact) 6%,var(--surface-soft));word-break:break-all}
.ev a:hover{border-color:var(--fact)}
.score{margin:14px 0 0;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.05em;font-variant-numeric:tabular-nums;display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.score b{color:var(--text)}
.detail-link{margin-left:auto;color:var(--accent)}

.rows{display:flex;flex-direction:column;gap:2px}
.row{display:grid;grid-template-columns:96px 1fr auto;gap:16px;align-items:baseline;padding:14px 8px;border-bottom:1px solid var(--border-soft)}
.row:hover{background:var(--surface-soft)}
.row time{color:var(--quiet);font:var(--fs-micro) var(--mono)}
.row .rt{font-size:var(--fs-md);font-weight:560;line-height:1.4}
/* 原文永遠印在中文下面一行：譯文是二手的，讀者要能看到一手的那句。 */
.row .rt-src{font-size:var(--fs-sm);font-weight:400;line-height:1.35;opacity:.62;margin-top:.15rem}
.title-src{font-size:var(--fs-base);opacity:.6;margin:.25rem 0 0;font-weight:400}
.row .rm{color:var(--muted);font:var(--fs-micro) var(--mono);letter-spacing:.05em;white-space:nowrap}

.line-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.line-block{background:var(--surface);border:1px solid var(--border-soft);border-top:3px solid var(--tc,var(--accent));border-radius:var(--radius-md);padding:20px 22px}
.line-block h3{font-size:var(--fs-lg);margin:.1rem 0 .3rem;letter-spacing:-.01em}
.line-block .lc{color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.06em}
.line-block ul{margin:14px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:9px}
.line-block li{font-size:var(--fs-base);line-height:1.45;color:var(--muted);display:flex;gap:9px}
.line-block li time{flex:none;color:var(--quiet);font:var(--fs-micro) var(--mono)}
.line-block li b{color:var(--text);font-weight:520}
.line-empty{color:var(--quiet);font-size:var(--fs-base);margin-top:12px}
.line-section h2{display:flex;align-items:center;gap:10px;font-size:var(--fs-xl);margin:0 0 4px}
.line-section h2::before{content:"";width:12px;height:12px;border-radius:3px;background:var(--tc,var(--accent))}
.line-meta{color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.05em;margin:0 0 18px}
.line-thesis{color:var(--muted);font-size:var(--fs-base);line-height:1.6;margin:10px 0 0;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.narrative{background:var(--surface);border:1px solid var(--border-soft);border-left:3px solid var(--tc,var(--accent));border-radius:var(--radius-md);padding:20px 24px;margin:0 0 18px}
.narrative .thesis{font-size:var(--fs-md);line-height:1.7;margin:0;color:var(--text)}
.narrative .nn{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:16px}
@media(max-width:640px){.narrative .nn{grid-template-columns:1fr}}
.narrative .nn .lbl{display:block;font:var(--fs-micro) var(--mono);letter-spacing:.12em;color:var(--tc,var(--accent));margin-bottom:5px}
.narrative .nn p{margin:0;font-size:var(--fs-base);color:var(--muted);line-height:1.65}
.lens-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:0 0 22px}
.lens{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:18px 20px}
.lens-role{display:inline-block;font:var(--fs-micro) var(--mono);letter-spacing:.1em;color:var(--tc,var(--accent));border:1px solid color-mix(in srgb,var(--tc,var(--accent)) 40%,var(--border));border-radius:999px;padding:3px 9px;margin-bottom:11px}
.lens-q{font-size:var(--fs-base);font-weight:580;line-height:1.45;margin:0 0 8px}
.lens-a{font-size:var(--fs-base);color:var(--muted);line-height:1.6;margin:0 0 10px}
.lens-w{font:var(--fs-micro) var(--mono);color:var(--quiet);line-height:1.55;margin:0;display:flex;gap:6px}
.lens-w span{color:var(--tc,var(--accent));flex:none}
.line-sub{font:var(--fs-micro) var(--mono);letter-spacing:.1em;color:var(--muted);margin:4px 0 14px;text-transform:uppercase}

.tl-controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 26px}
.chip-row{display:flex;flex-wrap:wrap;gap:7px}
.chip-row button{font:var(--fs-micro) var(--mono);letter-spacing:.04em;padding:6px 12px;border-radius:999px;border:1px solid var(--border-soft);background:var(--surface);color:var(--muted);cursor:pointer}
.chip-row button:hover{color:var(--text)}
.chip-row button.active{color:var(--canvas);background:var(--accent);border-color:var(--accent)}
.tl-count{margin-left:auto;color:var(--quiet);font:var(--fs-micro) var(--mono)}
.tl-year{margin-bottom:30px}
.tl-year>h2{font:var(--fs-mini) var(--mono);letter-spacing:.14em;color:var(--muted);margin:0 0 6px}
.tl-month{margin:0 0 20px;padding-left:20px;border-left:1px solid var(--border-soft)}
.tl-month>time{display:block;font:var(--fs-micro) var(--mono);letter-spacing:.08em;color:var(--forecast);margin:0 0 12px}
.tl-card{position:relative;background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-sm);padding:15px 18px;margin-bottom:10px}
.tl-card::before{content:"";position:absolute;left:-25px;top:20px;width:9px;height:9px;border-radius:50%;background:var(--tc,var(--accent));box-shadow:0 0 0 4px color-mix(in srgb,var(--tc,var(--accent)) 14%,transparent)}
.tl-card time{color:var(--quiet);font:var(--fs-micro) var(--mono)}
.tl-card h3{font-size:var(--fs-md);line-height:1.4;margin:5px 0 5px;font-weight:560}
.tl-card h3 a:hover{color:var(--accent)}
.tl-card p{color:var(--muted);font-size:var(--fs-base);margin:0}
.tl-card .tl-meta{margin-top:9px;display:flex;flex-wrap:wrap;gap:10px;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.04em}
.tl-hide{display:none!important}

.sig-stream{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.sig-card{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:18px 20px;transition:border-color .16s,transform .16s}
.sig-card:hover{border-color:var(--border);transform:translateY(-1px)}
.sig-card.research{border-left:3px solid var(--analysis)}
.sig-card.high{border-left:3px solid var(--fact)}
.sig-meta{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:9px}
.sig-tags{display:flex;flex-wrap:wrap;gap:6px}
.sig-tag{font:var(--fs-micro) var(--mono);letter-spacing:.05em;padding:3px 7px;border-radius:6px;background:var(--surface-soft);color:var(--muted);border:1px solid var(--border-soft)}
.sig-card time{color:var(--quiet);font:var(--fs-micro) var(--mono);white-space:nowrap}
.sig-card h2{font-size:var(--fs-md);line-height:1.4;margin:2px 0 6px;font-weight:560}
.sig-card p{color:var(--muted);font-size:var(--fs-base);margin:0 0 12px;flex:1}
.sig-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.04em;border-top:1px solid var(--border-soft);padding-top:10px}
.sig-foot .go{color:var(--fact);display:inline-flex;align-items:center;gap:4px}

/* page-status strip + signal toolbar */
.page-status{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin-top:26px;border:1px solid var(--border-soft);border-radius:var(--radius-md);overflow:hidden;background:var(--border-soft)}
.page-status div{background:var(--canvas);padding:14px 16px}
.page-status span{display:block;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.1em;margin-bottom:4px}
.page-status b{font-size:var(--fs-lg);font-weight:620;font-variant-numeric:tabular-nums}
@media(max-width:560px){.page-status{grid-template-columns:1fr}}
.sig-toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 22px}
.sig-search{display:flex;align-items:center;gap:8px;flex:1;min-width:220px;padding:0 14px;height:40px;border:1px solid var(--border-soft);border-radius:999px;background:var(--surface);color:var(--quiet)}
.sig-search input{flex:1;border:0;background:transparent;color:var(--text);font-size:var(--fs-tiny);outline:none}
.sig-select{position:relative}
.sig-select select{appearance:none;-webkit-appearance:none;height:40px;padding:0 32px 0 14px;border:1px solid var(--border-soft);border-radius:999px;background:var(--surface);color:var(--muted);font:var(--fs-mini) var(--mono);cursor:pointer}
.sig-select::after{content:"▾";position:absolute;right:13px;top:11px;color:var(--quiet);pointer-events:none}
.sig-count{margin-left:auto;color:var(--quiet);font:var(--fs-micro) var(--mono)}
.sig-more{margin:24px auto 0;display:block;padding:9px 22px;border:1px solid var(--border);border-radius:999px;background:var(--surface);color:var(--muted);font:var(--fs-mini) var(--mono);cursor:pointer}
.sig-more:hover{color:var(--text);border-color:var(--accent)}
.sig-none{display:none;color:var(--quiet);font:var(--fs-mini) var(--mono);text-align:center;padding:36px}

/* ── event detail ── */
.crumb{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font:var(--fs-micro) var(--mono);letter-spacing:.05em;margin-bottom:16px}
.crumb:hover{color:var(--text)}
.detail-grid{display:grid;grid-template-columns:1fr 320px;gap:28px;align-items:start}
@media(max-width:820px){.detail-grid{grid-template-columns:1fr}}
.detail-main h2,.detail-aside h3{font-size:var(--fs-sm);font:700 12px var(--mono);letter-spacing:.12em;color:var(--muted);margin:0 0 16px;text-transform:uppercase}
.detail-block{margin-bottom:34px}
.jn-note{color:var(--muted);font-size:var(--fs-sm);line-height:1.6;margin:0 0 14px;padding:9px 12px;border-left:2px solid var(--border-soft);background:color-mix(in srgb,var(--quiet) 6%,transparent)}
.tl-chip{display:inline-block;margin-left:8px;padding:1px 7px;border-radius:9px;border:1px solid var(--border-soft);color:var(--quiet);font:var(--fs-micro) var(--mono);vertical-align:1px}
.tl-cut{grid-column:1/-1;margin:6px 0 14px;padding:8px 12px;border-top:1px dashed var(--border-soft);color:var(--quiet);font-size:var(--fs-sm);line-height:1.6}
.journey{list-style:none;margin:0;padding:0 0 0 6px}
.journey li{position:relative;padding:0 0 20px 24px;border-left:2px solid var(--border-soft)}
.journey li:last-child{border-left-color:transparent;padding-bottom:0}
.journey li::before{content:"";position:absolute;left:-7px;top:2px;width:12px;height:12px;border-radius:50%;background:var(--dc,var(--accent));box-shadow:0 0 0 4px color-mix(in srgb,var(--dc,var(--accent)) 16%,transparent)}
.jn-head{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.jn-type{font:var(--fs-micro) var(--mono);letter-spacing:.08em;padding:2px 7px;border-radius:5px;color:var(--dc,var(--accent));border:1px solid color-mix(in srgb,var(--dc,var(--accent)) 40%,var(--border))}
.jn-head time{color:var(--quiet);font:var(--fs-micro) var(--mono)}
.journey b{display:block;font-size:var(--fs-base);font-weight:540;line-height:1.45;margin:6px 0 2px}
.journey small{color:var(--muted);font:var(--fs-micro) var(--mono);letter-spacing:.04em}
.journey a.jn-open{color:var(--fact)}
.aside-box{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-md);padding:20px}
.score-hero{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px}
.score-hero .sh{background:var(--surface-soft);border-radius:var(--radius-sm);padding:12px 14px}
.score-hero .sh span{display:block;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.08em}
.score-hero .sh b{font-size:var(--fs-2xl);font-weight:660;font-variant-numeric:tabular-nums}
.factors{display:flex;flex-direction:column;gap:9px}
.factor{display:grid;grid-template-columns:74px 1fr minmax(30px,auto);gap:9px;align-items:center;font:var(--fs-micro) var(--mono);color:var(--muted)}
.factor .bar{height:5px;border-radius:3px;background:var(--border-soft);overflow:hidden}
.factor .bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.factor b{color:var(--text);text-align:right;font-variant-numeric:tabular-nums}
/* 沒量過的那幾格：**不能長得像一條空的比例條**。
   `.bar` 本身就是一條灰色軌道，量到 0 的時候也是這個樣子——兩者在畫面上
   一模一樣，而那正是這一格要修掉的誤會（同一張卡片上 heat 寫著「未量測」，
   旁邊四個因子理直氣壯地印 0）。所以軌道換成虛線、不填色，值印字不印數。 */
/* GitHub 動能那一頁的專屬規則。**搬進共用樣式表**：它原本住在
   pulse-github.py 的 inline <style> 裡——六個硬寫字級、零個級距 token，
   而且這一輪把字級收成級距時它整份被跳過（它不經過 pulse-render）。 */
.gh-wrap{padding:clamp(30px,5vw,52px) 0 clamp(60px,9vw,110px)}
.gh-note{color:var(--quiet);font:var(--fs-micro) var(--mono);margin:0 0 18px}
.gh-row{display:grid;grid-template-columns:34px 1fr auto;gap:14px;align-items:baseline;padding:15px 4px;border-bottom:1px solid var(--border-soft)}
.gh-row:hover{background:var(--surface-soft)}
.gh-rank{font:600 var(--fs-tiny) var(--mono);color:var(--quiet);text-align:right}
.gh-main .n{font-size:var(--fs-md);font-weight:600;line-height:1.35}
.gh-main .n a{color:var(--text)}.gh-main .n a:hover{color:var(--accent)}
.gh-main .d{color:var(--muted);font-size:var(--fs-base);margin:3px 0 0}
/* 原文一律留著。譯文是二手的，讀者要能一眼看到一手的那句。 */
.gh-main .d-src{color:var(--quiet);font:var(--fs-micro)/1.5 var(--mono);margin:2px 0 0}
.gh-main .t{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}
.gh-tag{font:var(--fs-micro) var(--mono);letter-spacing:.04em;padding:2px 7px;border-radius:5px;background:var(--surface-soft);color:var(--muted);border:1px solid var(--border-soft)}
.gh-new{color:var(--fact);border-color:color-mix(in srgb,var(--fact) 40%,var(--border))}
.gh-metric{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.gh-metric .v{font:700 var(--fs-md) var(--mono);color:var(--fact)}
.gh-metric .v.down{color:var(--muted)}
.gh-metric .s{display:block;color:var(--quiet);font:var(--fs-micro) var(--mono);margin-top:2px}
.gh-none{color:var(--quiet);font:var(--fs-mini) var(--mono);text-align:center;padding:40px}

/* ── 泳道：一列一家公司、一格一個月 ────────────────────────────────
   改版前這一頁是「年 → 月 → 一疊卡片」，卡片彼此之間沒有任何視覺關聯，
   關聯性完全靠讀者自己記。實測 41 則已發布事件裡有 34 則落在前三家公司，
   而扁平清單把那件事完全藏起來了。
   縱軸選公司不選產品線，是因為 fingerprint 有 36/41 是 null（見 lane_key）。 */
.lane-intro{margin:34px 0 12px}
.lane-intro h2{margin:0 0 4px;font-size:var(--fs-lg);letter-spacing:.01em}
.lane-intro p{margin:0;color:var(--muted);font-size:var(--fs-base)}
.lane-intro-2{margin-top:52px}
.lane-wrap{overflow-x:auto;padding-bottom:6px;-webkit-overflow-scrolling:touch}
.lane-grid{min-width:max(100%,calc(150px + var(--cols) * var(--colw,76px)))}
.lane-row{display:grid;grid-template-columns:150px 1fr;align-items:stretch;border-top:1px solid var(--border-soft)}
.lane-row:last-child{border-bottom:1px solid var(--border-soft)}
.lane-head{border-top:0}
.lane-name{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 12px 9px 0;font-size:var(--fs-tiny)}
.lane-name b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lane-name span{color:var(--quiet);font:var(--fs-micro) var(--mono)}
.lane-track{display:grid;grid-template-columns:repeat(var(--cols),minmax(var(--colw,76px),1fr))}
.lane-h{padding:7px 6px;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.06em;text-align:center;white-space:nowrap}
.lane-cell{display:flex;flex-wrap:wrap;align-content:center;gap:5px;justify-content:center;padding:8px 6px;border-left:1px solid var(--border-soft)}
.lane-dot{position:relative;width:11px;height:11px;border-radius:50%;background:var(--tc);opacity:.85}
.lane-dot:hover,.lane-dot:focus-visible{opacity:1;outline:2px solid var(--tc);outline-offset:2px}
/* 觀測起點那一則：空心，代表「這是我們開始追的地方」 */
/* 覆蓋狀態要在**點上**看得出來，不能只藏在浮層裡。
   只放浮層的話，泳道整片看起來都是我們當場看到的——那正是 coverage 這一層
   要修掉的誤會（同一個理由，編年那邊掛的是「回填」兩個字）。
   實心＝當場看到；空心＝回填；虛線空心＝連當時在不在場都沒紀錄。 */
.lane-dot[data-cov=backfilled]{background:none;border:2px solid var(--tc);opacity:.75}
.lane-dot[data-cov=unknown]{background:none;border:2px dashed var(--tc);opacity:.6}
.lane-dot.is-cut{background:none;border:2px solid var(--tc);box-shadow:0 0 0 3px color-mix(in srgb,var(--tc) 28%,transparent)}
.lane-legend{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0 2px;color:var(--muted);font:var(--fs-micro) var(--mono)}
.lane-legend span{display:inline-flex;align-items:center;gap:6px}
.lane-legend i{width:11px;height:11px;border-radius:50%;background:var(--muted)}
.lane-legend i.b{background:none;border:2px solid var(--muted)}
.lane-legend i.u{background:none;border:2px dashed var(--muted)}
.lane-many{display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:16px;padding:0 5px;
  border-radius:4px;background:color-mix(in srgb,var(--accent) calc(var(--a) * 1%),transparent);
  color:var(--text);font:var(--fs-micro) var(--mono);cursor:default}
.lane-many[data-lvl="1"]{--a:22}.lane-many[data-lvl="2"]{--a:42}
.lane-many[data-lvl="3"]{--a:62}.lane-many[data-lvl="4"]{--a:84}
/* 這裡本來是一個浮在格子上方的 tip。它有兩個問題，第二個才是真的：
     一、住在 .lane-wrap 裡會被裁掉——那是 overflow-x:auto 的捲動容器，
         而 CSS 規範說一軸不是 visible 時另一軸的 visible 會算成 auto。
     二、**就算逃出容器，它還是蓋住東西**。第一列離欄頭很近，往上彈就正好
         壓在日期欄頭上——而那是讀者當下最需要的座標：這個點是哪一天的。
   浮層在密集格線上永遠會遮到某個東西，這不是位置算得夠不夠好的問題。
   改成固定在格線下方的一條判讀列：不蓋任何東西、位置永遠一樣、
   觸控裝置沒有 hover 也照樣用得到（點一下就更新）。 */
.lane-readout{display:flex;align-items:baseline;gap:10px;min-height:34px;margin-top:10px;padding:7px 11px;
  border:1px solid var(--border-soft);border-radius:var(--radius-sm);background:var(--surface-soft)}
.lane-readout time{color:var(--quiet);font:var(--fs-micro) var(--mono);white-space:nowrap}
.lane-readout em{padding:1px 6px;border-radius:99px;background:var(--surface-2);color:var(--muted);
  font:var(--fs-micro) var(--mono);font-style:normal;white-space:nowrap}
.lane-readout b{font-size:var(--fs-tiny);font-weight:600;line-height:1.5}
.lane-readout .ph{color:var(--quiet);font-size:var(--fs-tiny);font-weight:400}
@media(max-width:720px){
  .lane-row{grid-template-columns:104px 1fr}
  }
.factor .bar-unmeasured{height:0;border-top:1px dashed var(--border-soft);background:none;border-radius:0}
.factor b.unmeasured{color:var(--muted);font-size:var(--fs-micro);letter-spacing:.02em;font-variant-numeric:normal}
.warnbox{margin-top:14px;padding:11px 13px;border-radius:var(--radius-sm);border:1px solid color-mix(in srgb,var(--forecast) 40%,var(--border));background:color-mix(in srgb,var(--forecast) 7%,transparent);color:var(--forecast);font:var(--fs-micro) var(--mono);line-height:1.6}

.site-footer{border-top:1px solid var(--border-soft);background:var(--surface-soft);margin-top:20px}
.footer-grid{display:grid;grid-template-columns:1.4fr 1fr;gap:28px;padding:40px 0 26px}
.footer-brand strong{display:block;font-size:var(--fs-mini);letter-spacing:.16em;margin-bottom:8px}
.footer-brand p{color:var(--muted);font-size:var(--fs-base);margin:0;max-width:44ch}
.footer-links{display:flex;gap:44px;justify-content:flex-end}
.footer-links nav{display:flex;flex-direction:column;gap:9px}
.footer-links span{color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.1em;margin-bottom:2px}
.footer-links a{color:var(--muted);font-size:var(--fs-base)}.footer-links a:hover{color:var(--text)}
.footer-meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;padding:16px 0 40px;border-top:1px solid var(--border-soft);color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.04em}
.mobile-nav{position:fixed;z-index:80;bottom:0;left:0;right:0;display:none;justify-content:space-around;background:color-mix(in srgb,var(--canvas) 92%,transparent);backdrop-filter:blur(20px);border-top:1px solid var(--border-soft)}
.mobile-nav a{display:flex;flex-direction:column;align-items:center;gap:3px;padding:9px 0;color:var(--quiet);font:var(--fs-micro) var(--mono);letter-spacing:.05em;flex:1}
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
  // 泳道判讀列：固定在格線下方，不蓋任何東西。
  // 沒有 JS 時每個點還有 <a title>，一樣讀得到，只是要等瀏覽器的原生提示。
  var ro=document.getElementById('lane-readout');
  if(ro){
    var show=function(a){
      var c=a.getAttribute('data-tip-c');
      ro.innerHTML='<time>'+a.getAttribute('data-tip-d')+'</time>'
        +(c?'<em>'+c+'</em>':'')+'<b>'+a.getAttribute('data-tip-t')+'</b>';
    };
    // 滑開之後**不清空**：清掉會閃，而且讀者常常是滑過去再回頭看那一行。
    document.addEventListener('mouseover',function(e){
      var a=e.target.closest&&e.target.closest('.lane-dot[data-tip-t]');if(a)show(a);});
    document.addEventListener('focusin',function(e){
      var a=e.target.closest&&e.target.closest('.lane-dot[data-tip-t]');if(a)show(a);});
  }
  var row=document.querySelector('[data-filter-row]');
  if(row){var cards=[].slice.call(document.querySelectorAll('[data-track]'));
    row.addEventListener('click',function(e){
      var b=e.target.closest('button[data-filter]');if(!b)return;
      row.querySelectorAll('button').forEach(function(x){x.classList.remove('active')});
      b.classList.add('active');var f=b.getAttribute('data-filter');
      var n=0;cards.forEach(function(c){var ok=f==='all'||c.getAttribute('data-track')===f;
        c.classList.toggle('tl-hide',!ok);
        // 只數卡片。泳道的點跟卡片是同一批事件的兩種畫法，兩邊都數會變兩倍。
        if(ok&&c.classList.contains('tl-card'))n++;});
      // 一整列都被篩掉時把那一列收起來——留一排空格子，讀者會以為那家公司
      // 這段時間有事而我們沒抓到，那是把「不符合篩選」講成「沒有動靜」。
      [].slice.call(document.querySelectorAll('.lane-row[data-lane]')).forEach(function(r){
        r.classList.toggle('tl-hide',!r.querySelector('.lane-dot:not(.tl-hide)'));});
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
<a class="brand" href="{prefix}" aria-label="AI Pulse 首頁">{BRAND}<span><strong>AI PULSE</strong><small>哪則進得來，規則說了算</small></span></a>
<nav class="desktop-nav" aria-label="主導覽">{nav}</nav>
<div class="top-actions">
<button class="icon-btn" data-theme-toggle type="button" aria-label="切換淺／深色">{SUN}</button>
<a class="gh" href="https://github.com/Vincenthsiehisme/ai-pulse" target="_blank" rel="noopener">GitHub</a>
</div></header>
<main id="main">{body}</main>
<footer class="site-footer"><div class="shell footer-grid">
<div class="footer-brand"><strong>AI PULSE</strong><p>哪則消息進得來由規則決定，沒有模型參與；敘述那一層才有潤稿。同一份資料重跑，會得到同一個網站。</p></div>
<div class="footer-links"><nav><span>探索</span>{foot_links}</nav></div>
</div><div class="shell footer-meta">
<span>規則決定去留 · 潤稿只碰文字 · 重跑結果一樣</span><span>全站日期為{esc(TZ_LABEL)} · 更新於 {esc(generated)}</span>
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
# 判斷層的 rule-tag。**它是即時算的，不是 note 裡存的那一份。**
#
# `pulse-enrich-apply.py` 曾經依當下的 `independent_sources` 把這句話寫進 prose，
# 之後不再重算；而同一頁的警示框是 render 即時算的。第二個獨立來源進來之後，
# 警示框消失了，那句話留著——`evt-2026-07-21-1bdb1a` 在對外站上長期寫著
# 「單一獨立來源」，而它自己的 frontmatter 是 `independent_sources: 2`。
# **同一頁兩個相反的宣稱，而且它是這批裡唯一正在對讀者說假話的。**
#
# 凍結的快照被當成現況——跟 `_slug_to_title`、`lastmod` 當 `published` 同一隻病。
# 修法不是去改那些 note，是**把第二個時鐘拆掉**：判斷層只能有一個真相源。
JUDGMENT_TAG = {False: "（單一獨立來源，暫標待證實）", True: "（多來源佐證）"}
# 舊 note 的 prose 裡烙著其中一句。render 剝掉再貼上即時的那句，
# 所以既有的 51 份不必遷移就會自己說對話；enrich 端也不再寫入。
_FROZEN_TAG = re.compile(r"\s*（(?:單一獨立來源，暫標待證實|多來源佐證)）\s*$")


def strip_frozen_tag(text):
    return _FROZEN_TAG.sub("", (text or "").rstrip())


def layer_html(heading, text, independent=None):
    cls, label, block = LAYER_META[heading]
    b = " block" if block else ""
    if heading == "判斷":
        text = strip_frozen_tag(text)
        if independent is not None:
            text = (text + " " + JUDGMENT_TAG[(independent or 0) >= 2]).strip()
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
    layers = "".join(layer_html(h, ev["layers"][h], ev.get("independent"))
                     for h in LAYERS if ev["layers"].get(h)) if full else ""
    ev_links = "".join(f'<a href="{esc(e["url"])}" rel="noopener" target="_blank">{esc(e["sid"])} {EXT}</a>'
                       for e in ev["evidence"] if e.get("url"))
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
#: 時間軸卡片上的覆蓋標記。`backfilled` 與 `unknown` **刻意不共用字樣**——
#: 「確定是首抓撈回的」跟「不知道當時看不看得到」是兩件事，共用會把後者講成前者。
#: `observed` 不標：那是預設狀態，滿版的標記等於沒有標記。
COVERAGE_CHIP = {"backfilled": "回填", "unknown": "覆蓋未知"}
#: 觀測起點線的說明。線以下沒有任何一則是我們當場看到的。
OBSERVED_CUT_NOTE = "這條線以下，都是我們開始追之前就已經發生的事。"


def observed_cut(events):
    """→ 觀測起點線該插在第幾張卡片**之前**（events 已按日期新到舊）。不畫回 None。

    判準只用 Event 自己的 `coverage`，不另外去讀 `_probe/state.json`——那會讓
    `first_fetch_at` 多一個消費者，而判準單一實作源優先（跟第二層拿掉
    〈首抓快照〉那一列同一個理由）。

    線的位置＝**最後一則 `observed` 之後**。這樣這條線的宣稱才是可證的：
    線以下沒有任何一則是我們當場看到的。反過來畫一條「以上都是觀測到的」是假的
    ——`coverage` 是逐則、逐來源算的，新加的來源會讓晚期的事件照樣是 backfilled。
    **只宣稱守得住的那一半。**

    一則 observed 都沒有 → 回 0（線畫在最前面，整條時間軸都在線下）。
    最後一則就是 observed → 回 None（沒有回填區，不畫線）。
    """
    last = None
    for i, e in enumerate(events):
        if e.get("coverage") == "observed":
            last = i
    if last is None:
        return 0
    return None if last == len(events) - 1 else last + 1


#: 證據區塊的標題與說明，由 coverage 與證據筆數決定。
#: 規格見 references/event-timestamps.md〈第三個現場：呈現層〉。
JOURNEY_HEADING = "發展歷程"
EVIDENCE_HEADING = "證據"
COVERAGE_NOTE = {
    "backfilled": "這幾筆是我們開始追這個來源時，一次撈回來的舊資料。事情發生的當下，我們不在場。",
    # 「確定是回填」跟「不知道」是兩件事，所以不共用同一句。共用的話，
    # 讀者會把「我們沒紀錄」讀成「我們確定沒在看」，那是把不知道講成知道。
    "unknown": "這則的來源是什麼時候開始被追的，我們沒有留下紀錄，所以說不準當時在不在場。",
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
    for e in ev["evidence"]:
        sid, url = e.get("sid"), e.get("url")
        rec = corpus_idx.get(url) or {}
        # 優先序：**Event 自己存的** → 語料 → 說不知道。
        # 先問 Event 自己，這一區才不再依賴 `_corpus/` 的保留期（規格〈第三個現場〉
        # 的〈一條沒被記下來的依賴〉）。語料退居補充：它只在舊 note 還沒補上
        # evidence[].title 的期間有用。
        # 兩個都沒有就說不知道——退回來源名／事件日的話，畫面上會出現一筆「標題是
        # 來源名」的證據，或一整串「全部同一天」的證據，而後者正是讀者用來判斷
        # 這件事怎麼發展的唯一線索。
        items.append({"sid": sid, "url": url,
                      "title": e.get("title") or rec.get("title") or TITLE_UNKEPT,
                      "date": e.get("published") or rec.get("date") or None})
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
        return heading, '<p class="line-empty">這則目前只有一個來源，還沒有第二個聲音。</p>'
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
        raw = sf.get(key)
        # None ＝ 從來沒量過（scoring.py 對空 metrics 回 None）。印「未量測」、
        # **而且不畫比例條**——一條長度 0 的條子跟「量到 0」在畫面上一模一樣，
        # 那正是要修掉的那個誤會。跟 heat 同一條規矩（HEAT_UNMEASURED）。
        if raw is None:
            facs.append(f'<div class="factor"><span>{esc(label)}</span>'
                        f'<div class="bar bar-unmeasured"></div>'
                        f'<b class="unmeasured">{esc(HEAT_UNMEASURED)}</b></div>')
            continue
        try:
            pct = max(0, min(100, round(float(raw) / cap * 100)))
        except (TypeError, ValueError):
            pct = 0
        shown = raw if cap != 100 else f"{int(round(float(raw)))}" if isinstance(raw, (int, float)) else raw
        facs.append(f'<div class="factor"><span>{esc(label)}</span><div class="bar"><i style="width:{pct}%"></i></div><b>{esc(shown)}</b></div>')
    warn = ""
    if (ev["independent"] or 0) < 2:
        warn = '<div class="warnbox">目前只有一個獨立來源說過這件事。要等第二個彼此無關的來源，才會從「待證實」升上來。</div>'
    return f"""<div class="aside-box">
<h3>評分理由</h3>
<div class="score-hero">{hero_html}</div>
<div class="factors">{"".join(facs)}</div>
{warn}</div>"""


# ─────────────────────── pages ───────────────────────
def build_home(events, narratives, generated):
    n = len(events)
    companies = len({e["company"] for e in events if e["company"]})
    # 首頁跟其他三頁用**同一個** hero()。
    #
    # 改版前首頁自成一套 `mh-*`：eyebrow 的字距 .3em vs kicker 的 .18em、
    # 標題 weight 720 vs 680、字距 -.03em vs -.02em、副標用等寬 vs 用內文字體、
    # 統計數字是一行文字 vs 其他頁的三格 page-status——**每一個 token 都不一樣**，
    # 而它們是同一種東西：一頁的標頭。
    # 首頁本來就該比較大，那用一個 `lead` 修飾詞表達就好，不必整套重寫。
    hero_html = hero("WHAT CHANGED",
                     "AI 產業的關鍵變化，每則查得到出處",
                     "每則標明誰先說的、有幾個獨立來源、我們什麼時候才看到它。",
                     extra=page_status([("已發布", n), ("主體", companies),
                                        ("更新", generated)]),
                     cls="lead")
    latest = events[0] if events else None
    latest_html = (f'<section class="section shell">{section_head("LATEST MATERIAL SHIFT", "這幾則最值得看")}'
                   f'{event_card(latest, "", full=True)}</section>') if latest else ""
    recent = events[1:9]
    recent_html = ""
    if recent:
        rows = "".join(recent_row(e, "") for e in recent)
        recent_html = f"""<section class="section section-tint"><div class="shell">
{section_head("ALSO WORTH KNOWING", "其餘通過檢查的事件", "一樣驗過來源、一樣附證據，只是重要性排在後面。")}
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
{section_head("SIX INDUSTRY TRENDS", "六大領域趨勢", "散落的事件收成六條可以一路追下去的故事。")}
<div class="line-grid">{''.join(blocks)}</div>
<a class="text-link" href="lines/">進入領域趨勢 {ARROW}</a></section>"""
    manifesto = ('<section class="section section-tint"><div class="shell">'
                 + section_head("這裡的取捨怎麼來的", "每一則為什麼在這裡，都查得到",
                                "一則消息夠不夠格發、熱度可不可信，由寫死的規則決定，沒有模型參與；"
                                "同一份資料重跑一次，會得到同一個網站。"
                                "文字讀起來像人寫的，是因為敘述那一層經過潤稿——"
                                "那一步用了模型，而它碰不到任何一個「發或不發」的決定。")
                 + '</div></section>')
    body = hero_html + latest_html + recent_html + lines_html + manifesto
    return page_layout("home", "AI Pulse — AI 產業的關鍵變化，每則查得到出處",
                       "每則事件都標明是誰先說的、有幾個獨立來源、我們什麼時候才看到它。",
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
    h = hero("TOPIC LINES", "領域趨勢", "每條主線底下是同一件事的連續進展：有哪些事件、最近一次是什麼時候、有幾個彼此獨立的來源說過。",
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
                       "六條可以一路追下去的故事：模型能力、Agent、產品、基礎設施、資本、全球版圖。", body, 1, generated)


LANE_DOT_MAX = 3


def lane_key(e):
    """泳道的縱軸＝**公司**。

    量過才決定的：41 則已發布事件裡，`fingerprint`（`google:gemini:3.6-flash`
    那種產品線鍵）有 **36 則是 null**，只有 `google:gemini` 湊得出兩則——
    產品線軸今天畫不出來（那條缺口是 BACKLOG 的 `gate-未接線`：
    `clustering.version_derivation` 從來沒接上）。

    公司則是密的：10 家，NVIDIA 14 則、OpenAI 11 則、Anthropic 7 則，
    **41 則裡有 34 則落在前三家**。「看不出關聯」的具體樣貌就是這個——
    14 則 NVIDIA 散在一條扁平的時間流裡，讀者看不出那是同一條線在動。
    """
    return e.get("company") or "其他"


def build_timeline(events, generated):
    # 觀測起點線：線以下沒有任何一則是我們當場看到的。
    cut = observed_cut(events)
    cut_id = events[cut]["id"] if cut is not None and cut < len(events) else None

    # ── 時間刻度的粗細**由資料的跨度決定，不寫死**。
    #
    # 第一版寫死用「月」，結果實測整條時間軸塌成一欄：41 則已發布事件全部落在
    # 2026-07（07-07 → 07-27）。一張只有一欄的泳道圖，等於把「誰在動」這個問題
    # 換成一句「大家都在動」——比不畫還糟，因為它看起來像有資訊。
    #
    # 判準只有一條：**格子數落在能掃視的範圍內**。跨度短就用天，長就用月。
    def _d(e):
        return (e["date_display"] or e["date"] or "0000-00-00")[:10]

    days = sorted({_d(e) for e in events}, reverse=True)
    # 判準是**跨了幾天**，不是「出現過幾個月份」。
    # 第一版用後者，而相隔半年的兩則事件只會有 2 個月份——於是它判成
    # 「跨度短」，畫出 204 個日欄位。是測試抓到的，不是我看出來的。
    try:
        span_days = (_date.fromisoformat(days[0]) - _date.fromisoformat(days[-1])).days
    except ValueError:
        span_days = 10 ** 6
    # 60 天上限＝最多 61 欄。再多就掃不動，該退回月刻度。
    by_day = span_days <= 60

    if by_day:
        # 用**連續日期**不是「有事件的日期」——中間的空白格子本身是資訊：
        # 那幾天這家公司沒有動靜。只印有事件的日子會把安靜的日子擠掉，
        # 於是每一家看起來都一樣忙。
        lo, hi = days[-1], days[0]
        cur = _date.fromisoformat(hi)
        end = _date.fromisoformat(lo)
        cols, step = [], _timedelta(days=1)
        while cur >= end:
            cols.append(cur.isoformat())
            cur -= step
        def ym(e):
            return _d(e)
    else:
        cols = sorted({_d(e)[:7] for e in events}, reverse=True)
        def ym(e):
            return _d(e)[:7]

    months = cols
    mindex = {m: i for i, m in enumerate(months)}

    # ── 泳道：依事件數排序，多的在上。這是**讀者最可能想先看的**那條。
    lanes = defaultdict(list)
    for e in events:
        lanes[lane_key(e)].append(e)
    lane_order = sorted(lanes, key=lambda k: (-len(lanes[k]), k))

    present_tracks = {track_of(e)[0] for e in events if track_of(e)}
    filters = "".join(f'<button type="button" data-filter="{slug}">{esc(name)}</button>'
                      for slug, name, _ in TRACKS if slug in present_tracks)

    MONTH_TW = {f"{i:02d}": f"{i} 月" for i in range(1, 13)}

    def month_label(m):
        parts = m.split("-")
        if len(parts) == 3:
            # 日刻度：欄頭只印「7/21」，年份在頁面別處已經有了，
            # 每一欄重印一次年只是把欄寬撐開。
            return f"{int(parts[1])}/{int(parts[2])}"
        return f"{parts[0]} · {MONTH_TW.get(parts[1], parts[1])}"

    head_cells = "".join(f'<div class="lane-h">{esc(month_label(m))}</div>' for m in months)
    rows = []
    for name in lane_order:
        cells = [[] for _ in months]
        for e in lanes[name]:
            cells[mindex[ym(e)]].append(e)
        tds = []
        for i, bucket in enumerate(cells):
            dots = []
            # 一格塞太多點就退成一個「幾則」的方塊。**這是為了長期累積**：
            # 今天是 21 天 × 10 條、一格最多 4 點，半年後改用月刻度，
            # NVIDIA 一個月二十幾則會把格子撐爆，而一堆擠在一起的點
            # 既讀不出數量也點不到——那時它已經不是圖，是一團。
            # 門檻 3 是版面量出來的（44px 欄寬放得下三個 11px 的點加間距）。
            if len(bucket) > LANE_DOT_MAX:
                # 濃度用 alpha 表示，級距刻意粗（4 級）——細分只會讓人去比較
                # 兩個看不出差別的灰階，而這一格要回答的是「多還是少」。
                lvl = min(4, 1 + (len(bucket) - 1) // 4)
                tds.append(f'<div class="lane-cell"><span class="lane-many" data-lvl="{lvl}"'
                           f' title="{esc(name)}　{esc(month_label(months[i]))}　'
                           f'{len(bucket)} 則">{len(bucket)}</span></div>')
                continue
            for e in bucket:
                tr = track_of(e)
                tc = tr[2] if tr else "var(--accent)"
                tslug = tr[0] if tr else ""
                chip = COVERAGE_CHIP.get(e.get("coverage"))
                cut_cls = " is-cut" if cut_id and e["id"] == cut_id else ""
                # `title` 是沒有 JS 時的那一份，永遠不會被捲動容器裁掉。
                # data-tip-* 給 JS 拿去畫那個唯一的浮層。
                dots.append(
                    f'<a class="lane-dot{cut_cls}" href="{ev_href("../", e["slug"])}"'
                    f' data-track="{esc(tslug)}" data-cov="{esc(e.get("coverage") or "")}"'
                    f' style="--tc:{tc}"'
                    f' data-tip-d="{esc(e["date_display"])}"'
                    f' data-tip-c="{esc(chip or "")}"'
                    f' data-tip-t="{esc(e["title"])}"'
                    f' title="{esc(e["date_display"])}　{esc(e["title"])}"></a>')
            tds.append(f'<div class="lane-cell">{"".join(dots)}</div>')
        rows.append(f'<div class="lane-row" data-lane="{esc(name)}">'
                    f'<div class="lane-name"><b>{esc(name)}</b>'
                    f'<span>{len(lanes[name])}</span></div>'
                    f'<div class="lane-track">{"".join(tds)}</div></div>')

    # 依時間排的那份不刪——泳道回答「誰在動」，清單回答「接下來發生了什麼」。
    # 兩個問題不一樣，用同一份資料各畫一次比逼讀者在一張圖上兼顧兩者好。
    chrono = []
    for m in sorted({_d(e)[:7] for e in events}, reverse=True):
        cards = []
        for e in [x for x in events if _d(x)[:7] == m]:
            tr = track_of(e)
            tc = tr[2] if tr else "var(--accent)"
            tslug = tr[0] if tr else ""
            tname = tr[1] if tr else ""
            if cut_id and e["id"] == cut_id:
                cards.append(f'<div class="tl-cut"><span>{esc(OBSERVED_CUT_NOTE)}</span></div>')
            chip = COVERAGE_CHIP.get(e.get("coverage"))
            chip_html = f'<span class="tl-chip">{esc(chip)}</span>' if chip else ""
            cards.append(f"""<div class="tl-card" data-track="{esc(tslug)}" style="--tc:{tc}">
<time>{esc(e['date_display'])}</time>{chip_html}<h3><a href="{ev_href('../', e['slug'])}">{esc(e['title'])}</a></h3><p>{esc(e['summary'])}</p>
<div class="tl-meta"><span>{esc(e['company'])}</span>{f'<span>{esc(tname)}</span>' if tname else ''}<span>confidence {esc(e['confidence'])}</span></div></div>""")
        y, mm = m.split("-")
        chrono.append(f'<div class="tl-month"><time>{esc(y)} · {esc(MONTH_TW.get(mm, mm))}</time>{"".join(cards)}</div>')

    companies = len(lanes)
    latest = events[0]["date_display"] if events else "—"
    n_back = sum(1 for e in events if e.get("coverage") != "observed")
    tl_stat = page_status([("事件", len(events)), ("其中回填", n_back),
                           ("主體", companies), ("最新", latest)])
    body = f"""{hero("EVENT TIMELINE", "事件時間軸", "最新在前。標著「回填」的是我們開始追之前就已經發生的事。", extra=tl_stat, cls="compact")}
<section class="section shell">
<div class="tl-controls" data-filter-row>
<div class="chip-row"><button type="button" class="active" data-filter="all">全部</button>{filters}</div>
<span class="tl-count" data-count>{len(events)} 則事件</span></div>
<div class="lane-intro"><h2>誰在動</h2><p>一列一家公司，一格{'一天' if by_day else '一個月'}。點進去看那一則，滑過去先看標題。</p><div class="lane-legend"><span><i></i>當場看到</span><span><i class="b"></i>回填</span><span><i class="u"></i>覆蓋未知</span><span>數字＝那一格有幾則</span></div></div>
<div class="lane-wrap" data-lane-wrap><div class="lane-grid" style="--cols:{len(months)};--colw:{44 if by_day else 76}px">
<div class="lane-row lane-head"><div class="lane-name"></div><div class="lane-track">{head_cells}</div></div>
{"".join(rows)}</div></div>
<div class="lane-readout" id="lane-readout" role="status" aria-live="polite"><span class="ph">滑過或用鍵盤選一個點，這裡會顯示那一則。</span></div>
<div class="lane-intro lane-intro-2"><h2>接下來發生了什麼</h2><p>同一批事件依時間排開，讀得到每一則在講什麼。</p></div>
<div class="tl-chrono">{"".join(chrono)}</div></section>"""
    return page_layout("timeline", "事件時間軸 — AI Pulse",
                       "已發布事件的時間軸：先看哪家公司在動，再看每一則的內容。",
                       body, 1, generated)

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
    stat = page_status([("剛抓到", len(signals)), ("來源", src_count), ("最新", latest)])
    toolbar = f"""<div class="sig-toolbar">
<label class="sig-search">{SEARCH}<input type="search" data-sig-q placeholder="搜尋標題或來源"></label>
<div class="sig-select"><select data-sig-kind aria-label="依來源類型篩選">{kind_opts}</select></div>
<div class="sig-select"><select data-sig-region aria-label="依地域篩選">{region_opts}</select></div>
<span class="sig-count" data-sig-count>{len(cards)} / {len(cards)}</span></div>"""
    body = f"""{hero("SOURCE UPDATES", "來源更新", "剛抓到、還沒驗過的線索。附原文連結是要你自己去看——驗過的才會進事件時間軸。", extra=stat, cls="compact")}
<section class="section section-tint"><div class="shell" data-sig>
{toolbar}
<div class="sig-stream">{''.join(cards)}</div>
<p class="sig-none" data-sig-none>沒有符合條件的更新。</p>
<button class="sig-more" type="button" data-sig-more>顯示更多</button>
</div></section>"""
    return page_layout("signals", "來源更新 — AI Pulse",
                       "剛抓到、還沒驗過的線索，附原文連結。",
                       body, 1, generated)


def build_event_page(ev, all_events, corpus_idx, sources, generated):
    pfx = "../../"
    tr = track_of(ev)
    layers = "".join(layer_html(h, ev["layers"][h], ev.get("independent"))
                     for h in LAYERS if ev["layers"].get(h))
    journey_heading, journey = journey_html(ev, corpus_idx, sources)
    scores = score_grid_html(ev)
    ev_links = "".join(f'<a href="{esc(e["url"])}" rel="noopener" target="_blank">{esc(e["sid"])} {EXT}</a>'
                       for e in ev["evidence"] if e.get("url"))
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
            # 證據帶著自己的 title / published，不只 (source_id, url)。只帶兩元組的話，
            # 發展歷程只能回頭查 `_corpus/`，而語料的保留期由 `corpus-累積` 那個
            # **還沒拍板的決定**控制——改成滾動視窗的那天，所有舊事件的證據標題會
            # 靜靜變成「未留存」。規格〈第三個現場〉把「不再依賴語料保留期」列為
            # 這一區的重點，而在此之前那句話是假的：欄位就在 frontmatter 裡，
            # 只是 render 讀進來的時候把它丟掉了。
            "evidence": [{"sid": e.get("source_id"), "url": e.get("url"),
                          "title": e.get("title"), "published": e.get("published")}
                         for e in (fm.get("evidence") or [])],
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
