# 夜班的階段機器：把十七步從散文變成碼

> 這份是**規格**，`scripts/pulse-nightly.py`（階段機器）與 `scripts/nightly-shell.sh`
> （外殼）是它的實作，`scripts/enrich-runbook.md` 是寫的人那一邊的規則。
> 不一致時以本檔為準，**先改本檔再改碼**（紅線 9）。

## 為什麼要有這一層

`enrich-runbook.md` 是一份 356 行的散文，它要求執行的那一方照著跑十七步，而**其中
十幾步是純腳本**。夜班每一晚都在做同一件事：讀那份散文、判斷現在該跑哪一支、
讀它的 exit code、決定那個數字是「沒事」「沒東西」還是「出事了」。

那是把確定性工作交給模型。這個 repo 記錄過的夜班事故，幾乎全發生在這一層：

| 日期 | 發生什麼 | 這一層怎麼擋 |
|---|---|---|
| 2026-08-12 | prep 沒跑，拿**上一班留在 repo 裡的** worklist 把昨天已潤好的 10 則整批重寫，當天該潤的 7 則一則沒碰。commit 訊息看起來很正常 | worklist 的新鮮度由狀態檔記，交棒時對帳 |
| 2026-08-16 | `digest-prep` 跑在 `gate` 之前，挑不到東西**而且不報錯**，只安靜產出一份空清單 | 順序寫死在階段表，前置沒過就不跑 |
| 2026-07-28 | `github-desc-apply` 回 3（收到了但一條都沒過關）被寫成「今晚沒東西要翻」，連續好幾晚沒人發現 | exit code 的語意寫成表，判讀只寫一次 |
| 2026-07-24 | Actions 誤點 96 分鐘，潤稿端 clone 到昨天的 repo，worklist 空，整晚「正常無事」 | `precheck` 是階段之一，今日語料沒到就停（2026-09-24 起不補跑，見下方〈precheck：語料沒到就停，不補抓〉） |
| 2026-08-16 | 「今晚沒素材」跟「今晚有素材而沒寫」在 git 裡長得一模一樣 | 每一段的結果都留痕，包含被跳過的那些 |
| 2026-09-20 | 雲端排程把 session 的工作樹 checkout 在一支臨時分支上，不是 `main`；commit 那一關擋得住，但擋在 commit 才發現，敘述工作早就寫完、錢也花了 | `align-main` 排在最前面，在花任何一分錢寫敘述之前就把「跑在哪一支」定案（見下方〈對齊 main〉） |
| 2026-09-22、09-23 | 雲端排程比誤點的 Actions 早到，`precheck` 自己補跑抓取；Actions 中途把同一天的語料推上 main，夜班最後 push 被拒，兩晚成果都落在 `nightly/` 備援分支 | `precheck` 不再補跑，語料沒到就停（見下方〈precheck：語料沒到就停，不補抓〉） |

七條事故，一個形狀：**判斷的規則寫在散文裡，而散文每晚被重新讀一次。**

## 兩種階段

**`run`**：跑一支腳本。driver 知道它的 exit code 表、要從輸出抓哪一行進摘要。

**`narrative`**：停下來交棒。driver 印出「現在要誰寫什麼、清單在哪、幾筆、結果寫到哪個檔」，然後**以 exit 10 結束**。寫的那一方（排程 agent、互動 session、或人）寫好 JSON 再叫一次 driver，它從狀態檔接回去。

exit 10 是刻意選的：0 是跑完、1 是有事要人看、2 是壞了，**10 是「還沒完，等你」**。三種在 shell 裡分得開，排程那一層才寫得出正確的迴圈。

## 階段表

順序就是 runbook 的順序。**依賴有兩種，混成一種會讓整條鏈在最平常的夜晚停掉**：

```
after   順序依賴：前面那一段沒壞就往下走。前面被跳過是正常的
needs   產出依賴：前面那一段必須真的產出了東西，否則這一段無事可做
```

多數夜晚 `enrich-worklist` 是空的（沒有新事件要潤），那一晚 `enrich-write` 與
`enrich-apply` 都會 `skipped`。若 `gate` 也算成「前置沒產出」而跟著跳過，
dashboard、digest、narrative、render 會一路連帶跳掉，**整條鏈在最平常的一晚等於
沒跑**，而狀態檔上每一格都寫著 `skipped`，看起來像一切正常。所以 `gate` 對
`enrich-apply` 是 `after`。

