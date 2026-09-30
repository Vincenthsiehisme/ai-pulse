# GitHub 榜的資料流：榜在 data-refresh 算一次、存進版控，pages 只讀

規格對象：`scripts/pulse-github.py`、`_github/board.json`、`.github/workflows/pages.yml`。
2026-09-30 起。

## 一句話

榜（`repos`、`surging`）**只在 data-refresh 算一次**，算完連同快照一起進版控，存在
`_github/board.json`。pages 出頁時**不重算、不打網路、不讀 token**，只讀那一份榜，掛上中文
描述，寫出 `dist/data/github.json` 與 `dist/github/index.html`。

## 誰算、誰存、誰出頁

| 角色 | 誰 | 讀什麼 | 寫什麼 |
|---|---|---|---|
| 算 | `data-refresh.yml` 跑 `pulse-github.py --snapshot-if-older-than 20`（抓取模式） | GitHub Search API 與 GraphQL（〈候選池〉）、`_github/state.json`（快照沒更新時改讀 `board.json`，見下） | `_github/state.json`、`_github/board.json`（只在快照有更新時）、`_github/desc-coverage.json`、`dist/data/github.json`、`dist/github/index.html` |
| 存 | `data-refresh.yml` 的 `git add -A`（不用改） | | 把 `_github/board.json` 一起 commit 進 `main` |
| 出頁 | `pages.yml` 跑 `pulse-github.py --render-only` | `_github/board.json`、`_github/desc-zh.json` | `dist/data/github.json`、`dist/github/index.html` |

抓取模式照舊寫 `dist/data/github.json`：data-refresh 後面的 `pulse-github-desc-prep.py` 讀的
是它。那份 `dist` 不部署，部署的是 pages 自己出的那份，所以這一份的內容必須與 pages 出的是同一份榜
（快照沒更新的班次取自 `board.json`，見〈抓取模式〉）。

## 兩個模式

### 抓取模式（預設）

依 `do_snapshot`（比對的基線是否已達門檻年紀）分兩條路。

**`do_snapshot` 為真**：行為照舊（打 Search、算 `rank()`、更新 `state.json`），另外把算好的榜原子寫進
`_github/board.json`。

- 抓取全失敗（`collect()` 回空）：不寫 `board.json`，保留上一份。
- 內容與 `dist/data/github.json` 是同一個 dict，**不含 `desc_zh` 欄**。譯文屬於敘述，在出頁時
  才掛，掛在 `board.json` 裡會讓「榜的事實」與「當下有沒有譯文」綁成同一份檔案。
- 寫檔順序：先 `board.json`、後 `state.json`。反過來的話，state 寫成功、board 沒寫成功，下一班
  的基線就太新，`--snapshot-if-older-than` 擋住，榜要等 20 小時才補得上。

**`do_snapshot` 為假**（基線未達門檻，或沒帶任何快照旗標）：**不抓、不重排、不寫 `board.json`**
（一個 byte 都不動），stdout 那行印「board.json 未更新」與「出頁取自 _github/board.json」。
`dist/data/github.json`、頁面與 `_github/desc-coverage.json` 的榜一律取自現有 `board.json`，掛譯文
的方式與 `--render-only` **是同一份碼**（`emit_board()`）。

為什麼不能另排一份：同一班後面的 `pulse-github-desc-prep.py` 預設讀 `dist/data/github.json`，
`write_desc_coverage()` 量的也是同一份榜。用年輕基線重排的榜線上不會顯示，desc-prep 與覆蓋率量到的
就會是一份沒人看得到的榜。`desc-prep` 的讀取路徑不變，只是這一班內容換成線上那份。

- `board.json` 不存在：`dist/data/github.json` 寫 `measured: false` 佔位、stderr 一行，
  `desc-coverage.json` 的 `ranked`、`with_zh` 兩格寫 null（量不到寫 null，不寫 0）。
- `board.json` 壞掉：與 `--render-only` 一樣 exit 2，訊息帶路徑。

### `--render-only`（pages 用）

不打任何網路、不讀 token、不寫 `_github/state.json` 與 `_github/desc-coverage.json`。

| 情況 | 行為 |
|---|---|
| `board.json` 存在且合法 | 用 `ghdesc.attach` 掛 `_github/desc-zh.json` 的譯文，寫 `dist/data/github.json` 與 `dist/github/index.html`；`generated` 沿用 board 的（榜是那一刻算的） |
| `board.json` 不存在 | 寫 `measured: false` 佔位（格式同抓取全失敗那份），stderr 印一行，exit 0 |
| 存在但不是合法 JSON、不是 object、或缺 `repos` | exit 2，訊息帶路徑；不寫任何輸出檔 |

`--render-only` 不能與 `--snapshot`、`--snapshot-if-older-than` 併用（argparse 直接拒）。

