#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-github.py — GitHub 星速榜（開發者注意力的領先指標，純規則、零 LLM）。

答「GitHub 竄起什麼」：打 GitHub Search API 撈 AI 主題白名單的活躍 repo，
跨執行累積星數快照、算星速（Δstars / 天），排名輸出。星數是硬數字，不推斷。

  dist/data/github.json     竄起榜（repo / stars / 星速 / 名次變動 / 語言 / 主題 / 連結 / 中文描述）
  dist/github/index.html    自帶「動能」視圖（讀 ../data/github.json）
  _github/state.json        star ＋名次快照歷史（跨次累積星速與名次變動用；進版控）
  _github/desc-zh.json      中文描述儲存（潤稿端寫，本檔只讀；見 lib/ghdesc.py）

中文描述：repo 的 description 來自 API，是英文。翻譯屬於**敘述**不是判斷，所以由潤稿端
（pulse-github-desc-prep / -apply）寫，本檔只負責把驗過章的譯文掛回榜上。抓取鏈不等它——
沒有譯文就顯示英文原文，榜照樣出得來。原文永遠保留在 desc 欄且前台一併顯示。

_github/state.json 的 schema（2026-08-01 起，每筆四個欄位）：

    "owner/repo": {"stars": 12345, "ts": 1785518099.1,
                   "rank_velocity": 3, "rank_surge": null}

前兩格是星速的基線，後兩格是名次變動的基線——**同一次快照寫的，所以兩個
數字回答的是同一個問句**：「跟上一次那一版榜單比」。分開存兩個時間點會讓頁面
上「▲3」與「+180★/天」量的是不同區間，而讀者沒有任何方式看得出來。

`rank_*` 三種值意義不同，缺一不可（見 rank_move()）：

    3      上一次快照時在這個榜的第 3 名
    null   上一次快照時**有量到這個 repo，但它不在這個榜上**（榜外）
    欄位不存在  上一次快照是舊 schema，根本沒記名次

遷移：舊 state.json 沒有這兩個欄位，第一次跑到這版碼時全榜都會落在「欄位不
存在」那一格，頁面印「沒有上一次名次可比」而不是假裝有變動。跑完第一次快照
就自己補齊，不需要 migration script。回滾：把這兩個欄位留在檔案裡無害——舊版
碼只讀 stars / ts，多的欄位會在下一次 state.update() 被整筆覆蓋掉。

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

from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib import ghdesc  # noqa: E402
from lib.atomicwrite import atomic_write_text  # noqa: E402  見 references/atomic-writes.md


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
    cutoff = clock.utc_date_str(now - timedelta(days=cfg["active_days"]))
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


# 竄升榜的最低基數。相對成長率在低基數上會爆掉：10 顆星變 20 顆就是 +100%，
# 沒有門檻的話那個榜會被剛開的空 repo 洗版，而「+100%/天」讀起來比任何真的
# 竄升都猛。門檻印在頁面上——一個沒有寫出來的門檻，跟沒有門檻一樣會誤導。
SURGE_FLOOR = 200


