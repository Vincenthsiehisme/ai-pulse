# 2026-08-09 — 一個部署閘門，把抓取鏈擋了四天

## 一句話

`data-refresh.yml` 的 `refresh` job 掛著 `environment: github-pages`，那個環境的一條
部署保護規則讓 job 停在 `Waiting` 三天；`concurrency: nightly` 是單槽且
`cancel-in-progress: false`，於是後面每一班都排在它後面到期被砍。**`main` 從 2026-08-05
到 2026-08-09 沒有進過任何資料**，而現場沒有任何一盞燈是紅的。

## 時間軸

| 時間 | 事情 |
|---|---|
| 08-05 17:16Z | 最後一班成功：`probe 2026-08-05` + `chore: nightly refresh` |
| 08-06 00:16Z | PR #50 合入（潤稿鏈的死人開關 `--alert-enrich-stale`） |
| 08-07 01:26 | run #34 排程觸發 → 狀態 `Waiting`，`Total duration –`，`refresh` 一個 step 都沒開始 |
| 08-08 / 08-09 | #35（23h38m）、#36（1d 0h 01m）排隊到期被砍 |
| 08-09 00:17 | #37 同上 |
| 08-09 ~22:00 | 人手動取消 #34，隊伍清空；#38 / #39 真的跑起來（13m41s / 8m47s） |

`Waiting` 這個狀態只有 `environment:` 會造成。四種保護規則裡只有「Required reviewers」
會跳核准鈕，而 #34 那一頁沒有鈕——所以是 wait timer、分支政策、或 GitHub App 的自訂
規則其中之一（本文寫成時尚未確認是哪一條，那不影響下面的結論）。

## 為什麼沒有任何東西變紅

三個判準各自都在，各自都對不上：

| 判準 | 為什麼漏掉 |
|---|---|
| `--alert-stale`（幾天沒抓到） | 它長在 `Health monitor` 那一步，而那一步在**同一個 job 裡**——job 沒開始，警報也沒開始 |
| `health.md` 的 `generated_day` | 同上，寫它的也是那個 job |
| `--alert-enrich-stale` | 同上。而且它 08-06 才合入，之後一班都沒成功，**這一段從來沒有渲染到 `_dashboards/health.md` 上過** |

也就是：**這條鏈所有的警報都住在它自己裡面。** 鏈整個沒被排上，警報就跟著沒被排上。
這個 repo 一直在修「警報自己把自己關掉」，這次是它最徹底的一種形態——警報連跑的機會
都沒有。GitHub 的失敗通知是唯一還會動的東西，而排隊到期被砍那幾班的通知看起來
跟「跑失敗了」一樣，沒有人會從那裡想到「四天沒資料」。

## 修法

**部署整個搬出這條鏈。**

`pages.yml` 本來就在任何 push 到 main 時部署（含 Cowork 潤稿推回、手動 commit），
而 `data-refresh.yml` 的最後一步就是 push 到 main——它必然觸發 `pages.yml`。
所以那兩步 `upload-pages-artifact` / `deploy-pages` 從第一天就是重複的，
代價是兩支工作流同時宣告 `environment: github-pages`。

改動：

1. `data-refresh.yml` 拿掉 `environment:`、拿掉部署兩步、`permissions` 收成只剩
   `contents: write`。**這條鏈到 commit 為止。**
2. `pages.yml` 成為唯一部署者，它的 `paths:` 過濾清單一併拿掉（見下）。
3. 兩支都補 `timeout-minutes`。整份 workflow 以前一個都沒有，所以任何一次卡住會燒滿
   預設的 6 小時，再連累後面每一班。實測正常一班是 8～14 分鐘。

### 順手拿掉 pages.yml 的 paths 過濾

原本只列 `Events/**`、`pulse-render.py`、`pulse-github.py`、`_config/github.yaml`。
而 `pulse-render.py` 實際上還讀 `_dashboards/`、`_github/`、`_config/` 底下別的檔。
清單跟渲染器讀什麼**會慢慢分岔，而分岔的那天沒有任何東西會紅**——網站只是靜靜停在
舊版本。同一個形狀這個 repo 量過很多次。render 是確定性的、分鐘級，寧可多跑幾次。

## 順手修掉一句會把人指向錯方向的警報

診斷過程中被自己的警報誤導了一次。`--alert-stale` 的訊息尾巴是**寫死**的：

> 已 4 天沒抓到任何項目……最後一次跑班 2026-08-05，**跑班日期是今天而這裡紅了，
> 代表鏈在跑但每條來源都沒東西進來**

同一句話裡自相矛盾：跑班是 08-05，卻說「跑班日期是今天」。那句尾巴只在
`run_lag == 0` 時成立，而它無條件印。它把人指向「來源全死了」，實際上是**鏈連跑
都沒跑到**——那兩件事要做的動作完全相反。

改成依 `run_lag_days` 分三種：今天跑過（來源的問題）／跑過但不是今天（排程或 CI
的問題）／從來沒跑過。`data-refresh.yml` 自己的註解早就寫過這句話：
**一個假訊號指向錯的地方，比沒有訊號更花時間。**

## 還沒關掉的那一條

那個環境的保護規則本身**沒有動**。取消 #34 只清掉這一次的隊伍。
`Settings → Environments → github-pages` 要看過、把不該在的規則移掉，
否則 `pages.yml` 會接手變成下一個卡住的人——差別是那時候只有網站停更，
資料鏈照樣進 main，而警報也照樣會叫。**這就是這次改動買到的東西。**