## 體量切分

2026-09-30 起（plan〈GitHub 榜去重分類與成本觀測〉AC-2）。

兩個榜以前是同一批 repo 的兩種排序，各自截前 `top_n`。大 repo 在星速榜上是日常，竄升榜又沒有
星數上限，結果同一個 repo 常常兩邊都上，頁面得靠「另一個榜的名次」那一格（xref）把重疊標出來。
讀者看到的是兩份大半重複的榜。

改成**按體量切**，門檻是 `_config/github.yaml` 的 `tier_split`（20000）：

| 榜 | 收哪些 repo | 排序 |
|---|---|---|
| 星速榜 `repos` | 這一次量到的 `stars >= tier_split` | Δ★/天，首次觀測排最後（同舊） |
| 竄升榜 `surging` | 這一次量到的 `stars < tier_split`，且上一版 `>= SURGE_FLOOR` | Δ%/天，同分用名字破（同舊） |

- 用**這一次**的星數切，不用上一版的。同一列的 `stars` 只有一個值，所以兩個榜一定不相交。
- 門檻寫在設定檔、由 `rank()` 讀，同一個值也寫進 `github.json`／`board.json` 頂層的 `tier_split`，
  頁面讀 `d.tier_split` 印出來。一個沒有寫出來的門檻跟沒有門檻一樣會誤導。
- 每個分類頁的兩個榜**同樣套 `tier_split`**（見〈分類〉），分類頁的兩榜也不相交。
- 頁面拿掉 xref：兩榜不再重疊，那一格永遠是空的。
- 跨過門檻的 repo 會換榜。它在新榜上的名次變動是「新進榜」（`entered`）：`state.json` 記的是
  它上一次**在那個榜上**的名次，上一次它不在那個榜上，所以是 null。這跟 `rank_move()` 六態的
  定義一致，不另立一態。
- 代價：`stars < tier_split` 的首次觀測 repo 兩邊都不上。星速榜以前會把它們排在最後、標「首次
  觀測」；現在它們不在星速榜的範圍內，竄升榜又要上一版的星數，隔一晚有了基線才會出現。
- `rank_move()` 的六態、`baseline_days` 的算法、`state.json` 的四欄 schema 都不變。

## 分類

2026-09-30 起（plan〈GitHub 榜去重分類與成本觀測〉AC-3，六類與順序由使用者裁定）。

以前的設定是一份全域 `keywords`，所有 repo 混在一個池子裡排。改成 `_config/github.yaml` 的有序
清單 `categories`，每項 `{id, name, topics, queries}`：

| 順序 | id | name |
|---|---|---|
| 1 | `open-models` | 開源模型與推論 |
| 2 | `automation` | AI 自動化與工作流 |
| 3 | `coding-agents` | Coding agent 與 skills |
| 4 | `agent-frameworks` | Agent 框架 |
| 5 | `mcp` | MCP 與工具整合 |
| 6 | `rag-memory` | RAG、記憶與向量資料庫 |

每一類的 `topics` 與 `queries` 見設定檔本身，這裡不抄第二份。

### 一個 repo 恰好一個分類

`classify(row, categories)` 是純函式：依清單順序，第一個 `topics` 跟 repo 的**完整** topics
有交集的類就是它；都沒有回 `unclassified`。

- **清單順序就是優先序。** 一個 repo 同時帶 `mcp` 與 `rag` 兩個 topic，算 `mcp`（第 5 類），不算
  `rag-memory`（第 6 類）。多類符合取第一類，所以一個 repo 只會出現在一個分類頁。
- **比對前兩邊都轉小寫。**
- **用完整 topics。** GitHub 一個 repo 最多 20 個 topic；搜尋回傳整份，GraphQL 用
  `repositoryTopics(first: 20)`。榜上每列只顯示前 6 個，分類在截斷**之前**做：topic 排在第 7 個
  以後的 repo 照樣分得到類，不會因為顯示截斷被判成 `unclassified`。
- **泛用 topic 刻意不放。** `ai-agents`、`agent`、`agents`、`llm`、`ai` 不在任何一類：放進去的話
  幾乎每個 repo 都會先命中那一類，優先序就沒有意義。只帶這些泛用 topic 的 repo 標 `unclassified`。
- **找到 repo 的是哪一類的 query 不影響分類。** 分類只看 topics；query 只決定候選池（見〈候選池〉）。

### 分類頁

- `github.json`／`board.json` 頂層新增 `categories`，**依設定順序**，每項
  `{id, name, repos, surging}`。
- 每一類在自己的池子內（`category` 等於那一類的 id）各排兩榜 `category_top_n` 名（10），
  **同樣套 `tier_split`**，排序與全部榜同一支 `split_tiers()`。分類頁的兩榜交集也必為空。
