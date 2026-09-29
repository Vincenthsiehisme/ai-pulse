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
| 算 | `data-refresh.yml` 跑 `pulse-github.py --snapshot-if-older-than 20`（抓取模式） | GitHub Search API、`_github/state.json` | `_github/state.json`、`_github/board.json`（只在快照有更新時）、`_github/desc-coverage.json`、`dist/data/github.json`、`dist/github/index.html` |
| 存 | `data-refresh.yml` 的 `git add -A`（不用改） | | 把 `_github/board.json` 一起 commit 進 `main` |
| 出頁 | `pages.yml` 跑 `pulse-github.py --render-only` | `_github/board.json`、`_github/desc-zh.json` | `dist/data/github.json`、`dist/github/index.html` |

抓取模式照舊寫 `dist/data/github.json`：data-refresh 後面的 `pulse-github-desc-prep.py` 讀的
是它。那份 `dist` 不部署，部署的是 pages 自己出的那份。

## 兩個模式

### 抓取模式（預設）

行為照舊（打 Search、算 `rank()`、`--snapshot` 或 `--snapshot-if-older-than` 決定要不要更新
`state.json`），另外加一條：**這次快照有更新時**（`do_snapshot` 為真，也就是比對用的基線已達
門檻年紀），把算好的榜原子寫進 `_github/board.json`。

- 快照沒更新：`board.json` 一個 byte 都不動，stdout 那行印「board.json 未更新」。
- 抓取全失敗（`collect()` 回空）：不寫 `board.json`，保留上一份。
- 內容與 `dist/data/github.json` 是同一個 dict，**不含 `desc_zh` 欄**。譯文屬於敘述，在出頁時
  才掛，掛在 `board.json` 裡會讓「榜的事實」與「當下有沒有譯文」綁成同一份檔案。
- 寫檔順序：先 `board.json`、後 `state.json`。反過來的話，state 寫成功、board 沒寫成功，下一班
  的基線就太新，`--snapshot-if-older-than` 擋住，榜要等 20 小時才補得上。

### `--render-only`（pages 用）

不打任何網路、不讀 token、不寫 `_github/state.json` 與 `_github/desc-coverage.json`。

| 情況 | 行為 |
|---|---|
| `board.json` 存在且合法 | 用 `ghdesc.attach` 掛 `_github/desc-zh.json` 的譯文，寫 `dist/data/github.json` 與 `dist/github/index.html`；`generated` 沿用 board 的（榜是那一刻算的） |
| `board.json` 不存在 | 寫 `measured: false` 佔位（格式同抓取全失敗那份），stderr 印一行，exit 0 |
| 存在但不是合法 JSON、不是 object、或缺 `repos` | exit 2，訊息帶路徑；不寫任何輸出檔 |

`--render-only` 不能與 `--snapshot`、`--snapshot-if-older-than` 併用（argparse 直接拒）。

## `board.json` schema

```json
{
  "generated": "2026-09-30 08:00 台北時間",
  "count": 25,
  "repos": [ { "full_name": "...", "stars": 0, "velocity": 0.0, "surge": 0.0,
               "baseline_days": 1.0, "rank_velocity": 1, "rank_move_velocity": "up", "...": "..." } ],
  "surging": [ { "...": "同 repos，另有 rank_surge 等欄" } ],
  "surge_floor": 200,
  "measured": true
}
```

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

`rank()`、`rank_move()` 的算法、`state.json` schema、`desc-zh.json` 格式、
`pulse-github-desc-prep.py`／`pulse-github-desc-apply.py` 的讀取路徑都不動。