def rank_move(prev, key, now_rank):
    """名次變動：回 (move, places, prev_rank)。純函式，可離線單測。

    `prev` 是 state.json 裡這個 repo 的上一次快照（沒有就給 None），`key` 是
    `rank_velocity` 或 `rank_surge`，`now_rank` 是這一班算出來的名次。

    **六種狀態，沒有一種叫 0。** 這一格最容易壞的方式不是算錯，是把「量不到」
    跟「持平」印成同一個東西——榜上二十五列裡有一半是首次觀測的那天，一整排
    「─」看起來會像「今天大家都沒動」，而事實是今天根本沒有昨天可比。同一種
    形狀在這個 repo 已經抓過好幾次（未量測的因子印 0、抓不到榜的那一班寫 0），
    所以這裡把「不知道」拆成三種，各自有各自的圖示與說明：

      up          prev > now      上升 places 名
      down        prev < now      下降 places 名
      flat        prev == now     持平（places = 0，這個 0 是真的量到的 0）
      entered     prev 是 null    上次有量到這個 repo，但它不在這個榜上（榜外）
                                  → 一定是上升，但**上升幾名量不到**：榜外可能是
                                    第 26 名也可能是第 300 名。所以 places 給 None，
                                    不給一個看起來很具體的假數字。
      first_seen  prev 是 None    這個 repo 這一班第一次被觀測到，沒有上一次
      no_baseline 沒有那個欄位    上一次快照是舊 schema，沒記名次

    最後兩種在畫面上都是「沒有上一次名次可比」，但成因不同：first_seen 是這個
    repo 新，no_baseline 是這份資料新。分開存是為了讓「部署完第一天整榜都沒有
    箭頭」查得出原因——如果兩者共用一個值，那天看起來會像整批 repo 同時新出現。
    """
    if prev is None:
        return "first_seen", None, None
    if key not in prev:
        return "no_baseline", None, None
    prev_rank = prev[key]
    if prev_rank is None:
        return "entered", None, None
    if prev_rank > now_rank:
        return "up", prev_rank - now_rank, prev_rank
    if prev_rank < now_rank:
        return "down", now_rank - prev_rank, prev_rank
    return "flat", 0, prev_rank


def attach_rank_move(board, state, axis):
    """把某個榜的名次變動寫進那一批 dict（前台不必自己算，也不會兩邊算出不同答案）。

    兩個榜共用同一批 dict 物件（`rows` 只建一次），所以這裡的欄位一律帶軸名
    後綴——不帶的話竄升榜會蓋掉星速榜剛寫好的那一格，而畫面上兩邊都會顯示
    後寫的那一個。
    """
    key = f"rank_{axis}"
    for r in board:
        move, places, prev_rank = rank_move(state.get(r["full_name"]), key, r[key])
        r[f"rank_move_{axis}"] = move
        r[f"rank_places_{axis}"] = places
        r[f"rank_prev_{axis}"] = prev_rank