- 分類榜**不算名次變動**：`state.json` 只存全部榜的名次，分類榜的列不帶 `rank_*` 欄位，前台
  名次底下那一格不畫。分類榜的列是另一批 dict（`measure()` 重算一次），不共用全部榜那一批，
  所以全部榜寫的名次欄不會漏進分類榜。
- `unclassified` 不是一個分類頁，只在「全部」出現，標籤寫「未分類」。
- 全部榜的每一列帶 `category`；頁面每一列印分類標籤。

### 頁面

上方一排分頁：「全部」加六類，分頁是出頁時依 `board.json` 的 `categories` 寫進 HTML 的
（`--render-only` 讀的是 board，不讀設定檔）。預設「全部」：兩榜各 `top_n`（25）名、帶分類標籤、
名次變動照舊。切到某一類：換成那一類的兩榜各 `category_top_n` 名，名次變動那一格不畫。沿用站上
的 `.chip-row` 按鈕與既有 token，不加 `<style>`。

### 中文描述涵蓋分類榜

分類榜會列出全部榜沒有的 repo（某一類的第 3 名可能排不進全部榜的前 25）。翻譯鏈只認 `repos`
與 `surging` 的話，那些 repo 永遠是英文，而頁面上印著「中文描述 x/y」。

- `ghdesc.doc_boards(doc)` 取出整份榜單的所有榜（`repos`、`surging`、每一類的兩榜），
  `ghdesc.doc_union(doc)` 把它們交給 `board_union` 輪流去重（語意不變）。
- `pulse-github-desc-prep.py` 的待譯清單、`pulse-github-desc-apply.py` 的 `english_source` 與寫回、
  `--render-only`／`emit_board()` 掛譯文，都走這兩支。
- 頁面「中文描述 x/y」與 `write_desc_coverage()` 的分母是同一份：全部榜與分類榜去重後的 repo 數。

## 候選池

2026-09-30 起（plan〈GitHub 榜去重分類與成本觀測〉AC-4）。

榜只能從候選池裡排，池子裝不到的 repo 永遠不會上榜，而畫面上看不出來。以前的池子是七個全域
關鍵字各打一次 Search、每次 40 筆，兩個洞：新建的 repo 在「依星數排」的搜尋裡排不進前 40；
`state.json` 裡已知的 repo 某一晚沒被搜到，那一晚就量不到，它的基線一天一天變老（實測 07-26～31
每班 1～6 條）。

`collect()` 現在分兩段。

### 一、Search：每類每個 query 兩次

依 `categories` 順序、每類依 `queries` 順序，每個 query 打兩次，都依星數排、`per_page` 40：

| 次 | q |
|---|---|
| 1 | `{query} stars:>={min_stars} pushed:>{今天−active_days}` |
| 2 | `{query} stars:>={min_stars} pushed:>{今天−active_days} created:>{今天−new_repo_days}` |

第二次專撈近 `new_repo_days`（90）天新建的 repo：它們星數還小，在第一次的前 40 名裡排不上。
兩次都帶 `pushed:>`，入池條件（近 `active_days` 天有推送）只有一份。依 `full_name` 去重，第一次
出現的那筆留下；`exclude` 照舊。

- **限速。** 每次 Search 之間 `time.sleep(2.1)`，第一次之前不睡。Search API 登入後上限每分鐘 30 次；
  間隔 2.1 秒，任何 60 秒的窗口最多 29 次。六類共 15 個 query、30 次 Search，這一段約 61 秒加上
  請求本身的時間。
- **失敗印得出來。** 單次 Search 失敗（HTTP 非 200、例外）stderr 印一行、那一次算失敗、`search_repos`
  回 None（跟「0 筆」分得開）。**全部 Search 都失敗**時 `collect()` 回空池，不做 GraphQL：只有
  追蹤名單的池子不是這一晚的榜（新 repo 一個都不在），照「抓取全失敗」處理，保留上一份 `board.json`。
- 抓取模式 stdout 那一行印 `Search N 次、耗時 S 秒、GraphQL 補量 M 個`（N 是實際呼叫次數、含失敗的，
  S 是整個 `collect()` 的秒數），另印失敗次數與剪枝個數。C4 用 Actions log 的 N 與 S 驗每分鐘不超過 30 次。

### 二、GraphQL：追蹤已知 repo

`state.json` 裡這次沒被搜到的 repo，用 GraphQL（`https://api.github.com/graphql`）補量：
`repository(owner, name)` 別名批次，一次最多 100 個，取 `nameWithOwner`、`stargazerCount`、
`description`、`url`、`primaryLanguage`、`repositoryTopics(first: 20)`、`createdAt`、`pushedAt`、
`isArchived`。補量到的列跟搜尋的列走同一支 `pool_row()`（分類用完整 topics）。

