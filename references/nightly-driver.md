# 夜班的階段機器：把十七步從散文變成碼

> 這份是**規格**，`scripts/pulse-nightly.py` 是它的實作，`scripts/enrich-runbook.md`
> 是寫的人那一邊的規則。三者不一致時以本檔為準，**先改本檔再改碼**（紅線 9）。

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
| 2026-07-24 | Actions 誤點 96 分鐘，潤稿端 clone 到昨天的 repo，worklist 空，整晚「正常無事」 | 步驟 0 的前置檢查是階段之一，補跑與否記在狀態檔 |
| 2026-08-16 | 「今晚沒素材」跟「今晚有素材而沒寫」在 git 裡長得一模一樣 | 每一段的結果都留痕，包含被跳過的那些 |

五條事故，一個形狀：**判斷的規則寫在散文裡，而散文每晚被重新讀一次。**

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
| 0 | `precheck` | run | 今日 `_corpus/<date>/` 在不在；不在就補跑 robots-recheck → probe → score → cluster | 無 |
| 1 | `enrich-prep` | run | `pulse-enrich-prep.py` | after precheck |
| 2 | `enrich-write` | narrative | 事件潤稿（六層 prose） | needs enrich-prep；worklist 非空 |
| 3 | `enrich-apply` | run | `--dry-run` 再正式 | **needs** enrich-write |
| 4 | `gate` | run | `pulse-gate.py` | **after** enrich-apply（整段跳過照跑） |
| 5 | `dashboard` | run | `pulse-dashboard.py` | needs gate |
| 6 | `digest-prep` | run | `pulse-digest-prep.py` | **needs gate**（這一格是 2026-08-16 那次事故的本體） |
| 7 | `digest-write` | narrative | 每日精選（空日寫 retrospective，一樣要寫） | needs digest-prep |
| 8 | `digest-apply` | run | `--dry-run` 再正式 | **needs** digest-write |
| 9 | `digest-gate` | run | `pulse-digest-gate.py` | after digest-apply |
| 10 | `narrative-prep` | run | `pulse-narrative-prep.py` | needs gate |
| 11 | `narrative-write` | narrative | 主線 `now`／`next` | needs narrative-prep；worklist 非空（多數夜晚是空的） |
| 12 | `narrative-apply` | run | `--dry-run` 再正式 | **needs** narrative-write |
| 13 | `github-desc-write` | narrative | 榜單中文描述。**清單由 Actions 那班準備**，driver 只讀 | 無（worklist 存在且非空） |
| 14 | `github-desc-apply` | run | `--dry-run` 再正式 | **needs** github-desc-write |
| 15 | `title-write` | narrative | Event 中文標題。清單同樣由 Actions 準備 | 無（worklist 存在且非空） |
| 16 | `title-apply` | run | `--dry-run` 再正式 | **needs** title-write |
| 17 | `render` | run | `pulse-render.py` | 無（前面 stop 會直接終止整輪） |
| 18 | `commit` | commit | 先擋白名單外的改動，再 `git add -A` ＋ 有變更才 commit ＋ push | after render |
| 19 | `monitor` | run | `pulse-monitor.py --top 5`，**不准帶警報旗標** | 無（排在 commit 之後：摘要要帶推上去之後的狀態） |

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

## 這一層不保證什麼

- **不保證寫的人寫得好。** driver 檢查的是清單對不對得上、JSON 合不合法，不看內容
  品質。那是 apply 的退件規則與人的事。
- **不保證跑得完。** 中途 `stop` 就是停住，狀態檔留在那裡，明晚重跑。enrich 與敘事
  刷新都冪等，這是 runbook 原本就有的性質，driver 沒有改變它。
- **不保證 Actions 那一班有跑。** `precheck` 只看今日 corpus 在不在，不在就補跑抓取。
  補跑成功不代表 Actions 沒事，那是兩件事，摘要要分開寫。
- **不取代 runbook。** 寫的那一方仍然照 runbook 寫。這一層拿走的是順序、exit code
  判讀、摘要組裝這些不該由模型每晚重做一次的東西。