def rank(current, state, now, top_n):
    """純函式：用 state 的上次快照算兩軸，各排一次。可離線單測。

    **為什麼是兩軸。** 只有絕對星速（Δ★/天）的時候，榜永遠是大 repo 的榜——
    同樣一天，10 萬星的專案漲 200 顆很平常，2 千星的漲 200 顆是暴動，而排序看
    不出差別。那正是這個 repo 一直在抓的形狀：**用一個對大者有系統性優勢的
    指標，去代表「誰在竄」**。兩者在平常的日子重合，正好在有黑馬的那天分岔。

    所以拆成兩個**各自誠實**的軸，不合成一個分數：

      velocity  Δ★/天       誰吸走最多注意力（偏袒大 repo，這是它的定義不是缺陷）
      surge     Δ%/天       誰漲得最快（偏袒小 repo，所以設 SURGE_FLOOR）

    合成一個「動能分」等於再造一個代理指標，而權重要多少沒有人答得出來。
    兩個榜並排，讀者自己看得到同一個 repo 在兩邊的位置。

    **首次觀測不再給代理值。** 舊版拿「星數 ÷ 自建立以來的天數」當動能，那是
    **歷史平均**不是現在的速度：三年前開的 5000 星專案會拿到 4.5★/天 排進前段，
    而它這一週可能一顆都沒漲。兩點才有斜率，一點沒有——所以 velocity 留 None、
    排在最後，頁面標「首次觀測」。量不到就說量不到。

    **名次變動（rank_move_*）跟星速共用同一個基線。** 兩個榜各自算一次，比的是
    「上一次快照那一版榜單」——也就是 state.json 裡跟 stars 同一次寫進去的
    rank_velocity / rank_surge。不另外存一份「上一班的名次」：那會讓頁面上的
    ▲3 與 +180★/天 量的是不同區間，而讀者沒有任何方式看得出來。六種狀態與
    「量不到」為什麼要拆成三種，見 rank_move()。
    """
    rows = []
    now_ts = now.timestamp()
    for full, r in current.items():
        prev = state.get(full)
        delta = velocity = surge = None
        is_new = prev is None
        prev_stars = None
        if prev and prev.get("ts"):
            days = max((now_ts - prev["ts"]) / 86400.0, 0.5)
            prev_stars = prev.get("stars", r["stars"])
            delta = r["stars"] - prev_stars
            velocity = round(delta / days, 1)
            if prev_stars >= SURGE_FLOOR:
                surge = round(100.0 * delta / days / prev_stars, 2)
        rows.append(dict(r, delta=delta, velocity=velocity, surge=surge,
                         prev_stars=prev_stars, is_new=is_new))

    # 沒有速度的排最後（None 不參與比較），同分再看星數。
    by_velocity = sorted(rows, key=lambda x: (x["velocity"] is not None,
                                              x["velocity"] or 0, x["stars"]), reverse=True)
    by_surge = [x for x in rows if x["surge"] is not None]
    # 同分用名字破，不用星數：相對增量打平的時候，拿星數破等於把絕對軸的
    # 偏袒偷渡回相對軸——而這個榜存在的理由就是不要那個偏袒。名字是任意的，
    # 但至少不偏袒任何一種 repo，而且重跑會得到同一個順序。
    by_surge.sort(key=lambda x: (-x["surge"], x["full_name"]))

    top = by_velocity[:top_n]
    surge_top = by_surge[:top_n]
    # 兩榜的名次寫進同一批 dict，前台不必再算一次，也不會兩邊算出不同的名次。
    for i, x in enumerate(top):
        x["rank_velocity"] = i + 1
    for i, x in enumerate(surge_top):
        x["rank_surge"] = i + 1
    # 名次變動要在兩個榜的名次都寫完之後才算——attach 讀的是 r["rank_<axis>"]。
    attach_rank_move(top, state, "velocity")
    attach_rank_move(surge_top, state, "surge")
    return top, surge_top


def _render():
    """import pulse-render.py，借它的 page_layout。檔名有連字號，只能走 importlib。

    **為什麼不自己寫一份 HTML**：這一頁原本是一整份手抄的複本——自己的 topbar、
    自己的 `<style>`、自己的 hero。抄出來的東西會漂，而且已經漂了：

      - **手機上完全沒有導覽。** 共用版有 `.mobile-nav`，`@media(max-width:720px)`
        會把 `.desktop-nav` 藏起來；這一頁只抄了 desktop 那半。也就是說手機讀者
        進到這一頁之後，除了按上一頁沒有任何出路。
      - 沒有 footer、沒有深淺色切換、沒有跳至內容的 skip link。
      - 站頭還寫著「0 LLM 判斷 · 去 AI 口吻」、kicker 還寫著「零 LLM」——
        那兩句在別的四頁已經因為不精確被換掉了（敘述那一層是有潤稿的），
        只有這一頁沒跟上，因為它不經過 pulse-render。
      - 六個硬寫字級、零個級距 token。

    五頁裡有一頁是手抄的，就是「同一種東西長成兩套」在頁面層級的版本。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pulse_render", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "pulse-render.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gh_page(generated: str) -> str:
    r = _render()
    body = r.hero("", "GitHub 竄起什麼", "", cls="compact") + GH_BODY
    return r.page_layout("github", "GitHub 動能 — AI Pulse",
                         "AI 主題 repo 星速榜：開發者最近在關注什麼的領先指標。"
                         "星數＝注意力，不必然等於採用。",
                         body, 1, generated)


GH_BODY = """<section class="gh-wrap shell">
<p class="gh-note" id="meta"></p>
<p class="gh-legend" id="legend"></p>
<div class="gh-two">
  <div>
    <div class="col-head">星速榜 · 誰吸走最多注意力</div>
    <p class="gh-axis">絕對增量（★/天）。<b>這個軸偏袒大 repo</b>——同樣漲 200 顆，
    在 10 萬星的專案是日常，在 2 千星的是暴動。那是它的定義，不是缺陷。</p>
    <div id="list"></div>
  </div>
  <div>
    <div class="col-head">竄升榜 · 誰漲得最快</div>
    <p class="gh-axis">相對增量（%/天），<b id="floor"></b> 顆星以下不列——
    低基數的百分比會爆掉（10 顆變 20 顆就是 +100%），而那讀起來比任何真的竄升都猛。</p>
    <div id="surge"></div>
    <p class="gh-none" id="surge-none" style="display:none">還沒有第二次觀測，算不出相對增量。</p>
  </div>
