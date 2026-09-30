#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-github.py — GitHub 星速榜（開發者注意力的領先指標，純規則、零 LLM）。

答「GitHub 竄起什麼」：依 _config/github.yaml 六類分類的查詢打 GitHub Search API，撈 AI 主題的
活躍 repo，跨執行累積星數快照、算星速（Δstars / 天），排名輸出。星數是硬數字，不推斷。
兩榜按 tier_split 切開、每個 repo 恰好一個分類、每類另排分類榜；state.json 裡這次沒搜到的
已知 repo 用 GraphQL 補量：規格見 references/github-board.md〈體量切分〉〈分類〉〈候選池〉。

  dist/data/github.json     竄起榜（repo / stars / 星速 / 名次變動 / 語言 / 主題 / 連結 / 中文描述）
  dist/github/index.html    自帶「動能」視圖（讀 ../data/github.json）
  _github/state.json        star ＋名次快照歷史（跨次累積星速與名次變動用；進版控）
  _github/board.json        算好的榜（同 github.json，不含 desc_zh；只在快照有更新時寫；進版控）
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

兩個模式（規格與理由見 references/github-board.md）：

  抓取模式（預設，data-refresh 用）  快照有更新：打 Search、算榜、把榜寫進 _github/board.json；
                                     快照沒更新：不抓，出頁與 desc-coverage 取自現有 board.json
  --render-only（pages 用）          不打網路、不讀 token、不寫 state／desc-coverage；
                                     讀 board.json 掛譯文，出 github.json 與頁面

榜只在 data-refresh 算一次。pages 每次 push 都跑，重算的話基線是幾分鐘前的快照，
baseline_days 變 0.0、星速被 days 的 0.5 下限放大成 2×delta（2026-09-30 量到）。

紅線：抓取＋度量全確定性；API 失敗不炸整條鏈（沿用上次 github.json）。
用法：VAULT_DIR=/path/to/AI-Pulse GITHUB_TOKEN=... python scripts/pulse-github.py
      VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-github.py --render-only
依賴：requests, PyYAML。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib import ghdesc  # noqa: E402
from lib.atomicwrite import atomic_write_text  # noqa: E402  見 references/atomic-writes.md


# Search API 登入後上限每分鐘 30 次。每次之間至少隔這麼久，任何 60 秒的窗口最多 29 次。
SEARCH_GAP_S = 2.1
GRAPHQL_URL = "https://api.github.com/graphql"
GRAPHQL_BATCH = 100
# 剪枝要看的欄位：任一缺或是 null，那個 repo 這次當「不知道」（見 track_known）。
GRAPHQL_REQUIRED = ("nameWithOwner", "pushedAt", "isArchived")
# GraphQL 補量要的欄位。topics 取 first: 20（GitHub 一個 repo 的上限），分類要完整清單。
GRAPHQL_FIELDS = ("nameWithOwner stargazerCount description url primaryLanguage { name } "
                  "repositoryTopics(first: 20) { nodes { topic { name } } } "
                  "createdAt pushedAt isArchived")


def search_repos(q, token):
    """打一次 GitHub Search repositories。回 items（list）；失敗回 None，stderr 印一行。

    失敗回 None 不回 []：collect() 要分得出「這一次搜不到東西」跟「這一次沒問到」，
    全部都沒問到的那一晚不能當成一份榜（見 references/github-board.md〈候選池〉）。

    HTTP 200 也可能是失敗（PR #106 審查 F-2，使用者裁定）：`incomplete_results` 為真是
    GitHub 自己說這一次沒搜完；`items` 為空也算失敗——每個 query 都帶 stars:>= 與 pushed:>，
    正常的一晚不會是 0 筆，額度或索引出狀況時才會。算成功的話，30 次全空的那一晚會被當成
    「今天沒有 repo」，照樣補量出一份只有追蹤名單的榜。
    """
    import requests
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get("https://api.github.com/search/repositories",
                         params={"q": q, "sort": "stars", "order": "desc", "per_page": 40},
                         headers=headers, timeout=20)
        if r.status_code != 200:
            print(f"  [warn] search '{q}' HTTP {r.status_code}", file=sys.stderr)
            return None
        body = r.json()
    except Exception as e:  # noqa: BLE001 — 抓取層任何錯誤都不該炸整條鏈
        print(f"  [warn] search '{q}' 失敗：{e}", file=sys.stderr)
        return None
    if body.get("incomplete_results"):
        print(f"  [warn] search '{q}' incomplete_results 為真，這一次算失敗", file=sys.stderr)
        return None
    items = body.get("items") or []
    if not items:
        print(f"  [warn] search '{q}' HTTP 200 但 items 是空的，這一次算失敗", file=sys.stderr)
        return None
    return items


def graphql_query(names):
    """純函式：一批 owner/repo → 一份 GraphQL 查詢，每個 repo 一個別名 r0、r1……"""
    parts = []
    for i, full in enumerate(names):
        owner, _, repo = full.partition("/")
        parts.append(f"r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(repo)}) "
                     f"{{ {GRAPHQL_FIELDS} }}")
    return "query { " + " ".join(parts) + " }"


