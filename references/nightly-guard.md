# 雲端夜班的守門：把「不要自己跑 apply、不要 commit」從 prompt 變成做不到的事

> 這份是**規格**，`scripts/nightly-guard.py` 是它的實作，接線在 `.claude/settings.json`。
> 〈成本帳〉一節的實作是 `scripts/nightly-cost.py` 與 `scripts/lib/nightcost.py`。
> 不一致時以本檔為準，**先改本檔再改碼**（紅線 9）。

## 為什麼要有這一層

`references/nightly-driver.md` 把順序、exit code 判讀、交棒對帳收進 driver，本機外殼再用
工具白名單（`Read Write Glob Grep`，沒有 Bash）讓寫作端「辦不到」判斷。搬到雲端排程
（`claude.ai/code/routines`）之後，寫作端跟迴圈是**同一個 agent**，它手上有 Bash，
「不要自己跑 apply、不要 commit、不要 push」又退回成 prompt 裡的一句話。雲端平台還有自己的
Stop hook（`~/.claude/stop-hook-git-check.sh`），工作樹髒或有沒推出去的 commit 就不准收工，
而 driver 在 commit 之後還會再寫一次狀態檔（`nightly-driver.md`〈狀態檔的最後一段不在同一顆
commit 裡〉），所以每晚收尾都會被它攔。被攔之後 agent 怎麼收，每晚即興一次：

| 日期 | agent 自己做了什麼 | 後果 |
|---|---|---|
| 2026-09-18、09-19 | `chore: record nightly run … completion in state file` 推上 main | 授權格式外的 commit |
| 2026-09-20 | `git stash` 收掉產物 | 產物跟容器一起消失 |
| 2026-09-23 | 自己先跑 narrative／github-desc／title 三支 apply，driver 再跑時全部判成做過；收尾把 driver 的 19 筆拒寫、18 筆退件改寫成「全部一次通過機檢，沒有退件」；平台要它推沒推出去的 commit，它 `git reset --hard origin/main` | 狀態檔失真、收尾摘要跟狀態檔相反 |
| 2026-09-27 | `chore: nightly refresh 2026-09-27 (run state: precheck stop)` 推上 main | 冒用資料鏈的 commit 前綴 |

五晚，一個形狀：**不准做的事寫在 prompt 裡，而 prompt 每晚被重新讀一次、被平台的 hook 逼著重新詮釋一次。**

## 什麼時候作用

三個條件都成立才管，否則一律放行、不讀任何檔：

1. 環境變數 `CLAUDE_CODE_REMOTE` 是 `true`（雲端 session）。本機的互動 session 與 launchd 外殼完全不受影響。
2. 這個 session 的**第一則使用者訊息**含 `ROUTINE_MARKER`（`你是 AI-Pulse 的半夜潤稿執行者`），從 hook 收到的 `transcript_path` 讀。看「含」不看「開頭是」：改由 API（`/fire`）觸發之後，平台可能在 prompt 前面包一層（例如帶 `text` 時的 `<routine-fire-payload>`），開頭就不一定是身分句。
3. 這一次的工具呼叫本來就會被擋（見下）。會被放行的呼叫連 transcript 都不讀。

**為什麼用 prompt 的身分句當標記，不用環境變數。** 三個 ai-pulse routine（半夜潤稿、抓取頻率禮貌檢查、
情報庫雙週體檢）可能共用同一個雲端環境，環境變數分不出是哪一個；只看 `CLAUDE_CODE_REMOTE`
又會連人在 claude.ai/code 開這個 repo 做開發時一起擋。身分句是 routine prompt 的第一行，
**改 routine prompt 時這一行不能動**，動了守門就安靜失效；這一點 selftest 驗不到（routine 設定不在 repo 裡）。

**標記對不上不能安靜地放行。** prompt 被改、或觸發方式改了訊息形狀的那一晚，守門會整晚不見，而且沒有人知道。
所以 Stop 多一道：雲端、第一則訊息沒有標記，但 `_probe/nightly-run.json` 是今天的、而且工作樹上它有改動
（雲端每次都是全新 clone，有改動就代表這個 session 跑過 driver），就擋一次，要收尾寫明「守門這一晚沒有作用」。
`stop_hook_active` 為真時只印不擋。

判不出是不是夜班（雲端、呼叫本來會被擋、但 transcript 讀不到）時**擋**，理由寫明是判不出，
不是猜「大概不是夜班」放行：放行的失敗形狀正是這一層要擋的那一種。

## PreToolUse：擋什麼、放什麼

**Bash** 先按 shell 分隔（`;`、`&&`、`||`、`|`、`&`、引號外的換行、`$(…)`、`bash -c`、`eval`）拆成單一指令，
逐一判：