</div>
<p class="gh-none" id="none" style="display:none">尚無資料（等第一次抓取後累積）。</p>
</section>
<script>

function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function fmt(n){return n>=1000?(n/1000).toFixed(1)+"k":(""+n);}

// 名次變動的圖示。走站上共用的 .ic 線條圖標（1em、currentColor、stroke），
// 不用實心三角形那類字元：它們在不同平台會被 emoji 字型接管，大小與基線都不受控，
// 而這一格就住在名次數字底下——歪一點點就整欄看起來像沒對齊。
// （這行註解會跟著 GH_BODY 一起送到頁面上，所以連舉例都不能把那幾個字打出來——
//   selftest 那條檢查是掃產出的頁面，它分不出「用了」跟「只是提到」。）
var MOVE_ICON={
  up:'<path d="M12 19V6M6 12l6-6 6 6"/>',
  down:'<path d="M12 5v13M6 12l6 6 6-6"/>',
  flat:'<path d="M5 12h14"/>',
  // 從榜外進來：一支往上的箭頭撞到一條線（榜的邊界）。
  entered:'<path d="M12 20V10M7 15l5-5 5 5M4 5h16"/>',
  // 量不到：同一條線改成**虛線**。站上「未量測」本來就是虛線（事件卡片那幾個
  // 沒量過的因子，軌道是虛線不填色），沿用同一個約定。
  // 第一版畫成「兩截短線」，在 11px 下跟 flat 那條實線只差一個缺口，
  // 兩者總寬還幾乎一樣——實線 / 虛線的對比看得出來，長短的對比看不出來。
  // 而「持平」跟「沒有可比的東西」長得像，就等於沒有這一格。
  first_seen:'<path d="M5 12h14" stroke-dasharray="2.5 3"/>',
  no_baseline:'<path d="M5 12h14" stroke-dasharray="2.5 3"/>'
};
function moveIcon(k){
  return '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'+MOVE_ICON[k]+'</svg>';
}
// 說明寫成完整句子，因為它同時是 aria-label：螢幕閱讀器聽到的只有這一句，
// 旁邊那個「#4」它讀不到上下文。
function moveText(r,axis){
  var mv=r["rank_move_"+axis], n=r["rank_places_"+axis],
      prev=r["rank_prev_"+axis], now=r["rank_"+axis];
  if(mv==="up")   return [""+n, "名次上升 "+n+" 名（上一版第 "+prev+" 名，這一版第 "+now+" 名）"];
  if(mv==="down") return [""+n, "名次下降 "+n+" 名（上一版第 "+prev+" 名，這一版第 "+now+" 名）"];
  if(mv==="flat") return ["",   "名次跟上一版一樣（第 "+now+" 名）"];
  if(mv==="entered")
    return ["新", "新進榜：上一版榜單上沒有它，所以一定是往上——但上升幾名量不到（榜外可能是第 26 名，也可能是第 300 名）"];
  if(mv==="first_seen")
    return ["", "沒有上一版名次可比：這個 repo 這一次才第一次被觀測到"];
  return ["", "沒有上一版名次可比：上一版榜單還沒有記名次，這一格從下一次更新開始才有值"];
}
function moveCell(r,axis){
  var mv=r["rank_move_"+axis];
  if(!mv) return "";                       // 舊的 github.json（沒有這幾個欄位）照樣畫得出來
  var t=moveText(r,axis);
  return '<span class="gh-move '+mv+'" role="img" title="'+esc(t[1])+'" aria-label="'+esc(t[1])+'">'
    +moveIcon(mv)+(t[0]?'<b>'+esc(t[0])+'</b>':"")+'</span>';
}
function row(r,i,axis){
  // 首次觀測沒有兩點就沒有斜率——印「首次觀測」不印一個算出來的數字。
  var mv, cls="";
  if(axis==="surge"){ mv = (r.surge>=0?"+":"")+r.surge+"%/天"; if(r.surge<0)cls=" down"; }
  else if(r.velocity!=null){ mv = (r.velocity>=0?"+":"")+r.velocity+"★/天"; if(r.velocity<0)cls=" down"; }
  else { mv = "首次觀測"; cls=" muted"; }
  var tags=[r.language?('<span class="gh-tag">'+esc(r.language)+'</span>'):""]
      .concat((r.topics||[]).slice(0,3).map(t=>'<span class="gh-tag">'+esc(t)+'</span>'))
      .concat(r.is_new?'<span class="gh-tag gh-new">首次觀測</span>':"").join("");
  // 另一個榜的名次：同一個 repo 兩邊都上，本身就是資訊。
  var other = axis==="surge" ? r.rank_velocity : r.rank_surge;
  var xref = other ? '<span class="gh-xref">'+(axis==="surge"?"星速":"竄升")+' #'+other+'</span>' : "";
  return '<div class="gh-row"><div class="gh-rank">'+(i+1)+moveCell(r,axis)+'</div>'
    +'<div class="gh-main"><div class="n"><a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.full_name)+'</a>'+xref+'</div>'
    +(r.desc_zh?'<div class="d">'+esc(r.desc_zh)+'</div>':"")
    +(r.desc?'<div class="'+(r.desc_zh?"d-src":"d")+'">'+esc(r.desc)+'</div>':"")
    +'<div class="t">'+tags+'</div></div>'
    +'<div class="gh-metric"><span class="v'+cls+'">'+esc(mv)+'</span><span class="s">'+fmt(r.stars)+' ★</span></div></div>';
}
function draw(d){
  var repos=d.repos||[], surging=d.surging||[];
  // 中文覆蓋率算**這一頁上有幾個不同的 repo**，不是算星速榜。只算星速榜的那一版，
  // 分母會小於畫面上的列數——分母比畫面窄，名字卻叫「中文描述」。
  var names={}, listed=0;
  repos.concat(surging).forEach(function(r){ if(!names[r.full_name]){names[r.full_name]=r; listed++;} });
  var zh=0; for(var k in names){ if(names[k].desc_zh) zh++; }
  document.getElementById("meta").textContent=listed+" 個 repo（兩個榜去重後）· 更新 "+(d.generated||"")
    +" · 中文描述 "+zh+"/"+listed+"（兩個榜都是純規則算的；描述由潤稿端翻寫，英文原文一併保留）";
  document.getElementById("floor").textContent = d.surge_floor!=null ? d.surge_floor : "—";
  document.getElementById("none").style.display=repos.length?"none":"block";
  document.getElementById("surge-none").style.display=surging.length?"none":"block";
  document.getElementById("list").innerHTML=repos.map((r,i)=>row(r,i,"velocity")).join("");
  document.getElementById("surge").innerHTML=surging.map((r,i)=>row(r,i,"surge")).join("");
}
// 圖例。**跟榜單共用同一份 MOVE_ICON**——圖例自己抄一套圖示，就是「同一種東西
// 長成兩套」的縮小版，而且圖例那一套不會有任何東西提醒你它已經跟榜上不一樣了。
// 一個沒有寫出來的判準跟沒有判準一樣會誤導，所以「跟哪一版比」也印在這裡。
document.getElementById("legend").innerHTML =
  '名次底下那一格＝跟<b>上一版榜單</b>比（榜單一天更新一次，跟 ★/天 同一把尺）：'
  + [["up","3","上升 3 名"],["down","2","下降 2 名"],["flat","","持平"],
     ["entered","新","新進榜（上一版不在這個榜上；上升幾名量不到）"],
     ["first_seen","","沒有上一版名次可比"]]
      .map(function(x){
        return '<span class="gh-leg"><span class="gh-move '+x[0]+'" aria-hidden="true">'
          +moveIcon(x[0])+(x[1]?'<b>'+x[1]+'</b>':"")+'</span>'+x[2]+'</span>';
      }).join("");
