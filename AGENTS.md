# AGENTS.md

自動化代理（Cowork 排程任務、Claude session、任何會對這個 repo 寫 commit 的東西）
在動手之前先讀 [CONTRIBUTING.md](CONTRIBUTING.md)。以下是最容易踩到的三條，全文
以 CONTRIBUTING.md 為準。

**1. 發現問題要自己開 PR。** 不是在摘要裡寫「建議修 X」就算交差，也不要直接推
`main`。開分支、修好、推分支、留 PR。驗證不出來的懷疑就寫「查過、不成立」，不要
硬送假問題（紅線 8）。**已知但還沒動手的問題記在 [BACKLOG.md](BACKLOG.md)** —— 開工前
先看一眼，別重複盤點同一個洞；修掉一條就順手從清單刪掉，清單留著過期條目比沒有清單更糟。

**2. 只有資料 commit 可以直推 `main`。** `chore: nightly refresh` 那一類，動的是
`_corpus/ _probe/ Events/ Sources/ _dashboards/ Tracks/ Actors/ Digests/ _github/ dist/`（`_github/` 含算好的榜 `board.json`），外加 `_config/sources.yaml`
的 `lifecycle` 與 `robots_ok` 兩欄（robots 重驗的實測結果，機器自己寫），以及
`_config/narratives.yaml` 的 `now` / `next` 兩段（每夜 enrich 的主線敘事，
`pulse-narrative-apply.py` 寫回）。這些是 `data-refresh.yml` 一天一班（`0 16 * * *` ＝台北隔日
00:00）、外加每夜 enrich 的產物，改成走 PR 會讓鏈卡死——刻意保留的例外。

**3. 碼、CI、`_config/`、文件一律走 PR。** 判斷邏輯與門禁門檻住在這裡；沒被審過
的規則不該直接決定什麼上線。改門檻 / 排名 / schema 前先改說明文件（紅線 9）。
`_config/sources.yaml` 除了上面那兩欄之外的所有欄位（新增來源、tier、role、
quota、覆蓋門檻）也走這條；`_config/narratives.yaml` 除了 `now` / `next` 之外的
`thesis` / `lenses`（編輯層）同理走 PR。

**憑證**：token 只出現在 clone / push 指令裡，絕不寫進任何檔案、commit 或摘要。

**雲端夜班有 hook 守門**：`.claude/settings.json` 接了 `scripts/nightly-guard.py`，只在雲端的
半夜潤稿 routine 裡作用，擋 agent 自己跑 apply、自己 commit／push／stash、寫交棒檔以外的檔，
收尾沒有原樣帶 driver 摘要也會被擋。被擋時理由寫在 stderr，規格在
[references/nightly-guard.md](references/nightly-guard.md)；範圍外的事寫進摘要，不要換寫法繞過去。

## commit 前的檢查

`.githooks/pre-commit` 擋 staged 改動裡的密鑰（gitleaks）與測試檔新增行裡的個資格式；`.githooks/commit-msg` 擋
commit message 裡的密鑰，並驗標題是 `<type>: <為什麼>`；`.githooks/pre-merge-commit` 在沒有衝突、git 直接建
merge commit 時跑同一支 pre-commit（git 這時不呼叫 pre-commit）；`git am` 不呼叫前兩支，`pre-applypatch`、
`applypatch-msg` 轉給同兩支。哪些算測試檔、哪些 email 放行、type 有哪些，
寫在各支開頭的註解，這裡不抄第二份。**在主 clone 啟用一次，所有 worktree 共用**：

```bash
brew install gitleaks
git config core.hooksPath "$(git rev-parse --show-toplevel)/.githooks"    # 在主 clone 裡跑（不是 worktree）；一定要絕對路徑
```

一定要絕對路徑：相對的 `.githooks` 會從每個 worktree 自己的根目錄找，還沒有這些 hook 的舊分支 worktree 會被
git 安靜略過。hook 讀的是主 clone 工作樹裡的 `.githooks/`：主 clone 更新到含這個目錄的 main 之前，git 找不到
hook，所有 worktree 的 commit 都不掃。確認有沒有作用：`git hook run pre-commit`，印 `cannot find a hook` 就是沒有。
沒裝 gitleaks 時三支都直接擋 commit，不會安靜略過。

本機 hook 擋不到的路：`--no-verify`、GitHub 網頁 merge、`git rebase --continue`（解衝突時新貼進去的內容）、
無衝突的 cherry-pick、預設 backend 的 rebase 重放與 `rebase -i` 的 squash／fixup、無衝突的 `git revert`、fast-forward；被 git 判成 binary 的檔（`.gitattributes` 標 `-diff`／`binary`、
超過 `core.bigFileThreshold`），gitleaks 與個資檢查都看不到內容，不要把文字檔標成 binary。密鑰誤報在那一行加 `# gitleaks:allow` 並寫理由：它整行放行，
只能用在整行都是公開資料的地方，commit message 裡不准寫它（寫了，message 掃描也會放行）。測試檔裡故意造的
假手機、假身分證格式在那一行寫 `pii:allow` 加理由；真資料不准這樣放行，email 一律改用 `example.com` 這類保留網域。
PR 說明照 `.github/pull_request_template.md` 寫。

會被擋、要自己處理的幾種：整合分支的 merge 用 git 預設標題（`git merge --no-ff --no-edit`），`-m "merge: …"` 會被擋在
merge 進行中，用 `git merge --abort` 退出；`git merge --squash` 預填的 `Squashed commit of the following:` 要自己改標題；
有衝突的 cherry-pick 解完 `--continue` 會跑 commit-msg，舊格式標題會停在 cherry-pick 進行中；`git rebase --apply` 走
`git am`，重放舊格式標題的 commit 時會停住：先 `git rebase --abort` 退回原狀（`--continue` 會回「沒有變更」卡住，`--skip`
會丟掉那個 commit），再改用預設 backend，或先用 `rebase -i` 的 reword 把標題改成新格式。

資料 commit（上面第 2 條那一類）在 GitHub Actions 與雲端 routine 裡 commit，那裡沒設 `core.hooksPath`，不經過
這組 hook；不要在那兩處設它，那裡沒有 gitleaks，三支都會擋。`commit-msg` 另外放行這兩種機器標題的完整格式
（`nightly: enrich + narrative|digest <日期>`、`probe <日期>: <n> items / <n> sources`），本機手跑 `pulse-probe.py`
才不會被擋；近似的人寫標題照樣擋。改了產生器的標題格式，要同一個 PR 改 `commit-msg` 那條正則，不然本機跑會被擋，
而 `pulse-probe.py` 只把 commit 失敗印成 warn。

## Review

派 reviewer 時指到這一節。

- 這個 repo 壞掉的樣子：數字看起來正常但其實是空轉，或夜裡的資料鏈卡住（CONTRIBUTING.md〈PR 內容要求〉〈兩條路，別走錯〉）。審的時候問「壞了儀表板會顯示什麼」。
- 第 2 條列的資料路徑（`_corpus/`、`_probe/`、`Events/`、`Sources/`、`_dashboards/`、`Tracks/`、`Actors/`、`Digests/`、`_github/`、`dist/`）是機器產物，內容不逐行審；但它們出現在程式或文件 PR 裡本身就要指出（CONTRIBUTING.md：人不手改這些檔），要求移除或附可重跑的產生證據。
- 最多回 5 條，會壞的排前面。