反過來 `digest-prep` 對 `gate` 是 `needs`：它挑的是「今晚通過門禁上線」的事件，
gate 沒真的跑過就挑不到，而且不會報錯（2026-08-16）。每一個 `*-apply` 對它自己那一段
`*-write` 也是 `needs`：那一段被跳過就沒有 result 檔可以寫回。

| # | id | 類型 | 做什麼 | 前置 |
|---|---|---|---|---|
| 0 | `align-main` | align | **先確認站在 `main`、跟 origin 對齊**，再清掉根目錄殘留的敘述產物（見下方〈對齊 main〉） | 無（第一步，前面 stop 會直接終止整輪） |
| 1 | `precheck` | precheck | 今日 `_probe/<date>/report.md`（Actions 那班 probe 的產物）在不在；**不在就 stop，不補跑抓取**（見下方〈precheck：語料沒到就停，不補抓〉） | 無 |
| 2 | `enrich-prep` | run | `pulse-enrich-prep.py` | after precheck |
| 3 | `enrich-write` | narrative | 事件潤稿（六層 prose） | needs enrich-prep；worklist 非空 |
| 4 | `enrich-apply` | run | `--dry-run` 再正式 | **needs** enrich-write |
| 5 | `gate` | run | `pulse-gate.py` | **after** enrich-apply（整段跳過照跑） |
| 6 | `dashboard` | run | `pulse-dashboard.py` | needs gate |
| 7 | `digest-prep` | run | `pulse-digest-prep.py` | **needs gate**（這一格是 2026-08-16 那次事故的本體） |
| 8 | `digest-write` | narrative | 每日精選（空日寫 retrospective，一樣要寫） | needs digest-prep |
| 9 | `digest-apply` | run | `--dry-run` 再正式 | **needs** digest-write |
| 10 | `digest-gate` | run | `pulse-digest-gate.py` | after digest-apply |
| 11 | `narrative-prep` | run | `pulse-narrative-prep.py` | needs gate |
| 12 | `narrative-write` | narrative | 主線 `now`／`next` | needs narrative-prep；worklist 非空（多數夜晚是空的） |
| 13 | `narrative-apply` | run | `--dry-run` 再正式 | **needs** narrative-write |
| 14 | `github-desc-write` | narrative | 榜單中文描述。**清單由 Actions 那班準備**，driver 只讀 | 無（worklist 存在且非空） |
| 15 | `github-desc-apply` | run | `--dry-run` 再正式 | **needs** github-desc-write |
| 16 | `title-write` | narrative | Event 中文標題。清單同樣由 Actions 準備 | 無（worklist 存在且非空） |
| 17 | `title-apply` | run | `--dry-run` 再正式 | **needs** title-write |
| 18 | `render` | run | `pulse-render.py` | 無（前面 stop 會直接終止整輪） |
| 19 | `commit` | commit | **先確認站在 `main`**，再擋白名單外的改動，然後 `git add -A` ＋ 有變更才 commit ＋ push；main push 失敗改推 `nightly/<日期>-<sha>` 分支（見下方〈push main 失敗時的備援〉），回 `noted` 不是 `stop` | after render |
| 20 | `monitor` | run | `pulse-monitor.py --top 5`，**不准帶警報旗標** | 無（排在 commit 之後：摘要要帶推上去之後的狀態） |

`monitor` 那一條的禁令不是這裡新增的：判準讀本地 `git log`，在 push 之前它會讀到
自己剛建、還沒推出去的那顆 commit 然後回一盞綠燈。理由全文在
`references/health-alarms.md`，selftest 另有一條擋 runbook 出現帶旗標的呼叫。

## exit code 怎麼判讀

每一支的 code 意思不一樣，這張表是唯一的真相源（**從碼讀出來的，不是從 runbook 抄的**）：

