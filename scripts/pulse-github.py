#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-github.py — GitHub 星速榜（開發者注意力的領先指標，純規則、零 LLM）。

答「GitHub 竄起什麼」：打 GitHub Search API 撈 AI 主題白名單的活躍 repo，
跨執行累積星數快照、算星速（Δstars / 天），排名輸出。星數是硬數字，不推斷。

  dist/data/github.json     竄起榜（repo / stars / 星速 / 語言 / 主題 / 連結 / 中文描述）
  dist/github/index.html    自帶「動能」視圖（讀 ../data/github.json）
  _github/state.json        star 快照歷史（跨次累積星速用；進版控）
  _github/desc-zh.json      中文描述儲存（潤稿端寫，本檔只讀；見 lib/ghdesc.py）

中文描述：repo 的 description 來自 API，是英文。翻譯屬於**敘述**不是判斷，所以由潤稿端
（pulse-github-desc-prep / -apply）寫，本檔只負責把驗過章的譯文掛回榜上。抓取鏈不等它——
沒有譯文就顯示英文原文，榜照樣出得來。原文永遠保留在 desc 欄且前台一併顯示。

紅線：抓取＋度量全確定性；API 失敗不炸整條鏈（沿用上次 github.json）。
用法：VAULT_DIR=/path/to/AI-Pulse GITHUB_TOKEN=... python scripts/pulse-github.py
依賴：requests, PyYAML。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from lib import ghdesc  # noqa: E402


def search_repos(keyword, cfg, token, cutoff_date):
    """回傳 GitHub Search repositories 結果（list）；任何失敗回 []（不炸鏈）。"""
    import requests
    q = f'{keyword} stars:>={cfg["min_stars"]} pushed:>{cutoff_date}'
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get("https://api.github.com/search/repositories",
                         params={"q": q, "sort": "stars", "order": "desc", "per_page": 40},
                         headers=headers, timeout=20)
        if r.status_code != 200:
            print(f"  [warn] search '{keyword}' HTTP {r.status_code}", file=sys.stderr)
            return []
        return r.json().get("items", [])
    except Exception as e:  # noqa: BLE001 — 抓取層任何錯誤都不該炸整條鏈
        print(f"  [warn] search '{keyword}' 失敗：{e}", file=sys.stderr)
        return []


def collect(cfg, token, now):
    from datetime import timedelta
    cutoff = (now - timedelta(days=cfg["active_days"])).strftime("%Y-%m-%d")
    excl = [x.lower() for x in (cfg.get("exclude") or [])]
    seen = {}
    for kw in cfg["keywords"]:
        for it in search_repos(kw, cfg, token, cutoff):
            full = it.get("full_name")
            if not full or full in seen:
                continue
            blob = f'{full} {it.get("description") or ""}'.lower()
            if any(x in blob for x in excl):
                continue
            seen[full] = {
                "full_name": full, "name": it.get("name"),
                "url": it.get("html_url"), "desc": (it.get("description") or "").strip(),
                "stars": it.get("stargazers_count", 0),
                "language": it.get("language") or "",
                "topics": (it.get("topics") or [])[:6],
                "created": (it.get("created_at") or "")[:10],
                "pushed": (it.get("pushed_at") or "")[:10],
            }
    return seen


def rank(current, state, now, top_n):
    """純函式：用 state 的上次快照算星速，排名。可離線單測。"""
    ranked = []
    now_ts = now.timestamp()
    for full, r in current.items():
        prev = state.get(full)
        delta = velocity = None
        is_new = prev is None
        if prev and prev.get("ts"):
            days = max((now_ts - prev["ts"]) / 86400.0, 0.5)
            delta = r["stars"] - prev.get("stars", r["stars"])
            velocity = round(delta / days, 1)
        r = dict(r, delta=delta, velocity=velocity, is_new=is_new)
        # 動能分：有歷史用星速；首次觀測用「星數/自建立天數」當代理，並打首觀標記
        if velocity is not None:
            r["momentum"] = velocity
        else:
            age = max((now - datetime.fromisoformat((r["created"] or "2020-01-01") + "T00:00:00+00:00")).days, 1)
            r["momentum"] = round(r["stars"] / age, 1)
        ranked.append(r)
    ranked.sort(key=lambda x: (x["momentum"] or 0, x["stars"]), reverse=True)
    return ranked[:top_n]