fetch("../data/github.json").then(r=>r.json()).then(draw)
  .catch(()=>{document.getElementById("meta").textContent="github.json 載入失敗";});
</script>"""



def write_desc_coverage(vault, now, ranked_n, with_zh_n):
    """把「榜上有幾條中文」寫成機器讀得到的一行。規格見 lib/ghdesc.py。

    走原子寫：下一班會讀回來算 `last_with_zh_day`，半份檔案會讓那個黏性欄位
    無聲歸零（references/atomic-writes.md 的分界線就是「壞掉之後會不會被當成
    事實讀回去」）。
    """
    day = clock.utc_date(now).isoformat()
    cov = ghdesc.next_coverage(ghdesc.load_coverage(vault), day, ranked_n,
                               with_zh_n, len(ghdesc.load(vault)))
    path = ghdesc.coverage_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(cov, ensure_ascii=False, indent=2) + "\n")
    return cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--snapshot", action="store_true",
                    help="更新 _github/state.json 星數快照（只在每晚跑一次，維持乾淨的 Δ/天）")
    ap.add_argument("--snapshot-if-older-than", type=float, default=None, metavar="HOURS",
                    help="只有當現有快照已舊過 N 小時才更新。給一天跑很多班的排程用。")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    cfg = yaml.safe_load((vault / "_config" / "github.yaml").read_text("utf-8"))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    now = datetime.now(timezone.utc)

    state_path = vault / "_github" / "state.json"
    state = json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}

    # 一天只跑一班時 --snapshot 就夠。一天跑很多班時它會班班覆蓋基線，而 rank() 的
    # days 有 max(..., 0.5) 下限——基線才隔兩小時，Δ 卻被除以半天，星速就變成一個
    # 看起來很正常的假數字。假數字比空欄危險，因為沒有人會去查它。
    #
    # 所以改讓「該不該更新基線」由快照自己的年紀決定，不由班次順序或時鐘判斷：
    # Actions 的 cron 是「最早不早於」，實測誤點過 96 分鐘，用 `date +%H` 判小時
    # 會在誤點那天整天不更新基線，而且一樣沒人會發現。
    do_snapshot = args.snapshot
    age_h = None
    if args.snapshot_if_older_than is not None:
        newest = max((v.get("ts") or 0) for v in state.values()) if state else 0
        age_h = (now.timestamp() - newest) / 3600.0 if newest else float("inf")
        do_snapshot = age_h >= args.snapshot_if_older_than

    current = collect(cfg, token, now)
    # 榜單頁把這個字串直接印給讀者看（上面那段 JS 的 `d.generated`），
    # 所以它走顯示層的時鐘、帶「台北時間」四個字。見 references/timezones.md。
    generated = clock.display_stamp(now)

    out = vault / args.out
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "github").mkdir(parents=True, exist_ok=True)

    if not current:
        # 抓取全失敗：沿用上次 github.json，不覆寫成空、不炸鏈
        print("[warn] 本次未取得任何 repo（API 失敗或額度）——保留上次榜單", file=sys.stderr)
        if not (out / "data" / "github.json").exists():
            # 佔位檔要標成「沒量到」。少了 measured 這一格，這份 0 條的榜單
            # 跟「今天真的沒有 repo 上榜」在下游眼裡一模一樣——
            # pulse-github-desc-prep 會照著回報「0 條待譯」，然後翻譯這件事
            # 就在沒有人知道的情況下停擺（紅線 8）。
            (out / "data" / "github.json").write_text(
                json.dumps({"generated": generated, "count": 0, "repos": [],
                            "measured": False}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        (out / "github" / "index.html").write_text(gh_page(generated), encoding="utf-8")
        # 這一班量不到榜單，但**中文有幾條照樣量得到**（那只是數檔案）。
        # 量不到的兩格寫 null，不寫 0（紅線 8）——寫 0 會讓「今天問不到 GitHub」
        # 看起來跟「今天榜上一條中文都沒有」一樣。
        write_desc_coverage(vault, now, None, None)
        return 0

    ranked, surging = rank(current, state, now, cfg.get("top_n", 25))
    # 掛上潤稿端翻好的中文描述。抓取鏈不等它、也不產生它——沒有就是英文原文，
    # 榜照樣出得來。中文晚一步到（潤稿任務比 Actions 晚三小時）是設計，不是缺陷。
    # 兩個榜都掛：同一個 repo 可能同時在兩邊，翻過的譯文要兩邊都看得到。
    ghdesc.attach(ranked, ghdesc.load(vault))
    ghdesc.attach(surging, ghdesc.load(vault))
    (out / "data" / "github.json").write_text(
        json.dumps({"generated": generated, "count": len(ranked), "repos": ranked,
                    "surging": surging, "surge_floor": SURGE_FLOOR,
                    "measured": True},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "github" / "index.html").write_text(gh_page(generated), encoding="utf-8")

    # 更新快照（一天一次，維持乾淨的 Δ/天基線）；進版控
    #
    # 名次跟星數同一次寫回，理由見模組 docstring 的 schema 段：兩個數字要回答
    # 同一個問句。**沒上榜的 repo 寫 null，不是不寫**——不寫的話下一班讀到的是
    # 「這個欄位不存在」，會被判成「舊 schema、量不到」，而事實是我們上次量過、
    # 它就是不在榜上。兩者在畫面上是不同的說法（見 rank_move()）。
    if do_snapshot:
        vel_rank = {r["full_name"]: r["rank_velocity"] for r in ranked}
        sur_rank = {r["full_name"]: r["rank_surge"] for r in surging}
        state.update({full: {"stars": r["stars"], "ts": now.timestamp(),
                             "rank_velocity": vel_rank.get(full),
                             "rank_surge": sur_rank.get(full)}
                      for full, r in current.items()})
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    n_new = sum(1 for r in ranked if r["is_new"])
    # 覆蓋率算**整頁**不算單一個榜。只算 ranked 的那一版，分母是星速榜的條數，
    # 而畫面上的列數是兩個榜去重後的——一個比事實窄的東西掛著事實的名字。
    listed = ghdesc.board_union(ranked, surging)
    n_zh = sum(1 for r in listed if r.get("desc_zh"))
    # 這個數字以前只印在 CI 的 log 裡：人看得到、機器讀不到，於是「這個榜已經
    # 連續幾天沒有中文」沒有任何地方存著。潤稿端的 C2 段失敗時**寫不進 repo**，
    # 所以觀測要住在會跑的這一邊。見 lib/ghdesc.py 的〈覆蓋率〉。
    write_desc_coverage(vault, now, len(listed), n_zh)
    if do_snapshot:
        snap = " [snapshot 已更新]"
    elif age_h is not None:
        snap = f" [snapshot 未更新：基線才 {age_h:.1f} 小時大，還沒到門檻]"
    else:
        snap = ""
    print(f"pulse-github  抓到={len(current)}  上榜={len(ranked)}＋竄升={len(surging)}"
          f"（去重 {len(listed)}）  首次觀測={n_new}  "
          f"中文描述={n_zh}/{len(listed)}{snap}  → data/github.json + github/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