| 腳本 | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `pulse-enrich-prep` | ok | | 壞了 → stop | |
| `pulse-enrich-apply` | ok | **有拒寫**（已潤過的事件）→ 記進摘要，繼續 | | |
| `pulse-digest-prep` | ok | | | |
| `pulse-digest-apply` | ok | 退件／已存在 → 記進摘要，**不擋 push** | 壞了 → 記進摘要，**不擋 push** | |
| `pulse-digest-gate` | ok | 有 digest 的 status 不屬三桶（檔案壞了）→ 記進摘要，繼續 | | |
| `pulse-narrative-prep` | ok | | 壞了 → stop | |
| `pulse-narrative-apply` | ok | 有退件 → 記進摘要，繼續 | 壞了 → stop | |
| `pulse-github-desc-apply` | ok | | 榜與 worklist 都讀不到（**量不到**） | **收到了但一條都沒過關** |
| `pulse-title-apply` | ok | 有退件 → 記進摘要，繼續 | 壞了 → stop | |
| `pulse-gate` | ok | | 壞了 → stop | |
| `pulse-dashboard` | ok | 壞了 → stop | | |
| `pulse-render` | ok | | | |

digest 那兩條的「不擋 push」是 runbook 寫明的過渡期豁免：`Digests/` 目前還沒有下游
消費者，寫不出來不影響當天的潤稿與發布。**豁免不等於靜音**，結果照樣進摘要與狀態檔。
等 `/daily/` 那條線接上之後這個豁免要拿掉，那天要同時改本檔與 runbook。

`github-desc-apply` 的 2 與 3 **一定要分開**。2 是抓取鏈那邊出事，3 是這一段沒有成果。
2026-07-28 之前這支一律回 0，於是「25 條全退」在摘要上長得跟「今晚沒東西要翻」一樣。

## 交棒協定

driver 停在 narrative 階段時，印出的東西要讓接手的一方**不必再讀 runbook 也知道要做什麼**：

```
[narrative] enrich-write
  清單：_probe/enrich-worklist.json（7 筆，prep 於 2026-09-15T19:12:03Z 產出）
  規則：scripts/enrich-runbook.md〈流程 步驟 2-3〉與〈speak-human-tw 規則摘要〉
  產出：enrich-result.json（dict keyed by event_id）
  紅線：判斷不由你決定發不發、只依證據不編造、去 AI 口吻
```

**規則本身不複製到這裡。** runbook 是那一邊的正本，driver 只指過去。同一句規則兩份，
改一處忘一處，而讀的人不知道哪份是真的。

收回來的時候 driver 檢查三件事，任一不過就 exit 2 並指名：

1. 結果檔存在且是合法 JSON
2. **它對應的是這一輪的 worklist**（狀態檔記著 prep 的時間戳與筆數）
3. 結果的 key 是 worklist 的子集（多出來的 key 代表寫的人拿錯清單）

第 3 條有兩種模式，因為五段的產物形狀不一樣：

```
keyed    dict keyed by worklist 的 key 欄位。enrich（id）、narrative（slug）、
         github-desc（full_name）、title（id）四段都是這種，比對 key 的子集關係
single   單一物件。digest 那一段交的是一篇文章的 sections[]，沒有 key 可以比對，
         只驗它是一個非空的物件，內容由 pulse-digest-apply.py 的退件規則管
```

`digest-write` 另外有一條：**worklist 是空的也要停下來寫**。空日不是「沒東西可寫」，
是「今天寫的是回頭看」（`references/digest-framework.md` §四）。其餘四段清單空就跳過。

第 2 條是 2026-08-12 那次事故的補丁。那一晚的 worklist 是上一班留在 repo 裡的，
而它躺在那裡是因為它進版控，不是因為它是今天的。

## 狀態檔

`_probe/nightly-run.json`，**進版控**，跟 `_probe/digest-apply-last.json` 同一個理由：
一晚一次 diff 不是噪音，而「今晚沒事做」跟「今晚沒跑到」在 git 裡不能長得一樣。

時間戳一律走 `lib/clock.utc_stamp()`（`2026-09-15 19:08Z`，分鐘精度）。**腳本不自己
取日期**，那是 `lib/clock.py` 的獨佔職責，selftest 有一條掃全 repo 擋這件事。

