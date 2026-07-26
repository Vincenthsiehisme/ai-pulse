# AGENTS.md

自動化代理（Cowork 排程任務、Claude session、任何會對這個 repo 寫 commit 的東西）
在動手之前先讀 [CONTRIBUTING.md](CONTRIBUTING.md)。以下是最容易踩到的三條，全文
以 CONTRIBUTING.md 為準。

**1. 發現問題要自己開 PR。** 不是在摘要裡寫「建議修 X」就算交差，也不要直接推
`main`。開分支、修好、推分支、留 PR。驗證不出來的懷疑就寫「查過、不成立」，不要
硬送假問題（紅線 8）。**已知但還沒動手的問題記在 [BACKLOG.md](BACKLOG.md)** —— 開工前
先看一眼，別重複盤點同一個洞；修掉一條就順手從清單刪掉，清單留著過期條目比沒有清單更糟。

**2. 只有資料 commit 可以直推 `main`。** `chore: nightly refresh` 那一類，動的是
`_corpus/ _probe/ Events/ Sources/ _dashboards/ dist/`，外加 `_config/sources.yaml`
的 `lifecycle` 與 `robots_ok` 兩欄（robots 重驗的實測結果，機器自己寫），以及
`_config/narratives.yaml` 的 `now` / `next` 兩段（每夜 enrich 的主線敘事，
`pulse-narrative-apply.py` 寫回）。這些是 `data-refresh.yml` 每兩小時一班、外加每夜
enrich 的產物，改成走 PR 會讓鏈卡死——刻意保留的例外。

**3. 碼、CI、`_config/`、文件一律走 PR。** 判斷邏輯與門禁門檻住在這裡；沒被審過
的規則不該直接決定什麼上線。改門檻 / 排名 / schema 前先改說明文件（紅線 9）。
`_config/sources.yaml` 除了上面那兩欄之外的所有欄位（新增來源、tier、role、
quota、覆蓋門檻）也走這條；`_config/narratives.yaml` 除了 `now` / `next` 之外的
`thesis` / `lenses`（編輯層）同理走 PR。

**憑證**：token 只出現在 clone / push 指令裡，絕不寫進任何檔案、commit 或摘要。