GH_VIEW = """<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitHub 動能 — AI Pulse</title>
<meta name="description" content="AI 主題 repo 星速榜：開發者最近在關注什麼的領先指標。星數＝注意力（不必然等於採用）。純規則、零 LLM。">
<meta name="color-scheme" content="dark light"><link rel="stylesheet" href="../assets/app.css">
<style>
.gh-wrap{padding:clamp(30px,5vw,52px) 0 clamp(60px,9vw,110px)}
.gh-note{color:var(--quiet);font:11px var(--mono);margin:0 0 18px}
.gh-row{display:grid;grid-template-columns:34px 1fr auto;gap:14px;align-items:baseline;padding:15px 4px;border-bottom:1px solid var(--border-soft)}
.gh-row:hover{background:var(--surface-soft)}
.gh-rank{font:600 15px var(--mono);color:var(--quiet);text-align:right}
.gh-main .n{font-size:1.05rem;font-weight:600;line-height:1.35}
.gh-main .n a{color:var(--text)}.gh-main .n a:hover{color:var(--accent)}
.gh-main .d{color:var(--muted);font-size:.9rem;margin:3px 0 0}
/* 原文一律留著。譯文是二手的，讀者要能一眼看到一手的那句。 */
.gh-main .d-src{color:var(--quiet);font:11px/1.5 var(--mono);margin:2px 0 0}
.gh-main .t{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}
.gh-tag{font:9px var(--mono);letter-spacing:.04em;padding:2px 7px;border-radius:5px;background:var(--surface-soft);color:var(--muted);border:1px solid var(--border-soft)}
.gh-new{color:var(--fact);border-color:color-mix(in srgb,var(--fact) 40%,var(--border))}
.gh-metric{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.gh-metric .v{font:700 16px var(--mono);color:var(--fact)}
.gh-metric .v.down{color:var(--muted)}
.gh-metric .s{display:block;color:var(--quiet);font:10px var(--mono);margin-top:2px}
.gh-none{color:var(--quiet);font:12px var(--mono);text-align:center;padding:40px}
</style></head><body data-page="github">
<header class="topbar">
<a class="brand" href="../" aria-label="AI Pulse 首頁"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><span><strong>AI PULSE</strong><small>0 LLM 判斷 · 去 AI 口吻</small></span></a>
<nav class="desktop-nav" aria-label="主導覽"><a href="../">關鍵變化</a><a href="../lines/">領域趨勢</a><a href="../timeline/">事件時間軸</a><a href="../signals/">來源更新</a><a href="../github/" aria-current="page">GitHub 動能</a></nav>
</header>
<main id="main"><section class="hero compact shell"><div><span class="kicker">DEVELOPER MOMENTUM · 星數＝注意力訊號 · 零 LLM</span><h1>GitHub 竄起什麼</h1><p>AI 主題 repo 的星速榜——開發者最近在關注什麼的領先指標，常比新聞早。注意：星數是<strong>注意力</strong>，不必然等於採用或重要性；星速＝跨執行的星數增量，純規則、可累積。</p></div></section>
<section class="gh-wrap shell">
<p class="gh-note" id="meta"></p>
<div id="list"></div>
<p class="gh-none" id="none" style="display:none">尚無資料（等第一次抓取後累積）。</p>
</section></main>
<script>
function esc(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
function fmt(n){return n>=1000?(n/1000).toFixed(1)+"k":(""+n);}
function row(r,i){
  var mv = r.velocity!=null ? (r.velocity>=0?"+":"")+r.velocity+"★/天"
        : "~"+r.momentum+"★/天";
  var cls = (r.velocity!=null && r.velocity<0)?" down":"";
  var tags=[r.language?('<span class="gh-tag">'+esc(r.language)+'</span>'):""]
      .concat((r.topics||[]).slice(0,3).map(t=>'<span class="gh-tag">'+esc(t)+'</span>'))
      .concat(r.is_new?'<span class="gh-tag gh-new">首次觀測</span>':"").join("");
  return '<div class="gh-row"><div class="gh-rank">'+(i+1)+'</div>'
    +'<div class="gh-main"><div class="n"><a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.full_name)+'</a></div>'
    +(r.desc_zh?'<div class="d">'+esc(r.desc_zh)+'</div>':"")
    +(r.desc?'<div class="'+(r.desc_zh?"d-src":"d")+'">'+esc(r.desc)+'</div>':"")
    +'<div class="t">'+tags+'</div></div>'
    +'<div class="gh-metric"><span class="v'+cls+'">'+esc(mv)+'</span><span class="s">'+fmt(r.stars)+' ★</span></div></div>';
}
function draw(d){
  var repos=d.repos||[];
  var zh=repos.filter(r=>r.desc_zh).length;
  document.getElementById("meta").textContent=(d.count||repos.length)+" 個 repo · 更新 "+(d.generated||"")
    +" · 中文描述 "+zh+"/"+repos.length+"（排名純規則；描述由潤稿端翻寫，英文原文一併保留）";
  document.getElementById("none").style.display=repos.length?"none":"block";
  document.getElementById("list").innerHTML=repos.map(row).join("");
}
fetch("../data/github.json").then(r=>r.json()).then(draw)
  .catch(()=>{document.getElementById("meta").textContent="github.json 載入失敗";});
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--snapshot", action="store_true",
                    help="更新 _github/state.json 星數快照（只在每晚跑一次，維持乾淨的 Δ/天）")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    cfg = yaml.safe_load((vault / "_config" / "github.yaml").read_text("utf-8"))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    now = datetime.now(timezone.utc)

    state_path = vault / "_github" / "state.json"
    state = json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}

    current = collect(cfg, token, now)
    generated = now.strftime("%Y-%m-%d %H:%MZ")

    out = vault / args.out
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "github").mkdir(parents=True, exist_ok=True)

    if not current:
        # 抓取全失敗：沿用上次 github.json，不覆寫成空、不炸鏈
        print("[warn] 本次未取得任何 repo（API 失敗或額度）——保留上次榜單", file=sys.stderr)
        if not (out / "data" / "github.json").exists():
            (out / "data" / "github.json").write_text(
                json.dumps({"generated": generated, "count": 0, "repos": []}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        (out / "github" / "index.html").write_text(GH_VIEW, encoding="utf-8")
        return 0

    ranked = rank(current, state, now, cfg.get("top_n", 25))
    # 掛上潤稿端翻好的中文描述。抓取鏈不等它、也不產生它——沒有就是英文原文，
    # 榜照樣出得來。中文晚一步到（潤稿任務比 Actions 晚三小時）是設計，不是缺陷。
    ghdesc.attach(ranked, ghdesc.load(vault))
    (out / "data" / "github.json").write_text(
        json.dumps({"generated": generated, "count": len(ranked), "repos": ranked},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "github" / "index.html").write_text(GH_VIEW, encoding="utf-8")

    # 更新快照（只在 --snapshot：每晚一次，維持乾淨的 Δ/天基線）；進版控
    if args.snapshot:
        state.update({full: {"stars": r["stars"], "ts": now.timestamp()} for full, r in current.items()})
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    n_new = sum(1 for r in ranked if r["is_new"])
    n_zh = sum(1 for r in ranked if r.get("desc_zh"))
    snap = " [snapshot 已更新]" if args.snapshot else ""
    print(f"pulse-github  抓到={len(current)}  上榜={len(ranked)}  首次觀測={n_new}  "
          f"中文描述={n_zh}/{len(ranked)}{snap}  → data/github.json + github/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