```json
{
  "date": "2026-09-15",
  "started_at": "2026-09-15 19:08Z",
  "updated_at": "2026-09-15 19:41Z",
  "finished": false,
  "stages": [
    {"id": "precheck", "status": "ok", "note": "今日 corpus 已就緒", "at": "..."},
    {"id": "enrich-prep", "status": "ok", "note": "待 enrich=7 已跳過=3",
     "worklist": {"path": "_probe/enrich-worklist.json", "count": 7, "at": "..."}},
    {"id": "enrich-write", "status": "waiting"}
  ]
}
```

`status` 六種，**各自代表不同的動作**，不要合併：

```
ok        跑完，沒事
skipped   前置不成立而跳過（例：worklist 是空陣列）→ 這是正常的一晚
absent    該有的東西不存在（例：Actions 沒準備清單）→ **這不是 skipped**，是別人出事了
waiting   停在這裡等人寫
noted     跑了，有事要人看（退件、拒寫、壞檔），但不擋後面
stop      壞了，整條停住
```

`skipped` 與 `absent` 分開是 runbook 反覆強調的那件事：清單是空陣列代表今晚沒東西要
做，檔案不存在代表上游那一班出事了，兩者要人做的動作完全不同。

## 摘要

runbook 步驟 18 列了六七行必須貼進摘要的輸出，漏掉 prep 那一行就**證明不了清單是
今晚產的**。driver 從狀態檔組這份摘要，不靠人記得貼。

摘要寫進 `_probe/nightly-run.json` 之外，也印到 stdout 供呼叫端轉發。**它要落在一個
人看得到的地方**，那是呼叫端的責任，不是這一層的。

## 外殼：迴圈是 shell 的

`scripts/nightly-shell.sh` 是呼叫端。它做的事只有一件：driver 回 10 就把那份交棒訊息
原樣餵給一個**獨立的** `claude -p`，寫完再叫 driver 接回去。

```
driver 回 10 ──► claude -p（只有 Read/Write/Glob/Grep）──► 寫出 result 檔 ──► driver 接回
```

**一棒一個 session，不是一個 session 裡開 subagent。** headless 開得了 subagent
（2026-09-15 實測 `spawned: 1, completed: 1`），但用不到，而且一棒一個 session 更好：

```
context 最小   每一棒只看到自己那一段的清單，看不到別段的
成本可預測     五段各自獨立，一段爆掉不會把整晚的 context 拖著
失敗隔離       某一棒寫壞了，driver 在對帳時擋下來，其餘的狀態還在
```

**寫作端的工具白名單是它能造成的傷害上限**：`Read Write Glob Grep`，沒有 Bash。
拿不到 Bash 就跑不了 apply、commit、push，所以「判斷不由你決定」那條紅線不只是
寫在 prompt 裡的一句話，是它辦不到的事。selftest 有一條擋 `bypassPermissions`
與 `--dangerously-skip-permissions`：那兩個旗標會讓白名單失效，而失效的時候
畫面上什麼都看不出來。

**派工第一行是身分句**（「你是 ai-pulse 夜班的寫作端，不要跑任何啟動序列」）。
少了它，全域 `CLAUDE.md` 的啟動序列會讓寫作端去讀 vault 的 profile 與日誌，
而那一段工作一個字都用不到。

**交棒次數有上限**（`NIGHTLY_MAX_HANDOFF`，預設 8）。沒有上限的迴圈會在 driver
因為某個沒想到的狀態一直回 10 的時候，整晚反覆叫 claude。那是會燒錢的失敗模式，
而且它不會報錯。

所以整條鏈的分工是：**迴圈是 shell 的、判斷是 driver 的、寫作才是 LLM 的**。
這個 repo 對外的承諾（runtime 0 LLM 判斷）在這裡照樣成立：LLM 一個判斷都不做，只寫字。

### precheck：語料沒到就停，不補抓

**這是 2026-09-24 改的。** 在那之前，`precheck` 看到今日 `_corpus/<date>/` 不在，會自己
補跑一次 robots-recheck → probe → score → cluster。那條後路是 2026-09-15 在本機 launchd
上設計的，當時本機網路全通，補跑抓到的東西跟 Actions 一樣。搬到雲端排程
（`claude.ai/code/routines`）之後，這個前提沒了，而沒有任何東西檢查到：

