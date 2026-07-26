# Event 上的兩個時間，與「不要拿外面的時鐘量自己的鏈」

## 一句話

`happened_at` 是**外面的世界什麼時候發生這件事**；`ingested_at` 是**我們什麼時候
第一次把它寫進 vault**。監控自己的鏈跑了沒，只能用後者。

## 為什麼要分開寫（2026-07-26 的實際事故）

那天 GitHub Actions 每兩小時紅一次。唯一的訊息是：

```
[alert] 有事件未 enrich 已放 4 天（門檻 2）——夜間潤稿那條鏈可能沒跑到
```

三則都是 AMD 的事件，`git log --diff-filter=A` 顯示它們是**當天早上 06:41 才進
vault** 的——來自那天凌晨才併進去的 `src-amd-ir`。夜間潤稿鏈不可能碰到它們，
它們前一晚還不存在。

`pulse-monitor.py` 當時是這樣算年紀的：

```python
d = _as_date(fm.get("happened_at")) or _as_date(fm.get("date"))
age = (today - d).days
```

`happened_at` 是新聞的發布日。AMD 那則 partnership 是 07-22 發的，所以它**一進庫
就自帶「4 天大」**，當場撞穿門檻 2。

也就是說：**每新增一條會補歷史的來源，CI 就會立刻紅，而且會一直紅到有人手動
把那些事件潤完為止。** 這是我們自己給自己裝的假警報。跟 `is_backfill` 那個坑
（`fix/backfill-flag-erased-by-second-run`）是同一種病——拿外部世界的時間軸，去量
「我們自己的鏈有沒有在動」。

## 兩個欄位

| 欄位 | 意思 | 誰寫 | 回答什麼問題 |
|---|---|---|---|
| `happened_at` | 事情在外面發生 / 被發布的時刻 | `pulse-cluster` 從訊號的 `published` 取 | 這是不是新聞？freshness 給幾分？ |
| `ingested_at` | 這則 Event note **被建立**的時刻 | `pulse-cluster` 建立時寫一次 | 我們把它放著沒處理多久了？ |

訊號層（`_corpus/*.jsonl`）本來就有 `first_observed_at`——「probe 第一次看到這一筆」。
`ingested_at` 就是取建立這則 Event 的那個訊號的 `first_observed_at`。Event 層另外
取一個名字，是因為在 Event 上講「first observed」會跟訊號那個混淆：一則 Event 可以
在建立之後好幾天才綁到新證據，那些新證據各有自己的 `first_observed_at`，但 Event
進庫的時刻只有一個。

## 黏住不動（sticky）

`ingested_at` **寫一次就不再改**。`pulse-cluster` 每次 rescore 都會整份重寫非
enriched 事件的 frontmatter，任何沒被明確帶過去的欄位都會被抹掉——這正是
`fix/backfill-flag-erased-by-second-run` 修的那個坑。所以 reload 既有 note 時要把
`ingested_at` 讀回 `Event` 物件，寫檔時原樣寫回。selftest 有測試釘住「第二次寫入
不會改變 `ingested_at`」。

## 量不到就說量不到

2026-07-26 之前建立的 Event 沒有這個欄位。監控遇到缺值時**不觸警**，另外印一行
「年紀不明 N 則」——紅線 8：量不到就寫量不到，不要拿 `happened_at` 頂替，那正是
要修掉的東西。

歷史事件的回填值來自 git（檔案第一次出現在哪個 commit）：

```
git log --diff-filter=A --format=%aI -- Events/<id>.md | tail -1
```

這是一次性的，不留成腳本：它問的是版控歷史，不是 vault 狀態，讓 pipeline 去
shell out 呼叫 git 只會多一個在別人機器上壞掉的理由。任何人都能用上面那行
逐則驗證回填值對不對。

## 監控怎麼用

`pulse-monitor.py` 的兩個佇列年紀都改吃 `ingested_at`：

- `oldest_unenriched_days` → `--alert-unenriched-days`：**還沒潤稿又在庫裡放了幾天**。
  超過門檻＝夜間潤稿那條鏈沒跑到。
- `oldest_stuck_days` → `--alert-days`：卡在 `review` 又在庫裡放了幾天。

兩個問的都是「**我們**放了多久」，所以兩個都不該看新聞的發布日。一則五年前的
舊聞今天被收進來，它在我們的佇列裡就是零天大。

## 這條警報為什麼值得這麼小心

死人開關是用 `exit 1` 讓 GitHub 寄失敗通知的，而排程是每兩小時一班——一條誤報
一天會紅 12 次。`data-refresh.yml` 裡關於 `--alert-no-source` 的註解早就寫過這件事：

> 否則 CI 天天紅，人只會學會忽略 CI，連帶忽略真正的回歸。

一條會被新增來源自動觸發、而且沒有自癒路徑的警報，比沒有警報更糟。