- **`scripts/pulse-*.py` 只准 `pulse-nightly.py`**，而且只准 `run`、`summary`、`status` 三個子命令，
  `run` 不准帶 `--reset`、`--no-push`。直接跑任何一支 prep／apply／gate／render（含 `--dry-run`）一律擋：
  判斷是 driver 的，退件要記進摘要，不是讓寫的人先自己試到過。`--reset` 是「要不要重跑」，
  `nightly-driver.md` 寫明那是人的決定。讀這些檔（`cat`、`sed`、`grep`）不算跑。
- **git 採允許清單**，表上沒有的子命令一律擋：
  - 唯讀的照放：`status`、`log`、`diff`、`show`、`rev-parse`、`rev-list`、`merge-base`、`ls-files`、
    `ls-tree`、`cat-file`、`blame`、`describe`、`shortlog`、`grep`、`name-rev`、`for-each-ref`、
    `show-ref`、`fetch`、`help`、`version`；`branch` 只准列出（不帶要建、刪、改名的參數）；
    `remote` 只准列出與 `get-url`；`config` 只准讀；`reflog` 只准看。
  - routine prompt 第 1 步的對齊照放：`git checkout main`、`git merge --ff-only origin/main`。
  - **平台 Stop hook 的三個出口**，每一個都要當下查過 git 狀態才放（`GitFacts`）：
    1. `git add _probe/nightly-run.json`，而且工作樹上改動的只有這個檔。
    2. `git commit -m "<訊息>"`，訊息第一行符合 `STATE_COMMIT_RE`（`chore: nightly run state <UTC 當天>`，
       後面可以接括號說明），而且工作樹上改動的只有 `_probe/nightly-run.json`。只准 `-m`／`--message`／`-q`，
       `--amend`、`-F`、`--author`、不帶訊息開編輯器都擋。
    3. `git push` 不帶 `--force` 類旗標，目的地只准 `main`（站在 `main` 上）或這一晚的備援分支
       `nightly/<UTC 當天>-<sha>`；`git reset --hard origin/main`，只准在 `HEAD` 已經被某支
       `origin/nightly/*` 包含、而且工作樹乾淨時（09-23 那晚 agent 自己驗過再做的那一步，這裡改成守門驗）。
  - 其餘擋：`commit`（訊息不符或有別的改動）、`push`（強推、推別的分支）、`stash`、`reset`（上面那一種以外）、
    `rebase`、`cherry-pick`、`revert`、`restore`、`clean`、`rm`、`mv`、`add`（別的檔）、`checkout`（`main` 以外，
    含 `-b`）、`switch`、`tag`、`worktree`、`pull`、`merge`（上面那一種以外）……
- 引號沒關、拆不開的指令擋，理由寫明是拆不開。

**Write／Edit／MultiEdit／NotebookEdit** 只准寫 repo 根目錄的五個交棒檔（`pulse-nightly.py` 的
`ROOT_RESULT_FILES`，從那裡讀，不另抄一份）。寫別的檔一律擋，包括 scratchpad 裡的產生器腳本：
09-23 那晚寫了三支產生器、再用 Bash 跑它們，跟直接寫交棒檔的結果一樣，只是多一層沒人審的程式碼。

擋下時 exit 2，stderr 寫明擋了哪一段、為什麼、該怎麼做（例如「退件寫進摘要」「收尾照實說工作樹留了什麼」）。

### 為什麼 commit 不是一律擋

平台 Stop hook 不看 `stop_hook_active`，條件不滿足就每一輪都擋（anthropics/claude-code#69201 記的就是
這個形狀的死循環）。一律擋 commit，工作樹上那個 driver 寫的狀態檔永遠在，agent 會卡在收尾燒 token。
所以這一層不跟平台打架，而是把平台要的東西收窄成**唯一一種、可以機械驗的寫法**：只 commit 狀態檔、
訊息固定、推回原本該去的地方。

訊息刻意不用 `nightly: enrich` 開頭、也不用資料鏈的 `chore: nightly refresh`：`pulse-monitor.py` 的
`night_shift_commit_days()` 認夜班看的是作者 `ai-pulse-enrich` 或訊息前綴 `nightly: enrich`，
一顆只有狀態檔的 commit 不能讓「潤稿鏈缺日」的警報變綠。

## Stop：收尾要原樣帶 driver 的摘要

同樣三個條件（這裡的第 3 條換成「今天的狀態檔存在」）成立時，從狀態檔組出 `summary_lines()` 的前段
（標題、每一段一行、寫作端成本；不含尾端的完整輸出），逐行比對這個 session 所有 assistant 訊息的文字：

- 比對前兩邊都拿掉 `**` 與反引號、把連續空白壓成一格，**整行相等才算**。「`enrich-apply noted rc=1`」後面
  加一句「（第二輪重跑時正確拒寫）」就不算同一行：09-23 那晚就是這樣把拒寫改寫成正常。
- 看整個 session，不只最後一則：平台 hook 攔過之後，最後一則常常只是一句回顧，摘要貼在前面。
- 少任何一行就 exit 2，stderr 列出缺的行並叫它跑 `python3 scripts/pulse-nightly.py summary` 原樣貼上。
  `stop_hook_active` 為真時只印不擋，不跟自己打架。