```
2026-09-23 雲端補跑   33 條來源  200 的只有 2 條（src-anthropic-news、src-msr-blog）
                      24 條 robots.txt 取不到、2 條 GitHub http 403、5 條 dormant
                      官方線 50 則
同一天 Actions         438 則，四條線
```

所以補跑在雲端只要走到就是壞的，差別只在壞成哪一種：

- **撞到 Actions。** Actions 誤點落在夜班執行窗裡，會把同一天的語料先推上 `main`，夜班最後
  push 必然 non-fast-forward。2026-09-22、09-23 兩晚都是這樣，成果落在 `nightly/` 備援分支，
  而備援分支併不回去：兩邊抓的是同一天，`_corpus/<date>/`、`_probe/state.json` 等檔一定衝突。
  在 push 那一步加「fetch 後重推」救不了同一個衝突。
- **沒撞到。** 夜班先推，main 上就多一份只有兩條來源的語料，當晚的潤稿與每日精選用它做，
  摘要只多一行「今晚由潤稿端補跑抓取」。2026-09-17、09-21 兩晚是這樣（各 10 則，同一天 Actions
  438、458 則）。

補跑原本擋的是 2026-07-24 那種空轉：比 Actions 早到，拿昨天的 repo 整晚「正常無事」。那件事
現在由停下來擋：**語料沒到就 stop**，note 指名缺哪一天，exit 2。

「語料到了沒」看的是 `_probe/<date>/report.md`，不是 `_corpus/<date>/`。`pulse-probe.py` 只替有
資料列的來源寫 `_corpus/<date>/<source>.jsonl`，整班都回 304 或 0 筆的時候那個目錄根本不會建，
但報告、`source-runs.jsonl` 與 commit 照寫、exit 0。拿目錄當證據，會把合法的空班誤判成 Actions
還沒到，整晚停掉（連空日該寫的 retrospective 都沒寫）。報告跟 corpus 是同一次執行寫的，有 corpus
的日子一定有報告，所以換判準只在空班那一天換結局。這也是 `lib/corpus.run_days()` 判「這班跑過了」
用的同一個判準，報告因此走原子寫入（`references/atomic-writes.md`）。

已知不擋的一種：Actions 誤點到跨 UTC 午夜，報告寫的是前一天、夜班算的是後一天，會停住。
近半個月最晚 20:10Z，離午夜還有近四小時；真的發生是大聲停住、隔天那一班照樣把待潤事件挑回來，
不為它加判斷。stop 不寫 `finished`，同一個
UTC 日之後再觸發一次，`precheck` 會重新判斷，不需要 `--reset`。**重新判斷不等於重新拉資料**：雲端排程每次觸發都是全新 clone，
下一次拿得到 Actions 剛推上的語料；在同一個工作樹手動重跑則要先自己 `git pull --ff-only`，driver 不替你拉。
`align-main` 在同一輪只跑一次，而且站在 `main` 上時本來就不 fetch，它不是用來拉新資料的。

**什麼時候觸發是排程那一層的責任，不在這支 driver 裡。** 夜班要在 `data-refresh.yml` 那一班
收工之後才開跑，而 Actions 的 cron 是「最早不早於」，近半個月實際開跑落在 17:53–20:10Z，
排在 16:00Z。固定時鐘挑哪個時間都是在賭誤點，所以雲端排程改成由 Actions 收工的事件觸發
（GitHub `workflow_run` completed），只認 `schedule` 觸發的那一班：白天手動 `workflow_dispatch`
一次也觸發夜班的話，那個 UTC 日的一輪會在晚上真正的那班之前就用掉。這一段 driver 驗不了，
驗得到的只有「語料沒到就不做」。

### 對齊 main：開跑前，不是 commit 前