def parse_graphql(names, body):
    """純函式：GraphQL 回應 → {full_name: node 或 None}；整批失敗回 None。

    回傳裡的三種樣子意義不同，剪枝只認前兩種（見 references/github-board.md〈候選池〉）：

      node   查到了
      None   GitHub 明說查不到（別名是 null，錯誤型別 NOT_FOUND）——刪除或改名
      不在回傳裡  別名是 null 但錯誤不是 NOT_FOUND，或根本沒回這個別名——這次不知道

    回應沒有 data（或不是 object）就是整批失敗，一個都不能當成「確定」。
    errors 的 path 指到某個 rN 底下的欄位（例如 ["r3", "pushedAt"]，欄位級錯誤）時，rN 仍是
    dict 但那個欄位被置 null——那個 repo 這次也是「不知道」，不列（PR #106 審查 F-1）。
    """
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        return None
    data = body["data"]
    not_found, field_err = set(), set()
    for e in body.get("errors") or []:
        if not isinstance(e, dict) or not e.get("path"):
            continue
        path = [str(x) for x in e["path"]]
        if len(path) == 1 and e.get("type") == "NOT_FOUND":
            not_found.add(path[0])
        else:
            field_err.add(path[0])
    out = {}
    for i, full in enumerate(names):
        alias = f"r{i}"
        if alias in field_err:
            continue
        node = data.get(alias)
        if isinstance(node, dict):
            out[full] = node
        elif alias in not_found:
            out[full] = None
    return out