- 今天（UTC）沒有狀態檔是明寫的放行分支：driver 一次都沒跑到，沒有摘要可以比，那晚要看的是 run log。

## 成本帳：守門之外唯一會 commit 的程式

`.claude/settings.json` 的 `Stop` 有兩條：這支守門（`nightly-guard.py stop`）與成本帳
（`scripts/nightly-cost.py`）。成本帳讀 transcript 算這一晚的 token 與等價 USD，寫進
`_probe/nightly-cost.jsonl`，**自己 commit、自己推上 main**。算法、牌價與帳本格式在
`references/nightly-driver.md`〈一晚花多少錢，要是一個被記錄的量〉，這裡只講它跟守門的關係。

**它不經過守門，因為守門管的是 agent 的工具呼叫。** PreToolUse 只在 agent 用 Bash、Write、
Edit 這些工具時觸發；hook 程式自己跑的 `git` 是平台叫起來的子行程，不是工具呼叫，守門看不到，
也不該看到。成本帳要是交給 agent 去 commit，就又回到「不准做的事寫在 prompt 裡」那個形狀，
而且得替它在守門上多開一個出口。所以把它做成一段確定性的程式，條件寫死在碼裡：

- **只在雲端半夜潤稿 routine 作用。** 判斷跟守門同一套（`CLAUDE_CODE_REMOTE == "true"`、
  transcript 第一則使用者訊息含 `ROUTINE_MARKER`），import 守門的函式與常數，不另抄一份。
  不符合就 exit 0、不寫任何檔。transcript 路徑只取 hook stdin 的 `transcript_path`，不自己找；
  讀不到就在 stderr 印原因、exit 0。
- **先檢查、後寫檔。** `git status --porcelain` 有任何帳本以外的改動（最常見的是 driver 寫的
  狀態檔還沒被 agent commit）就整個跳過：不寫帳本，stderr 印那份清單，等下一次 Stop 再記。
  agent 照平台 hook 的要求 commit 完狀態檔之後，平台會再觸發一次 Stop。不在 `main` 也跳過。
- **工作樹乾淨才寫帳本。** 內容跟 `HEAD` 一樣就不 commit；否則只 `git add _probe/nightly-cost.jsonl`，
  用 `ai-pulse-cost` 這個作者 commit `chore: nightly cost <UTC 當天>`，再 `git push origin HEAD:main`。
- **作者刻意不是 `ai-pulse-enrich`。** `pulse-monitor.py` 的 `night_shift_commit_days()` 認那個
  作者當作「那天夜班有推」。成本 commit 每晚都會有，用同一個作者的話，潤稿鏈整晚沒推上 main，
  缺日警報照樣是綠的。訊息也不用 `nightly: enrich` 開頭，理由同狀態檔 commit。
- **失敗不重試、不強推。** commit 失敗就把帳本還原成 `HEAD` 那一版（`HEAD` 沒有這個檔就刪掉）；
  push 失敗就留著本機那顆 commit，stderr 印原因，平台的 Stop hook 會要 agent 推，守門放行
  站在 `main` 上的 `git push`。**hook 結束時工作樹上的帳本絕不能是 dirty**：守門給平台 Stop hook
  的出口只准狀態檔，帳本一髒，`git add`／`git commit` 那兩個出口就被堵死，agent 會卡在收尾。
- **所有失敗都 exit 0。** 成本帳記不到不擋 session 結束，但原因一定印在 stderr，不安靜吞掉。

**已知的競態。** 同一個 Stop 事件的兩支 hook 並行，平台自己的 Stop 檢查可能在成本帳
commit／push 完成前看到改動，多擋一輪。多一輪只會讓帳本在下一次 Stop 被取代成更完整的
數字，不掉資料；上線第一晚看 run log 判讀有沒有多出來的那一輪。

## 這一層不保證什麼

- **不是沙箱。** `python3 -c` 裡叫 `subprocess`、寫進別的直譯器再執行，這一層看不到。它擋的是
  五晚記錄到的那種即興（照著平台或自己的推理，直接下指令），不是存心繞過。
- **不保證 routine prompt 的身分句沒被改。** 改了之後 PreToolUse 整晚不擋；Stop 那一道只能在收尾時把這件事講出來，擋不回已經發生的事。
- **不保證另外兩個 routine。** 它們沒有這個身分句，守門對它們一律放行。
- **不取代 driver 的兩道關。** commit 前的分支與白名單檢查照舊在 driver 裡，這一層管的是 agent 自己下的指令。
- **routine prompt 第 4 步（自己開修碼分支並 push）會被擋。** 那一步跟排程 agent 的常設授權
  （只准推資料 commit）相牴觸，守門照常設授權走；prompt 那一步要一起改成「寫進摘要」。