**這是 2026-09-20 才長出來的一關。** 雲端排程（`claude.ai/code/routines`）把 session
的工作樹 checkout 在一支平台自建的臨時分支上（例如 `claude/gifted-faraday-nzxg63`），
不是 `main`。`align-main` 加之前，這件事要等到 `commit` 那一關的
`on_target_branch()` 才會被發現——但那時候敘述工作（`enrich-write` 到
`title-write`）早就跑完、`claude -p` 的錢也花了，整晚的成果因為卡在 commit
而全部推不上去。09-18、09-19 兩晚能推上 main，是那兩晚的寫作端自己讀了
`pulse-nightly.py` 的碼、臨時做了 `git checkout main && git merge --ff-only
origin/main` 才過的，**不是這支 driver 保證的**；09-20 沒有人做這件事，
就整晚白跑。`align-main` 把同一個對齊挪到最前面，在花任何一分錢之前就把
「跑在哪一支」定案。

**只在工作樹乾淨時切分支。** 站在別的分支又有未提交改動，代表有人正在用這個
工作樹做別的事，driver 沒有能力判斷那些改動該留還是該丟，不猜，停下來——跟
下面〈commit 前的兩道關〉的「地點錯了，內容再乾淨也是推到錯的地方」是同一個
判斷，只是這裡反過來：**內容不乾淨，連地點都不猜著換。**

**對齊失敗（`git fetch`／`checkout`／`merge --ff-only` 任何一步非零）一律 stop**，
不猜怎麼合併。`merge --ff-only` 理論上不該失敗——這支分支是這次 session 才剛從
遠端建的，本地 `main` 應該是 `origin/main` 的祖先——但「理論上不該發生」正是這個
repo 記過最多次的一句話，真的發生時交給人，不是找一種合併策略把它兜過去。

**同一次順手清掉根目錄殘留的敘述產物**（`ROOT_RESULT_FILES`：`enrich-result.json`、
`digest.json`、`narrative-result.json`、`title-zh-result.json`、
`github-desc-result.json`）。這五個檔只該在同一輪的兩次 `run` 之間短暫存在——
2026-09-15 一次手動實跑後忘了收，本機排程往後三晚都拿它們當成「這一輪的結果」
對帳，一直卡在 `enrich-write`。清理跟分支對齊放進同一個階段，是因為兩者要的
「只做一次」保證完全一樣：`align-main` 一旦記成 `ok`／`noted`，同一個 UTC 日
之後每次 `run` 都會跳過它，天然不會清到正在交棒中的檔。**清掉的東西要留痕**：
回傳被刪的檔名，寫進這一段的 note，不要默默刪掉——「今天特別乾淨」跟「有東西
被默默清掉」在摘要上不能長得一樣。

### commit 前的兩道關，順序不能換

**一、站在哪一支。** 排程跑的是本機工作樹，而工作樹會停在人上次切過去的地方：
某支 feature 分支、某次 review 留下的 detached HEAD 都算。不是 `main` 就 stop，
並說出實際在哪一支。

這擋的是 2026-09-11 那次事故的**另一半**。那一晚活做完了、commit 也建了，而它落在
一支 session 自己的分支上、沒有到 `main`，三天沒有人知道。那次的原因在 Cowork 那一邊，
搬到本機之後同一個形狀換一個入口回來：只要工作樹剛好停在別的分支，夜班就會把一整晚
的資料 commit 推到那裡去。夜班沒有能力判斷那支分支該不該收，所以不猜，停下來。

**二、改動的路徑。** 白名單外的東西一律不推（碼、CI、`_config` 的判斷邏輯走 PR）。

順序不能換：先確認地點，再確認內容。地點錯了的話，內容再乾淨也是推到錯的地方。

### push main 失敗時的備援：改推分支，不是 stop

2026-09-18 加。這條鏈原本只在本機 launchd 跑，push 失敗的成本是「重試一次」；
但雲端排程（`claude.ai/code/routines`）跑在拋棄式容器裡，**commit 建了、push
不出去，資料就跟著容器一起永久消失**——2026-08-05、2026-09-11 兩次事故都是
這個形狀，只是那時候活還沒做完就先斷在別的地方，這次要擋的是「活做完了、
commit 也建了，最後一步失手」。

所以 `main` push 失敗時不再直接 `stop`：改推 `nightly/<UTC 日期>-<short-sha>`，
status 回 `noted`——資料沒丟，只是要人手動把這支分支併回 `main`。連備援分支
都推不上去才是真的 `stop`。分支名**不沿用**舊 routine 用過的 `claude/` 前綴：
上面〈狀態檔的最後一段不在同一顆 commit 裡〉附近的歷史裡，`references/
health-alarms.md` 記過 9 支 `claude/*` 的舊命名殘留 ref 讓「未收分支」警報分
不清哪些早就進了 `main`，這裡換一個新前綴，不要跟那批混在一起。