def graphql_repos(names, token):
    """打一次 GraphQL 補量（一批最多 GRAPHQL_BATCH 個）。回 parse_graphql 的結果；整批失敗回 None。"""
    if not token:
        print("  [warn] GraphQL 補量需要 token，這一批跳過（不剪任何 state）", file=sys.stderr)
        return None
    import requests
    try:
        r = requests.post(GRAPHQL_URL, json={"query": graphql_query(names)},
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code != 200:
            print(f"  [warn] GraphQL HTTP {r.status_code}（{len(names)} 個，不剪任何 state）",
                  file=sys.stderr)
            return None
        body = r.json()
    except Exception as e:  # noqa: BLE001 — 抓取層任何錯誤都不該炸整條鏈
        print(f"  [warn] GraphQL 失敗：{e}（{len(names)} 個，不剪任何 state）", file=sys.stderr)
        return None
    got = parse_graphql(names, body)
    if got is None:
        print(f"  [warn] GraphQL 回應沒有 data：{(body or {}).get('errors')}"
              f"（{len(names)} 個，不剪任何 state）", file=sys.stderr)
        return None
    unknown = len(names) - len(got)
    if unknown:
        print(f"  [warn] GraphQL 有 {unknown} 個沒有明確結果（不是 NOT_FOUND），這次不動它們",
              file=sys.stderr)
    return got


UNCLASSIFIED = "unclassified"


def classify(row, categories):
    """純函式：依清單順序，第一個 topics 跟 repo 的**完整** topics 有交集的類。都沒有回 unclassified。

    清單順序就是優先序（使用者裁定，見 references/github-board.md〈分類〉）：多類符合取第一類，
    所以一個 repo 恰好一個分類、只出現在一個分類頁。比對前兩邊都轉小寫。
    `row["topics"]` 必須是完整清單——呼叫端（pool_row）在截成顯示用的前 6 個**之前**呼叫。
    """
    have = {str(t).lower() for t in (row.get("topics") or [])}
    for c in categories:
        if have & {str(t).lower() for t in c["topics"]}:
            return c["id"]
    return UNCLASSIFIED


def pool_row(full, name, url, desc, stars, language, topics, created, pushed, categories):
    """候選池的一列（搜尋與 GraphQL 兩條路共用）。分類用完整 topics 做完，才截成顯示用的前 6 個。

    兩條路各自組 dict 的話，遲早有一條先截斷再分類：topic 排在第 7 個以後的 repo 就會
    在那一條路上變成 unclassified，而畫面上看不出它為什麼換了分類。
    """
    topics = list(topics or [])
    row = {"full_name": full, "name": name, "url": url, "desc": (desc or "").strip(),
           "stars": stars, "language": language or "", "topics": topics,
           "created": (created or "")[:10], "pushed": (pushed or "")[:10]}
    row["category"] = classify(row, categories)
    row["topics"] = topics[:6]
    return row


def excluded(full, desc, cfg):
    """標題或描述含 exclude 字樣（教材／清單類）就排除。"""
    blob = f'{full} {desc or ""}'.lower()
    return any(x.lower() in blob for x in (cfg.get("exclude") or []))


def collect(cfg, token, now, state):
    """候選池：每類每個 query 打兩次 Search，再用 GraphQL 補量 state 裡這次沒搜到的 repo。

    回 (池子 {full_name: row}, info)。info 是 stdout 那一行與剪枝要的量：
    search_calls（實際呼叫次數，含失敗）、search_failed、elapsed_s、graphql_filled、
    drop（GraphQL 確定不活躍、封存或查不到的 state repo，快照寫回時剪掉）。
    規格見 references/github-board.md〈候選池〉。
    """
    from datetime import timedelta
    t0 = time.monotonic()
    cutoff = clock.utc_date_str(now - timedelta(days=cfg["active_days"]))
    born = clock.utc_date_str(now - timedelta(days=cfg["new_repo_days"]))
    cats = cfg["categories"]
    seen = {}
    calls = failed = 0
    # 依分類順序、每類依 query 順序打；同一個 repo 只留第一次出現的那筆。找到它的是哪一類的
    # query 不影響它的分類（classify 只看 topics）。第二次專撈近 new_repo_days 天新建的：
    # 它們星數還小，在依星數排的前 40 名裡排不上。
    for cat in cats:
        for kw in cat["queries"]:
            base = f'{kw} stars:>={cfg["min_stars"]} pushed:>{cutoff}'
            for q in (base, f"{base} created:>{born}"):
                if calls:
                    time.sleep(SEARCH_GAP_S)
                calls += 1
                items = search_repos(q, token)
                if items is None:
                    failed += 1
                    continue
                for it in items:
                    full = it.get("full_name")
                    if not full or full in seen:
                        continue
                    if excluded(full, it.get("description"), cfg):
                        continue
                    if not isinstance(it.get("stargazers_count"), int):
                        # 星數是 null 的那一筆無效：進池的話 split_tiers 會丟 TypeError（PR #106 F-3）。
                        print(f"  [warn] search 結果 {full} 的 stargazers_count 是 "
                              f"{it.get('stargazers_count')!r}，這一筆不進池", file=sys.stderr)
                        continue
                    seen[full] = pool_row(
                        full, it.get("name"), it.get("html_url"), it.get("description"),
                        it["stargazers_count"], it.get("language"), it.get("topics"),
                        it.get("created_at"), it.get("pushed_at"), cats)
    info = {"search_calls": calls, "search_failed": failed, "graphql_filled": 0,
            "graphql_unknown": 0, "drop": []}
    if calls and failed == calls:
        # 一次都沒問到：只剩追蹤名單的池子不是這一晚的榜（新 repo 一個都不在），
        # 當成抓取全失敗，保留上一份 board.json。
        print(f"  [warn] Search {calls} 次全部失敗，這一班不補量、不出新榜", file=sys.stderr)
        info["elapsed_s"] = time.monotonic() - t0
        return {}, info
    filled, drop, unknown = track_known(state, seen, cfg, token, cutoff)
    seen.update(filled)
    info["graphql_filled"] = len(filled)
    info["graphql_unknown"] = unknown
    info["drop"] = drop
    info["elapsed_s"] = time.monotonic() - t0
    return seen, info


def track_known(state, seen, cfg, token, cutoff):
    """GraphQL 補量 state 裡這次沒被搜到的 repo。回 (補進池子的列 {full: row}, 要剪的名字 sorted list)。

    只有 GraphQL 明說了狀態的才算確定：封存、pushedAt 超過 active_days、查不到（NOT_FOUND）或
    改名（nameWithOwner 對不上）→ 剪；整批失敗或沒有明確結果 → 不進池子也不剪。
    補量的列不套 min_stars（已知的 repo 入池時已經過了門檻），exclude 照套。

    剪枝要看的欄位（nameWithOwner、pushedAt、isArchived）或 stargazerCount 缺或是 null：這個 repo
    這次也當「不知道」，不進池也不剪（PR #106 審查 F-1、F-3）。null 的 pushedAt 不是「45 天沒 push」，
    null 的 nameWithOwner 不是「改名」——讀成那樣，就是把一個活著的 repo 從 state 剪掉。

    回 (filled, drop, unknown)：unknown 是這次沒有明確結果的個數（整批失敗那一批全算），印在 stdout。
    """
    todo = sorted(k for k in state if k not in seen)
    filled, drop, unknown = {}, [], 0
    for i in range(0, len(todo), GRAPHQL_BATCH):
        batch = todo[i:i + GRAPHQL_BATCH]
        got = graphql_repos(batch, token)
        if got is None:
            unknown += len(batch)
            continue
        for full in batch:
            if full not in got:
                unknown += 1
                continue
            node = got[full]
            if node is not None:
                bad = [k for k in GRAPHQL_REQUIRED if node.get(k) is None]
                if not isinstance(node.get("stargazerCount"), int):
                    bad.append("stargazerCount")
                if bad:
                    print(f"  [warn] GraphQL {full} 的 {'、'.join(bad)} 缺或是 null，這次不知道（不進池、不剪）",
                          file=sys.stderr)
                    unknown += 1
                    continue
            if node is None or str(node.get("nameWithOwner") or "").lower() != full.lower():
                drop.append(full)
                continue
            if node.get("isArchived") or (node.get("pushedAt") or "")[:10] <= cutoff:
                drop.append(full)
                continue
            if excluded(full, node.get("description"), cfg):
                continue
            topics = [((n or {}).get("topic") or {}).get("name")
                      for n in ((node.get("repositoryTopics") or {}).get("nodes") or [])]
            filled[full] = pool_row(
                full, full.partition("/")[2], node.get("url"), node.get("description"),
                node["stargazerCount"], (node.get("primaryLanguage") or {}).get("name"),
                [t for t in topics if t], node.get("createdAt"), node.get("pushedAt"),
                cfg["categories"])
    return filled, sorted(drop), unknown


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


def rank(current, state, now, top_n, tier_split):
    """純函式：用 state 的上次快照算兩軸，按體量切成兩個榜，各排一次。可離線單測。

    **按體量切（2026-09-30）。** 星速榜只收這一次 `stars >= tier_split` 的 repo，
    竄升榜只收 `stars < tier_split` 的（仍要上一版 >= SURGE_FLOOR）。兩榜因此不相交，
    以前那一格「另一個榜的名次」就沒有東西可標了。規格與代價見
    references/github-board.md〈體量切分〉。

    **為什麼是兩軸。** 只有絕對星速（Δ★/天）的時候，榜永遠是大 repo 的榜——
    同樣一天，10 萬星的專案漲 200 顆很平常，2 千星的漲 200 顆是暴動，而排序看
    不出差別。那正是這個 repo 一直在抓的形狀：**用一個對大者有系統性優勢的
    指標，去代表「誰在竄」**。兩者在平常的日子重合，正好在有黑馬的那天分岔。

    所以拆成兩個**各自誠實**的軸，不合成一個分數：

      velocity  Δ★/天       誰吸走最多注意力（偏袒大 repo，這是它的定義不是缺陷）
      surge     Δ%/天       誰漲得最快（偏袒小 repo，所以設 SURGE_FLOOR）

    合成一個「動能分」等於再造一個代理指標，而權重要多少沒有人答得出來。
    兩個榜並排；2026-09-30 起按體量切開，大 repo 在星速榜、小 repo 在竄升榜，不再重疊。

    **首次觀測不再給代理值。** 舊版拿「星數 ÷ 自建立以來的天數」當動能，那是
    **歷史平均**不是現在的速度：三年前開的 5000 星專案會拿到 4.5★/天 排進前段，
    而它這一週可能一顆都沒漲。兩點才有斜率，一點沒有——所以 velocity 留 None、
    排在最後，頁面標「首次觀測」。量不到就說量不到。

    **名次變動（rank_move_*）跟星速共用同一個基線。** 兩個榜各自算一次，比的是
    「上一次快照那一版榜單」——也就是 state.json 裡跟 stars 同一次寫進去的
    rank_velocity / rank_surge。不另外存一份「上一班的名次」：那會讓頁面上的
    ▲3 與 +180★/天 量的是不同區間，而讀者沒有任何方式看得出來。六種狀態與
    「量不到」為什麼要拆成三種，見 rank_move()。

    **但同一個基線不等於同一把尺，而 baseline_days 就是為了說出這件事。**
    星速除以實際天數（`days`），所以它是「每天」的量；名次位移**沒有除以任何
    東西**，它是「這段區間」的量。兩者在每晚都抓得到的 repo 上看起來一樣，
    正好在基線舊掉的那幾條上分岔——而那不是理論值：state.json 每晚有幾條
    沒被搜到（實測 2026-07-26～31 每班 1～6 條），它們的基線就這樣一天一天
    變老。實測 07-31 那一班之後的分佈是 224 條 0 天、其餘 1／2／5／6 天。

    一個 repo 掉出關鍵字搜尋六天再回來，箭頭上的「3」是**六天**的位移。頁面
    第一版的圖例寫著「榜單一天更新一次，跟 ★/天 同一把尺」——那句話對榜是對的
    （榜確實每晚重畫），對這支箭頭是錯的。所以每一列都帶自己的 baseline_days，
    圖例改口說「隔了幾天每一列不一樣」，tooltip 印出那一列真正的天數。

    baseline_days 只是**顯示**用，不參與任何排序或門檻——名次位移刻意不做
    「除以天數」的正規化：那會生出一個「每天位移 0.5 名」的東西，而名次是序數，
    序數的每日平均沒有意義。量到幾天就說幾天，不換算。
    """
    rows = measure(current, state, now)
    by_velocity, by_surge = split_tiers(rows, tier_split)
    top = by_velocity[:top_n]
    surge_top = by_surge[:top_n]
    # 兩榜的名次寫進各自那一批 dict，前台不必再算一次。
    for i, x in enumerate(top):
        x["rank_velocity"] = i + 1
    for i, x in enumerate(surge_top):
        x["rank_surge"] = i + 1
    # 名次變動要在名次寫完之後才算——attach 讀的是 r["rank_<axis>"]。
    attach_rank_move(top, state, "velocity")
    attach_rank_move(surge_top, state, "surge")
    return top, surge_top


def measure(current, state, now):
    """純函式：每個 repo 對上一版快照算 delta／velocity／surge／baseline_days。回一批新的 dict。

    每呼叫一次就是一批新的 dict：全部榜與分類榜各自呼叫，分類榜的列才不會帶到全部榜寫的
    名次欄（分類榜不算名次變動，見 rank_categories()）。
    """
    rows = []
    now_ts = now.timestamp()
    for full, r in current.items():
        prev = state.get(full)
        delta = velocity = surge = None
        is_new = prev is None
        prev_stars = baseline_days = None
        if prev and prev.get("ts"):
            days = max((now_ts - prev["ts"]) / 86400.0, 0.5)
            # 給讀者看的是**沒有下限**的那個年紀。`days` 的 0.5 是除法的護欄
            # （一天跑很多班時不讓 Δ 被除進一個假的大數字），拿它當「隔了幾天」
            # 印出去，就會在同一天跑第二班時對讀者說「跟半天前那一版比」——
            # 而基線其實是昨天的。護欄跟事實不是同一個數字。
            baseline_days = round((now_ts - prev["ts"]) / 86400.0, 1)
            prev_stars = prev.get("stars", r["stars"])
            delta = r["stars"] - prev_stars
            velocity = round(delta / days, 1)
            if prev_stars >= SURGE_FLOOR:
                surge = round(100.0 * delta / days / prev_stars, 2)
        rows.append(dict(r, delta=delta, velocity=velocity, surge=surge,
                         prev_stars=prev_stars, is_new=is_new,
                         baseline_days=baseline_days))
    return rows


def rank_categories(current, state, now, categories, tier_split, top_n):
    """純函式：每一類在自己的池子內各排兩榜 top_n 名，依設定順序。回 [{id, name, repos, surging}]。

    **同樣套 tier_split**（split_tiers 同一支），所以分類頁的兩榜也不相交。
    **分類榜不算名次變動**：state.json 只存全部榜的名次，分類榜的名次沒有上一版可比。
    所以這裡用 measure() 另算一批 dict，不共用全部榜那一批——共用的話，全部榜寫進去的
    rank_* 欄會跟著出現在分類榜上，前台會在分類頁畫出一個量的是別的榜的箭頭。
    unclassified 不是分類頁，只在全部榜出現。
    """
    rows = measure(current, state, now)
    out = []
    for c in categories:
        mine = [r for r in rows if r["category"] == c["id"]]
        by_velocity, by_surge = split_tiers(mine, tier_split)
        out.append({"id": c["id"], "name": c["name"],
                    "repos": by_velocity[:top_n], "surging": by_surge[:top_n]})
    return out


def split_tiers(rows, tier_split):
    """純函式：按這一次的星數切兩個池、各自排序。回 (星速榜排序, 竄升榜排序)，都還沒截斷。

    用**這一次**的 stars 切：同一列只有一個 stars，所以兩邊一定不相交。全部榜與每個分類榜
    都走這一支，切法只有一份。
    """
    big = [x for x in rows if x["stars"] >= tier_split]
    small = [x for x in rows if x["stars"] < tier_split]
    # 沒有速度的排最後（None 不參與比較），同分再看星數。
    by_velocity = sorted(big, key=lambda x: (x["velocity"] is not None,
                                             x["velocity"] or 0, x["stars"]), reverse=True)
    by_surge = [x for x in small if x["surge"] is not None]
    # 同分用名字破，不用星數：相對增量打平的時候，拿星數破等於把絕對軸的
    # 偏袒偷渡回相對軸——而這個榜存在的理由就是不要那個偏袒。名字是任意的，
    # 但至少不偏袒任何一種 repo，而且重跑會得到同一個順序。
    by_surge.sort(key=lambda x: (-x["surge"], x["full_name"]))
    return by_velocity, by_surge


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


def gh_tabs(categories):
    """上方分頁：「全部」加每一類（依 board 的 categories 順序）。出頁時寫進 HTML。

    分頁從 board 來、不從設定檔來：--render-only 只讀 board.json，頁面上的分頁要跟那份資料
    同一個來源，不然設定檔改了而 board 還沒重算的那幾個小時，會有點了沒有資料的分頁。
    """
    import html
    tabs = [("all", "全部")] + [(c["id"], c["name"]) for c in categories]
    out = []
    for i, (cid, name) in enumerate(tabs):
        sel = "true" if i == 0 else "false"
        cls = ' class="active"' if i == 0 else ""
        out.append(f'<button type="button" role="tab" data-cat="{html.escape(cid)}" '
                   f'aria-selected="{sel}"{cls}>{html.escape(name)}</button>')
    return ('<div class="chip-row" id="tabs" role="tablist" aria-label="分類">'
            + "".join(out) + "</div>")


def gh_page(generated: str, categories) -> str:
    r = _render()
    body = (r.hero("", "GitHub 竄起什麼", "", cls="compact")
            + GH_BODY.replace("<!--gh-tabs-->", gh_tabs(categories), 1))
    return r.page_layout("github", "GitHub 動能 — AI Pulse",
                         "AI 主題 repo 星速榜：開發者最近在關注什麼的領先指標。"
                         "星數＝注意力，不必然等於採用。",
                         body, 1, generated)


GH_BODY = """<section class="gh-wrap shell">
<p class="gh-note" id="meta"></p>
<!--gh-tabs-->
<p class="gh-legend" id="legend"></p>
<p class="gh-axis" id="cat-note" style="display:none">分類頁：這一類自己的池子重排的兩榜，
同樣按 <b class="tier"></b> 顆星切開。分類榜不算名次變動（只有「全部」有上一版名次可比），
名次底下那一格不畫。</p>
<div class="gh-two">
  <div>
    <div class="col-head">星速榜 · 誰吸走最多注意力</div>
    <p class="gh-axis">絕對增量（★/天），只收 <b class="tier"></b> 顆星以上的 repo。
    <b>這個軸偏袒大 repo</b>——同樣漲 200 顆，在 10 萬星的專案是日常，在 2 千星的是暴動。
    那是它的定義，不是缺陷，所以小於門檻的 repo 改在竄升榜比。</p>
    <div id="list"></div>
  </div>
  <div>
    <div class="col-head">竄升榜 · 誰漲得最快</div>
    <p class="gh-axis">相對增量（%/天），只收 <b class="tier"></b> 顆星以下的 repo，
    上一版 <b id="floor"></b> 顆星以下不列——低基數的百分比會爆掉（10 顆變 20 顆就是 +100%），
    而那讀起來比任何真的竄升都猛。</p>
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
// 「上一版是幾天前」——**每一列不一樣**，所以只能一列一列印，不能寫在圖例上。
// 每晚都有幾條 repo 沒被搜到，它們的基線就這樣一天一天變老；那些 repo 回來上榜
// 時，箭頭上的數字是那幾天的位移，不是昨天的。
function ageText(r){
  var d=r.baseline_days;
  if(d==null) return "";
  var s=(d%1===0)?d:d.toFixed(1);
  return "；上一版是 "+s+" 天前";
}
// 說明寫成完整句子，因為它同時是 aria-label：螢幕閱讀器聽到的只有這一句，
// 旁邊那個「#4」它讀不到上下文。
function moveText(r,axis){
  var mv=r["rank_move_"+axis], n=r["rank_places_"+axis],
      prev=r["rank_prev_"+axis], now=r["rank_"+axis], age=ageText(r);
  if(mv==="up")   return [""+n, "名次上升 "+n+" 名（上一版第 "+prev+" 名，這一版第 "+now+" 名"+age+"）"];
  if(mv==="down") return [""+n, "名次下降 "+n+" 名（上一版第 "+prev+" 名，這一版第 "+now+" 名"+age+"）"];
  if(mv==="flat") return ["",   "名次跟上一版一樣（第 "+now+" 名"+age+"）"];
  if(mv==="entered")
    return ["新", "新進榜：上一版榜單上沒有它，所以一定是往上——但上升幾名量不到（榜外可能是第 26 名，也可能是第 300 名"+age+"）"];
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
  var tags=[r.category?('<span class="gh-tag">'+esc(catName(r.category))+'</span>'):"",
            r.language?('<span class="gh-tag">'+esc(r.language)+'</span>'):""]
      .concat((r.topics||[]).slice(0,3).map(t=>'<span class="gh-tag">'+esc(t)+'</span>'))
      .concat(r.is_new?'<span class="gh-tag gh-new">首次觀測</span>':"").join("");
  // 兩榜按體量切開、不再重疊（tier_split），所以不標「另一個榜的名次」。
  return '<div class="gh-row"><div class="gh-rank">'+(i+1)+moveCell(r,axis)+'</div>'
    +'<div class="gh-main"><div class="n"><a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.full_name)+'</a></div>'
    +(r.desc_zh?'<div class="d">'+esc(r.desc_zh)+'</div>':"")
    +(r.desc?'<div class="'+(r.desc_zh?"d-src":"d")+'">'+esc(r.desc)+'</div>':"")
    +'<div class="t">'+tags+'</div></div>'
    +'<div class="gh-metric"><span class="v'+cls+'">'+esc(mv)+'</span><span class="s">'+fmt(r.stars)+' ★</span></div></div>';
}
var D=null;
// 分類標籤。unclassified 不是一個分類頁，只在「全部」出現，標籤寫「未分類」。
function catName(id){
  if(id==="unclassified") return "未分類";
  var c=((D&&D.categories)||[]).filter(function(x){return x.id===id;})[0];
  return c ? c.name : id;
}
// 整頁的每一個榜：全部榜的兩榜，加每一類的兩榜。跟 lib/ghdesc.doc_boards 同一個範圍。
function allBoards(d){
  var b=[d.repos||[], d.surging||[]];
  (d.categories||[]).forEach(function(c){ b.push(c.repos||[], c.surging||[]); });
  return b;
}
function emptyNote(t){ return '<p class="gh-none">'+esc(t)+'</p>'; }
function view(id){
  var cat=(D.categories||[]).filter(function(x){return x.id===id;})[0];
  var isAll=(id==="all");
  var repos=isAll ? (D.repos||[]) : (cat ? cat.repos||[] : []);
  var surging=isAll ? (D.surging||[]) : (cat ? cat.surging||[] : []);
  document.querySelectorAll("#tabs button").forEach(function(b){
    var on=b.getAttribute("data-cat")===id;
    b.classList.toggle("active",on); b.setAttribute("aria-selected",on?"true":"false"); });
  document.getElementById("legend").style.display=isAll?"":"none";
  document.getElementById("cat-note").style.display=isAll?"none":"block";
  document.getElementById("none").style.display=(isAll&&!repos.length)?"block":"none";
  document.getElementById("surge-none").style.display=(isAll&&!surging.length)?"block":"none";
  var miss = cat ? "這一類這一版沒有夠格的 repo。" : "這一版的榜單沒有這一類的資料。";
  document.getElementById("list").innerHTML = (!isAll&&!repos.length) ? emptyNote(miss)
    : repos.map((r,i)=>row(r,i,"velocity")).join("");
  document.getElementById("surge").innerHTML = (!isAll&&!surging.length) ? emptyNote(miss)
    : surging.map((r,i)=>row(r,i,"surge")).join("");
}
function draw(d){
  D=d;
  // 中文覆蓋率算**這一頁上有幾個不同的 repo**：全部榜與分類榜去重後。只算星速榜的那一版，
  // 分母會小於畫面上的列數——分母比畫面窄，名字卻叫「中文描述」。分類榜也一樣：
  // 某一類的第 3 名可能排不進全部榜，它也是畫面上的一列。
  var names={}, listed=0;
  allBoards(d).forEach(function(b){ b.forEach(function(r){
    if(!names[r.full_name]){names[r.full_name]=r; listed++;} }); });
  var zh=0; for(var k in names){ if(names[k].desc_zh) zh++; }
  document.getElementById("meta").textContent=listed+" 個 repo（全部榜與分類榜去重後）· 更新 "+(d.generated||"")
    +" · 中文描述 "+zh+"/"+listed+"（榜都是純規則算的；描述由潤稿端翻寫，英文原文一併保留）";
  document.getElementById("floor").textContent = d.surge_floor!=null ? d.surge_floor : "—";
  // 切分門檻從 github.json 讀，不在頁面寫死：設定檔改了，頁面上的字要跟著變。
  document.querySelectorAll(".tier").forEach(function(el){
    el.textContent = d.tier_split!=null ? d.tier_split : "—"; });
  view("all");
}
document.querySelectorAll("#tabs button").forEach(function(b){
  b.addEventListener("click", function(){ if(D) view(b.getAttribute("data-cat")); });
});
// 圖例。**跟榜單共用同一份 MOVE_ICON**——圖例自己抄一套圖示，就是「同一種東西
// 長成兩套」的縮小版，而且圖例那一套不會有任何東西提醒你它已經跟榜上不一樣了。
// 一個沒有寫出來的判準跟沒有判準一樣會誤導，所以「跟哪一版比」也印在這裡。
//
// 這句話的第一版是「榜單一天更新一次，跟 ★/天 同一把尺」。前半對（榜確實每晚
// 重畫），後半是假的：★/天 除以實際天數、名次位移沒有除以任何東西，而每晚都有
// 幾條 repo 沒被搜到、基線就這樣變老。所以圖例不再宣稱任何節奏——天數是每一列
// 自己的事，印在那一列的 tooltip 裡。
document.getElementById("legend").innerHTML =
  '名次底下那一格＝跟這個 repo <b>上一次入榜的那一版</b>比。隔了幾天每一列不一樣'
  + '（滑過去看），所以它不是「每天」的位移——跟 ★/天 不是同一把尺：'
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


BOARD_REL = ("_github", "board.json")


def board_path(vault):
    return Path(vault).joinpath(*BOARD_REL)


PLACEHOLDER_MARK = "（佔位頁：尚無榜單）"


class BoardError(Exception):
    """board.json 存在但壞了（不是合法 JSON、不是 object、缺 repos、缺 generated）。訊息帶路徑。"""


def load_board(vault):
    """讀 _github/board.json；不存在回 None，壞掉 raise BoardError。"""
    bp = board_path(vault)
    if not bp.exists():
        return None
    try:
        board = json.loads(bp.read_text("utf-8"))
    except ValueError as e:
        raise BoardError(f"{bp} 不是合法 JSON：{e}")
    if not isinstance(board, dict) or not isinstance(board.get("repos"), list):
        raise BoardError(f"{bp} 缺 repos（或不是 JSON object）")
    if not isinstance(board.get("generated"), str):
        raise BoardError(f"{bp} 缺 generated（頁面的更新時間要用它）")
    return board


def emit_board(vault, out_dir, now):
    """讀 board.json、掛譯文、寫 dist/data/github.json 與頁面。回 (doc, 有沒有 board)。

    **--render-only 與「抓取模式但快照沒更新」共用這一份碼**：兩者出的頁都必須是線上
    顯示的那份榜（board.json），desc-prep 讀的 dist/data/github.json 與 desc-coverage
    量的也是它。分成兩份碼，就會各自漂成量不同的榜。
    board.json 不存在寫 measured:false 佔位（stderr 印一行）；壞掉 raise BoardError，
    不寫任何輸出。
    """
    board = load_board(vault)
    out = Path(vault) / out_dir
    if board is not None:
        store = ghdesc.load(vault)
        # 全部榜與每一類的兩榜都掛：分類榜上有全部榜沒有的 repo（見 ghdesc.doc_boards）。
        for rows in ghdesc.doc_boards(board):
            ghdesc.attach(rows, store)
        doc = board
        # 頁面的「更新」時間是榜算出來的那一刻（board 的 generated），不是出頁當下：
        # 資料是舊的、時間卻是新的，同一頁就有兩個時間，讀者會以為榜剛更新。
        page_stamp = board["generated"]
    else:
        print(f"[warn] {board_path(vault)} 不存在——寫 measured:false 佔位"
              "（等 data-refresh 寫出第一份）", file=sys.stderr)
        doc = {"generated": clock.display_stamp(now), "count": 0, "repos": [],
               "measured": False}
        # 佔位頁沒有榜的時間可沿用，只能用當下；但要寫明那是佔位，不是榜的時間。
        page_stamp = doc["generated"] + PLACEHOLDER_MARK
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "github").mkdir(parents=True, exist_ok=True)
    (out / "data" / "github.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    # 舊版（T1 那一版）的 board.json 沒有 categories：分頁只剩「全部」，不是錯誤。
    (out / "github" / "index.html").write_text(
        gh_page(page_stamp, doc.get("categories") or []), encoding="utf-8")
    return doc, board is not None


def render_only(vault, out_dir):
    """pages 用：只讀 _github/board.json，掛譯文，出 github.json 與頁面。

    不打網路、不讀 token、不寫 state.json 與 desc-coverage.json——榜在 data-refresh
    算過一次了，這裡再算就是 baseline_days 0.0 那個 bug（見 references/github-board.md）。
    board.json 不存在寫 measured:false 佔位（exit 0）；壞掉（不是 JSON、不是 object、
    缺 repos、缺 generated）exit 2 並帶路徑，不寫任何輸出。
    """
    try:
        doc, present = emit_board(vault, out_dir, datetime.now(timezone.utc))
    except BoardError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    if present:
        print(f"pulse-github --render-only  榜={len(doc['repos'])}"
              f"＋竄升={len(doc.get('surging') or [])}  "
              f"generated={doc.get('generated')}  → data/github.json + github/")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--snapshot", action="store_true",
                    help="更新 _github/state.json 星數快照（只在每晚跑一次，維持乾淨的 Δ/天）")
    ap.add_argument("--snapshot-if-older-than", type=float, default=None, metavar="HOURS",
                    help="只有當現有快照已舊過 N 小時才更新。給一天跑很多班的排程用。")
    ap.add_argument("--render-only", action="store_true",
                    help="不抓、不算：讀 _github/board.json 掛譯文後出頁（pages 用）。")
    args = ap.parse_args()
    if args.render_only and (args.snapshot or args.snapshot_if_older_than is not None):
        ap.error("--render-only 不能與 --snapshot／--snapshot-if-older-than 併用")
    vault = Path(os.environ["VAULT_DIR"])
    if args.render_only:
        return render_only(vault, args.out)
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

    if not do_snapshot:
        # 快照沒更新：這一班不重排榜。用年輕基線重排的那份榜線上不會顯示，而同一班的
        # desc-prep 與 write_desc_coverage 都讀 dist/data/github.json——量到的會是一份
        # 沒人看得到的榜。所以出頁與覆蓋率一律取自現有 board.json（線上那份），也不必抓。
        try:
            doc, present = emit_board(vault, args.out, now)
        except BoardError as e:
            print(f"[error] {e}", file=sys.stderr)
            return 2
        why = (f"基線才 {age_h:.1f} 小時大，還沒到門檻" if age_h is not None
               else "沒有快照旗標")
        if present:
            listed = ghdesc.doc_union(doc)
            n_zh = sum(1 for r in listed if r.get("desc_zh"))
            write_desc_coverage(vault, now, len(listed), n_zh)
            print(f"pulse-github  快照沒更新，不抓；出頁取自 _github/board.json"
                  f"（generated={doc.get('generated')}，榜={len(doc['repos'])}"
                  f"＋竄升={len(doc.get('surging') or [])}，去重 {len(listed)}）  "
                  f"中文描述={n_zh}/{len(listed)}  [snapshot 未更新：{why}，board.json 未更新]"
                  "  → data/github.json + github/")
        else:
            # 沒有 board 可取：兩格寫 null，不寫 0（沿用抓取全失敗那條路的語意）。
            write_desc_coverage(vault, now, ranked_n=None, with_zh_n=None)
            print(f"pulse-github  快照沒更新，不抓；_github/board.json 不存在，出 measured:false 佔位"
                  f"  [snapshot 未更新：{why}，board.json 未更新]  → data/github.json + github/")
        return 0

    current, info = collect(cfg, token, now, state)
    cost = (f"Search {info['search_calls']} 次、耗時 {info['elapsed_s']:.0f} 秒、"
            f"GraphQL 補量 {info['graphql_filled']} 個")
    # 榜單頁把這個字串直接印給讀者看（上面那段 JS 的 `d.generated`），
    # 所以它走顯示層的時鐘、帶「台北時間」四個字。見 references/timezones.md。
    generated = clock.display_stamp(now)

    out = vault / args.out
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "github").mkdir(parents=True, exist_ok=True)

    if not current:
        # 抓取全失敗：沿用上次 github.json，不覆寫成空、不炸鏈
        print("[warn] 本次未取得任何 repo（API 失敗或額度）——保留上次榜單", file=sys.stderr)
        print(f"pulse-github  抓取全失敗，board.json 未更新  {cost}"
              f"（Search 失敗 {info['search_failed']} 次）")
        if not (out / "data" / "github.json").exists():
            # 佔位檔要標成「沒量到」。少了 measured 這一格，這份 0 條的榜單
            # 跟「今天真的沒有 repo 上榜」在下游眼裡一模一樣——
            # pulse-github-desc-prep 會照著回報「0 條待譯」，然後翻譯這件事
            # 就在沒有人知道的情況下停擺（紅線 8）。
            (out / "data" / "github.json").write_text(
                json.dumps({"generated": generated, "count": 0, "repos": [],
                            "measured": False}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        # 這一班沒有新榜；分頁照設定檔的分類畫（這份 dist 不部署，pages 出的頁讀 board.json）。
        (out / "github" / "index.html").write_text(gh_page(generated, cfg["categories"]),
                                                   encoding="utf-8")
        # 這一班量不到榜單，但**中文有幾條照樣量得到**（那只是數檔案）。
        # 量不到的兩格寫 null，不寫 0（紅線 8）——寫 0 會讓「今天問不到 GitHub」
        # 看起來跟「今天榜上一條中文都沒有」一樣。
        write_desc_coverage(vault, now, None, None)
        return 0

    tier_split = cfg["tier_split"]
    ranked, surging = rank(current, state, now, cfg.get("top_n", 25), tier_split)
    categories = rank_categories(current, state, now, cfg["categories"], tier_split,
                                 cfg["category_top_n"])
    # board.json 存的是「榜的事實」：譯文在下面 attach 才掛，所以在那之前先序列化。
    # attach 是就地改 dict，晚一步序列化會把 desc_zh 一起存進去。
    doc = {"generated": generated, "count": len(ranked), "repos": ranked,
           "surging": surging, "surge_floor": SURGE_FLOOR, "tier_split": tier_split,
           "categories": categories, "measured": True}
    board_text = json.dumps(doc, ensure_ascii=False, indent=2)
    # 掛上潤稿端翻好的中文描述。抓取鏈不等它、也不產生它——沒有就是英文原文，
    # 榜照樣出得來。中文晚一步到（潤稿任務比 Actions 晚三小時）是設計，不是缺陷。
    # 全部榜與每一類的兩榜都掛：分類榜的列是另一批 dict，同一個 repo 在兩邊都要看得到譯文。
    store = ghdesc.load(vault)
    for rows in ghdesc.doc_boards(doc):
        ghdesc.attach(rows, store)
    (out / "data" / "github.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "github" / "index.html").write_text(gh_page(generated, categories),
                                               encoding="utf-8")

    # 更新快照（走到這裡就是 do_snapshot 為真，快照沒更新的班次在上面 emit_board 就回了）；進版控
    #
    # 名次跟星數同一次寫回，理由見模組 docstring 的 schema 段：兩個數字要回答
    # 同一個問句。**沒上榜的 repo 寫 null，不是不寫**——不寫的話下一班讀到的是
    # 「這個欄位不存在」，會被判成「舊 schema、量不到」，而事實是我們上次量過、
    # 它就是不在榜上。兩者在畫面上是不同的說法（見 rank_move()）。
    # 先 board、後 state：反過來的話 state 成功、board 失敗，下一班的基線就太新，
    # --snapshot-if-older-than 擋住，榜要等 20 小時才補得上。
    board_p = board_path(vault)
    board_p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(board_p, board_text + "\n")
    vel_rank = {r["full_name"]: r["rank_velocity"] for r in ranked}
    sur_rank = {r["full_name"]: r["rank_surge"] for r in surging}
    # 剪枝：GraphQL 確定不活躍、封存或查不到的 repo 拿掉（整批失敗那一批不在 drop 裡）。
    for full in info["drop"]:
        state.pop(full, None)
    state.update({full: {"stars": r["stars"], "ts": now.timestamp(),
                         "rank_velocity": vel_rank.get(full),
                         "rank_surge": sur_rank.get(full)}
                  for full, r in current.items()})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    n_new = sum(1 for r in ranked if r["is_new"])
    # 覆蓋率算**整頁**不算單一個榜。只算 ranked 的那一版，分母是星速榜的條數，
    # 而畫面上的列數是全部榜與分類榜去重後的——一個比事實窄的東西掛著事實的名字。
    # 頁面「中文描述 x/y」用同一個範圍（JS 的 allBoards）。
    listed = ghdesc.doc_union(doc)
    n_zh = sum(1 for r in listed if r.get("desc_zh"))
    # 這個數字以前只印在 CI 的 log 裡：人看得到、機器讀不到，於是「這個榜已經
    # 連續幾天沒有中文」沒有任何地方存著。潤稿端的 C2 段失敗時**寫不進 repo**，
    # 所以觀測要住在會跑的這一邊。見 lib/ghdesc.py 的〈覆蓋率〉。
    write_desc_coverage(vault, now, len(listed), n_zh)
    snap = " [snapshot 已更新，board.json 已寫]"
    print(f"pulse-github  抓到={len(current)}  上榜={len(ranked)}＋竄升={len(surging)}"
          f"（含分類榜去重 {len(listed)}）  首次觀測={n_new}  "
          f"中文描述={n_zh}/{len(listed)}{snap}  {cost}"
          f"（Search 失敗 {info['search_failed']} 次、GraphQL 沒有明確結果 {info['graphql_unknown']} 個、"
          f"剪枝 {len(info['drop'])} 個）"
          "  → data/github.json + github/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