| GraphQL 回來的樣子 | 進這次的池子 | `state.json` |
|---|---|---|
| 有資料、未封存、`pushedAt` 在 `active_days` 內 | 進 | 照常更新 |
| 已封存 | 不進 | 剪掉 |
| `pushedAt` 超過 `active_days` | 不進 | 剪掉 |
| 別名是 null 且錯誤是 `NOT_FOUND`（刪除），或 `nameWithOwner` 跟要的名字不同（改名） | 不進 | 剪掉 |
| 別名是 null 但錯誤不是 `NOT_FOUND`、或根本沒回這個別名 | 不進 | **不動**（這次不知道） |
| 整批失敗（沒 token、HTTP 非 200、例外、回應沒有 `data`） | 那一批都不進 | **那一批都不動**，stderr 印一行 |

- 只有 GraphQL 成功回來、而且明說了那個 repo 的狀態，才算「確定」。量不到的不剪：剪錯的代價是
  一個還活著的 repo 失去基線、下一晚變首次觀測，而那不會有任何東西變紅。
- 補量的 repo 不套 `min_stars`：它們是已知的 repo，入池時已經過了門檻，AC-4 要的是「已知且
  45 天內有 push 的每晚都量到」。`exclude` 照套。
- 改名的 repo 不追新名字：新名字要是還活躍，Search 會找到它，當首次觀測重新累積。
- 剪枝只在快照寫回時做（`do_snapshot` 為真），`state.json` 舊 schema 的四欄不變。

效果：`state.json` 已知、45 天內有推送的 repo 每晚都量到，非首次觀測的列 `baseline_days` 是
「上一晚到這一晚」（< 1.5），不再有掉出搜尋幾天、回來時帶著六天基線的列。

## `board.json` schema

```json
{
  "generated": "2026-09-30 08:00 台北時間",
  "count": 25,
  "repos": [ { "full_name": "...", "stars": 0, "velocity": 0.0, "surge": 0.0,
               "baseline_days": 1.0, "rank_velocity": 1, "rank_move_velocity": "up", "...": "..." } ],
  "surging": [ { "...": "同 repos，另有 rank_surge 等欄" } ],
  "surge_floor": 200,
  "tier_split": 20000,
  "categories": [ { "id": "open-models", "name": "開源模型與推論",
                    "repos": [ { "...": "同 repos 的列，但沒有 rank_* 欄" } ],
                    "surging": [ "..." ] } ],
  "measured": true
}
```

每一列另有 `category`（六類的 id 之一或 `unclassified`）。

與 `dist/data/github.json` 的差別只有一個：每列少了 `desc_zh`。`board.json` 只在抓取成功且
快照有更新時寫，所以檔案裡的 `measured` 永遠是 `true`；`measured: false` 只出現在 render-only
找不到 board 時的佔位。

## 為什麼 pages 不能重算

pages 每次 push 到 `main` 都會跑（`pages.yml` 刻意不設 `paths`），一天多次。它以前跑
`python scripts/pulse-github.py`（不帶任何快照旗標），流程是：打 Search、拿 checkout 出來的
`_github/state.json` 當基線、算 `rank()`。

data-refresh 每晚 commit 的 `state.json` 是**那一刻的星數**，所以 pages 隨後在幾分鐘內重算時，
基線與現值只差幾分鐘。結果就是 `baseline_days` 被壓成 0.0，星速被 `days` 的 0.5 下限放大成
2×delta。

2026-09-30 量到的線上現象：

- `github.json` 全列 `baseline_days` 都是 0.0。
- 星速是 2×delta：基線只有幾分鐘大，`rank()` 的 `days = max(..., 0.5)` 下限生效，delta 被除以
  0.5，所以每一列的星速剛好是 delta 的兩倍。

這兩個數字看起來都很正常，沒有任何東西會紅。所以榜只能算一次：拿「基線已達門檻年紀」那一刻
算出來的，存下來，之後所有出頁都讀同一份。

## 驗收

merge 後手動跑一次 data-refresh，線上 `github.json` 非首次觀測（`is_new` 為 false）的列
`baseline_days` 要 ≥ 0.8。

第一次上線時 `board.json` 還不存在：pages 在 data-refresh 寫出第一份之前會出 `measured: false`
的佔位頁。data-refresh 手動跑那一次要是基線不到 20 小時大（快照沒更新），`board.json` 仍不會
被寫，要等基線夠老那一班。

## 不變的東西

`rank_move()` 的六態、`baseline_days` 的算法、`state.json` 的四欄 schema、`desc-zh.json` 格式、
`pulse-github-desc-prep.py`／`pulse-github-desc-apply.py` 的讀取路徑都不動。

T1 那一版（榜的資料流）寫的是 `rank()` 不動；2026-09-30 T2 那一版改了 `rank()` 的入池條件
（〈體量切分〉），星速與竄升的算式、排序鍵、同分的破法照舊。