推分支「成功」不等於遠端真的收到——這條鏈過去的失效模式就是「自己以為推上去
了」，所以推完要 `git fetch origin` 再 `git branch -r --contains <sha>` 親眼
確認一次，兩者都寫進這一階段的 note。

### 一晚花多少錢，要是一個被記錄的量

外殼用 `--output-format json` 叫寫作端，把 `total_cost_usd` 記回狀態檔那一段的
`cost_usd`，摘要印總額。

**量不到跟 0 不一樣。** 一晚每一段都跳過是真的 0；外殼沒把數字傳回來是量不到。
兩者長得一樣的話，「這條鏈很便宜」跟「沒有人在量」就分不出來，而那是這份文件
從第一行講到現在的同一個形狀。所以摘要那一格在沒量到的時候印的是
「**量不到**（外殼沒有把數字傳回來）」，不是 `USD 0.0000`。

2026-09-15 實測（sonnet，一份 40 則 Event 的 vault）：`title-write` 那一棒
3 筆標題翻譯花 `USD 0.2708`。整晚的量級隨當晚事件數走，`enrich-write` 與
`digest-write` 是兩段大的。

**這一層只負責記，不負責省。** 要不要設上限、超過就只跑 A 與 B3，那是人的決定，
而人要先看得到數字才決定得了。

### 一個 UTC 日一輪，而台北的凌晨屬於前一個 UTC 日

`_probe/nightly-run.json` 的 `date` 用 UTC，一個 UTC 日只跑一輪（enrich 與敘事刷新
本來就冪等）。**台北 04:47 等於 UTC 前一天 20:47**，所以同一個 UTC 日會被兩個不同的
台北日碰到：白天手動跑一次、當晚排程再跑一次，第二次會看到「今天已經跑完」。

那個判斷是對的，**安靜地結束不對**。2026-09-15 差點這樣過去：白天手動 kickstart 跑
了一輪（UTC 03:32），當晚 04:47 那班（UTC 20:47，同一個 UTC 日）會什麼都不做、
一個字都不印，log 上只有一片空白——而「今晚沒事做」跟「今晚沒跑到」在一片空白上
長得一模一樣。

所以第二次碰到的時候印出完整摘要加一句說明，並告訴人 `run --reset` 可以重跑。
**要不要重跑是人的決定**：白天那一輪如果跑在 Actions 之前（像 2026-09-15 那次），
當晚的新事件就要等下一個 UTC 日才潤，延一天；那可能可以接受，也可能不行，
判準這一層不替人決定。

### 狀態檔的最後一段不在同一顆 commit 裡

`monitor` 排在 `commit` 之後（摘要要帶推上去之後的狀態），所以它跑完寫回狀態檔的
那一次，**已經在那顆 commit 之外**。實務上那一段會在下一晚的資料 commit 裡進去。

知道就好，不另外補一顆 commit：多一顆只為了記自己的結尾，成本高於它的價值。
要看某一輪的完整結尾，看本機的狀態檔或 log，不要只看 git。

## 這一層不保證什麼

- **不保證寫的人寫得好。** driver 檢查的是清單對不對得上、JSON 合不合法，不看內容
  品質。那是 apply 的退件規則與人的事。
- **不保證跑得完。** 中途 `stop` 就是停住，狀態檔留在那裡，明晚重跑。enrich 與敘事
  刷新都冪等，這是 runbook 原本就有的性質，driver 沒有改變它。
- **不保證 Actions 那一班有跑。** `precheck` 只看今日 probe 報告在不在，不在就停。
  排程在 Actions 收工之後才觸發夜班，是觸發那一層的責任（見〈precheck：語料沒到就停，不補抓〉），
  這一層只負責「沒到就不做」。
- **不取代 runbook。** 寫的那一方仍然照 runbook 寫。這一層拿走的是順序、exit code
  判讀、摘要組裝這些不該由模型每晚重做一次的東西。
