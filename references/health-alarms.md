# 警報層：什麼算「有一天」、什麼算「量不到」

> 這份文件是**規格**，`scripts/lib/corpus.py` 與 `scripts/pulse-monitor.py`
> 的 `_as_date()` / `health()` / `scan()` 是它的實作。三者不一致時以本檔為準，
> **先改本檔再改碼**（紅線 9）。

## 為什麼要單獨寫這一層

`source-lifecycle.md` 講的是「來源壞掉沒人會知道」。這一份講的是更上面一層、
也更難發現的一種病：**警報自己把自己關掉**。

死人開關（dead man's switch）的價值全押在一個假設上——**沒有動靜的時候它會叫**。
一旦「沒有動靜」這件事本身被量錯，開關不是壞掉，是**變成一顆綠燈**。
壞掉的燈至少會被看見；一顆永遠綠的燈不會，它看起來就跟一切正常一模一樣。

2026-07-26 的 code review 量到三個這種形態的洞（都有可重現的實驗，見下）：

| 現象 | 真相 | 系統顯示 |
|---|---|---|
| `_corpus/2026-07-26/` 是空目錄 | 6 天沒抓到任何東西 | 綠燈，`lag=0` |
| `_corpus/2026-07-30/`（未來日期） | 6 天沒抓到任何東西 | 綠燈，`lag=-4`，而且**永遠**綠 |
| Event 缺 `ingested_at` | 3 則未潤稿卡在庫裡 | `oldest_unenriched_days=0`，不叫 |

三個洞的共同結構是一樣的：**用一個比事實寬鬆的代理指標去代表事實**。
目錄名代理「那天有語料」、`max()` 代理「最久放了幾天」。
代理指標在正常路徑上跟事實重合，所以測不出來；只有在出事的那一天才會分岔，
而那正是唯一需要它準的那一天。

## 算對了不等於會叫：exit code 自己也要有測試

下面三條規則管的都是**算得準不準**。但這一層對外只有一個輸出——
`pulse-monitor.py` 的 exit code。CI 那一步是這樣寫的：

```yaml
python scripts/pulse-monitor.py \
  --alert-unenriched-days 2 --alert-coverage --alert-stale > /dev/null
```

`> /dev/null`。**沒有人在讀那些字**。整條鏈紅不紅，只取決於 `sys.exit(main())`
交出去的那個數字。算得再準，只要那個數字沒變成 1，警報就等於不存在。

2026-07-26 實測：把 `main()` 結尾的 `return rc` 改成 `return 0`，
selftest **222/222 全過**。三個旗標的計算邏輯都有測試，把計算結果轉成 exit code
的那一步一條都沒有——selftest 從來沒有呼叫過 `main()`，只用
`inspect.getsource()` 去比對原始碼字串。比對字串測得到「有人寫了這一行」，
測不到「這一行真的會讓 CI 紅」。

這是本檔開頭那個病的第四個實例，只是代理指標換成了原始碼文字：
**用「碼裡有沒有這句話」代理「跑起來會不會叫」**。正常路徑上兩者重合，
所以平常看不出來；分岔的那天，正好就是開關該叫而沒叫的那天。

規則：**每個 `--alert-*` 旗標都要有一對走真子行程的測試**，一條踩線的回 1、
一條乾淨的回 0，而且都要真的 `subprocess.run([sys.executable, "pulse-monitor.py", …])`
去讀 `returncode`。不可以在同一個行程裡呼叫 `main()` 取回傳值就算數——
那樣量到的是 `main()` 的 return，不是 CI 會看到的 exit code，
`sys.exit(main())` 那一行被改掉照樣全綠。

兩個方向都要釘，理由跟覆蓋率那一節一樣：只釘「該叫的會叫」，
把 `rc` 寫死成 1 也會全過，而一個天天紅的 CI 跟一個永遠綠的 CI 一樣沒有資訊。

一併要釘的邊界：

- **旗標沒開就不准叫。** 同一個壞掉的 vault，不帶旗標跑要回 0。
- **輸出模式不准吞掉 exit code。** `--json` 與 `--write-health` 各跑一次，
  該紅的還是要紅——這兩條路徑在 `main()` 裡都有自己的 return 點可以寫歪。
- **門檻的方向。** 卡 1 天、門檻 5 天要回 0；卡 5 天、門檻 2 天要回 1。
  只釘其中一邊的話，把 `>=` 改成 `<=` 只會有一半的測試紅。

## 推得上去的那一邊，監看推不上去的那一邊

2026-08-05 實測：半夜潤稿那條 Cowork 鏈**把活做完了、commit 也建了，但 push 被沙箱的
git proxy 擋掉**（403：`... is not in this session's authorized repository set`）。
容器是拋棄式的，所以那一晚的成果等於沒了。

而**現有的三個警報一條都不會叫**——判準各自對得上別的故障：

| 警報 | 判準 | 為什麼漏掉這個故障 |
|---|---|---|
| 死人開關 | 未 enrich 且放了 ≥2 天 | 那晚沒有新事件要潤，未 enrich 是 0 |
| 翻譯鏈 | 「有過然後停了」＝ 0 條中文 | 儲存層有 58 條、覆蓋 31/35，不是 0 |
| health 新鮮度 | `generated_day` 停住 | 那一頁是 Actions 寫的，而 Actions 好好的 |

**兩條鏈的失效模式不一樣，而警報只長在其中一條上。** Actions 那條跑在 GitHub 自己的
機器上、用 `${{ github.token }}`，不經過沙箱 proxy；Cowork 那條跑在沙箱裡，
最後一步要往外推。**推不上去的那一邊沒有辦法通報自己推不上去**——它的通報也要推。

所以判準只能長在**推得上去的那一邊**：Actions 每晚都跑、也推得上去，讓它去量
「潤稿鏈最後一次成功推回是哪一天」。

### 量什麼：commit 本身，不要代理欄位

判準是 `main` 上最近一個 `nightly: enrich` commit 的日期。

**刻意不用 `_config/narratives.yaml` 的 `updated`。** 它看起來是個現成的心跳，
實測不是：08-01、08-02 兩晚都有 `nightly: enrich` commit，但那個檔沒被動到
（那兩晚沒有主線要重寫），所以 `updated` 從 07-31 直接跳到 08-03——**一個合法的
三天空窗**。拿它當門檻，要嘛設得太鬆（≥4 天）而失去意義，要嘛天天誤報。
`docs/design/2026-07-27-published-is-a-proxy.md` 講的就是這個形狀：
**用一個因為別的理由而變動的欄位，去代表另一件事**。

commit 沒有這個問題：實測 2026-07-25 ~ 08-04 連續 11 天，每天至少一個，零空窗。
它量的就是「有沒有推回來」本身，不是它的副作用。

### 淺 checkout 要說「量不到」，不能回一個大數字

`actions/checkout@v4` 預設 `fetch-depth: 1`——一個淺 clone 裡 `git log --grep` 找不到
任何 enrich commit，而「找不到」跟「很久沒有」在數字上長得一樣。那會變成一個
**每天都叫的假警報**，而天天叫的警報跟不會叫的一樣沒有資訊。

所以實作先問 `git rev-parse --is-shallow-repository`：淺的就回「量不到」、印出來、
**不觸警**（紅線 8）。`data-refresh.yml` 的 checkout 因此要顯式設 `fetch-depth: 0`；
哪天有人拿掉，這一格會變成「量不到」而不是變成一顆假紅燈。

### 門檻

`_config/gate.yaml` 的 `monitor.enrich_stale_after_days`，起手 2——跟
`stale_after_days` 同一個數字，理由也一樣：日更的鏈，隔一天是誤點，隔兩天是壞了。

### 負數的 lag：規則在下面那一節，第二個消費者沒拿到

下面〈三條規則〉的第 3 條已經寫得很清楚：`lag < 0` 一律紅。那條規則是為
`stale_after_days` 寫的，而 `enrich_chain_line` 是後來新寫的**第二個消費者**，
它沒有一起拿到——`lag >= 門檻` 對負數同樣是沉默的，`-1 >= 2` 為假就綠燈，
畫面上還照樣印一句「最後一次推回 2026-08-06（-1 天前）」，讀起來像新鮮得不得了。
時間往前走只會讓它更綠，這個洞不會自癒。

同一個形狀這個 repo 已經量到第六次：**規矩寫在一個地方，新接上來的消費者
沒有一起接到，兩邊在規則沒動過的日子裡給一模一樣的答案。**

規則：`enrich_chain_line` 的 `lag < 0` **一律紅**，訊息要跟「太久沒推回」分開寫。
成因不同——一個是那條鏈斷了，一個是這份工作區裡有一顆日期在未來的 enrich
commit。而後者最常見的來源不是時鐘壞掉，是下一節那件事。

**這一格不寫「量不到」。** 這份文件裡「量不到」是保留給不觸警的那幾種
（淺 checkout、非 git 工作區）；負數 lag 要叫，用同一個詞會讓讀的人以為它不叫。

### 讀本地的那一邊，分不出「commit 了」與「推上去了」

判準讀的是 `git log`，而 `git log` 對「這顆 commit 有沒有推上去」一無所知。

在 Actions 那一邊這不成問題：它的工作區是從 `main` checkout 出來的，看到的每一顆
都已經在遠端。**在潤稿那一邊完全相反**——它跑到一半就自己建了一顆 `nightly: enrich`
commit，然後那顆 push 失敗、容器被回收。如果那一邊也開這支警報，它會讀到自己剛建的
那顆，回報「今天剛推回來」，燈是綠的。

實測（2026-08-07，模擬容器）：本地 commit 了 `nightly: enrich + narrative 2026-08-06`、
沒推，當天警報回「潤稿鏈：最後一次推回 2026-08-07（-1 天前）」，**不叫、綠燈**。
它把自己沒推成功的那一顆，讀成推成功了。

所以這支旗標**只准掛在推得上去的那一邊**：`.github/workflows/data-refresh.yml` 開，
`scripts/enrich-runbook.md` 的步驟 17 不准開——那一步是 `pulse-monitor.py --top 5`，
只讀不判。

**這條禁令不會因為寫在這裡就成立。** 這個 repo 已經證明過很多次，只活在文件裡的
規矩會在有人「順手補齊」的那天消失。所以 selftest 直接去量那份 runbook：
潤稿 runbook 裡不准出現帶警報旗標的 `pulse-monitor` 呼叫。散文可以解釋為什麼不准，
命令列不行。

> 更根本的修法是讓判準去問「這顆 commit 在不在遠端分支上」，而不是問 `git log`。
> 沒有走那條，是因為兩邊環境到底有沒有 `origin/main` 這個遠端追蹤 ref，我還沒實測過
> ——`actions/checkout` 的 fetch 行為要驗過才能寫進判準。**驗之前不假設**，
> 先把成本低、量得到的那一半接上。這一條留著。

## 鏈外的那一個（2026-08-11）

前面每一條警報都有一個共同的前提：**它自己要被執行到。**

2026-08-09 那次事故證明那個前提不成立。`main` 從 08-05 到 08-09 沒有進過任何
資料，而四個警報全綠——判準都對，但它們全部長在 `data-refresh.yml` 最後兩個
step 上，而那一班卡在部署環境的閘門、job 一個 step 都沒開始。

08-05 那次是「**推不上去的那一邊沒辦法通報自己推不上去**」，補法是把判準搬到
推得上去的那一邊。這次是「**沒被排上的鏈沒辦法通報自己沒被排上**」，
而這一種補不到同一條鏈上——**只能是另一條排程**。

### 每一個「分開」都是判準的一部分

`.github/workflows/watchdog.yml` 與 `scripts/pulse-watchdog.py`：

| 分開什麼 | 為什麼 |
|---|---|
| 另一支 workflow | 同一支裡加 step 完全沒用——job 沒開始，step 也不會開始 |
| 另一個 concurrency group | `nightly` 那一組卡住時，它不能跟著排隊 |
| 另一個時間（04:00Z ＝ 台北 12:00） | 看的是前一晚 16:00Z 那班的結果，隔 12 小時 |
| 不掛 `environment` | 部署閘門正是 08-09 卡住 `data-refresh` 的東西 |
| 不 import 任何 pipeline 模組 | `pulse-monitor.py` 哪天語法壞掉，它照樣跑得起來 |
| 只讀 git log 與檔案系統 | `_probe/` 是被監看那條鏈自己寫的——拿它判斷它有沒有跑，等於問一個昏迷的人他醒著沒有 |

唯一的例外是 `lib.clock`：取日期的唯一入口是紅線，抄第二份日期邏輯是這個 repo
量過很多次的病（`references/timezones.md`）。

### 它量四件事，分開報

| 量什麼 | 從哪裡讀 | 壞掉的樣子 |
|---|---|---|
| 抓取有沒有跑 | `main` 上最後一個 `probe ` commit | 排程沒被排上 / CI 掛了 |
| 有沒有抓到東西 | `_corpus/` 最新的目錄 | 鏈在跑但來源全空 |
| 看板有沒有重生成 | `_dashboards/health.md` 的 `generated_day` | vault 頁那幾步掛了 |
| 潤稿有沒有推回 | `main` 上最後一個 `nightly: enrich` commit | 沙箱授權掉了 |

**四格分開判、分開報。** 擠成一個「健康／不健康」的話，看到紅燈的人得自己去猜是
哪一種，而這四種要做的事完全不同。

### 門檻是另一個 key

`_config/gate.yaml` 的 `watchdog.stale_after_days`，跟 `monitor.stale_after_days`
**刻意分開**。monitor 那個判「幾天沒抓到東西」而且它自己就跑在被監看的鏈裡；
這一個判「那條鏈到底有沒有被排上」。共用一個 key 的話，哪天有人為了讓 monitor
安靜而調鬆它，會連鏈外那一支一起調鬆——而那正是唯一還會叫的東西。

### 淺 checkout 一樣回「量不到」

同 `enrich_chain_line` 的規矩：`git log --grep` 在 `fetch-depth: 1` 裡什麼都找不到，
而「找不到」跟「很久沒有」在數字上長得一樣。四格全印「量不到」且不觸警（紅線 8）。

負數 lag 判紅、訊息與「太久沒有」分開——同〈三條規則〉第 3 條。

## 三條規則

### 1. 「有語料的一天」＝目錄裡至少有一行非空白的 jsonl

`corpus_days()` 以前只數目錄名。但目錄是 `pulse-probe.py` **打算寫東西之前**
就建好的——建目錄跟寫進東西之間有一段路，任何一步失敗都會留下一個空目錄，
而那個空目錄接著會被當成「這天有語料」。

判準統一成 `observed()` 早就在用的那一把尺：**至少一行 `strip()` 後非空的
`.jsonl`**。同一個問題不該有兩把尺。

`run_days()` 同理，改成要求 `<day>/report.md` 真的存在——那正是這個模組開頭
就寫著的定義（「每班都寫，不管有沒有抓到東西」）。目錄存在但報告沒寫出來的班，
不算跑過。

### 2. 不是真日期的目錄名，不是一天

以前的判準是「長度 10 且第 5 個字元是 `-`」。`2026-13-99` 通得過，
`2026-W30-1` 也通得過。改用 `datetime.strptime(name, "%Y-%m-%d")` 嚴格驗。

驗不過的目錄名就當它不存在——**但這不代表它不重要**。它代表 `_corpus/` 裡有
一個沒人認得的東西，那是另一種 bug，該由 selftest 的目錄檢查去抓，不該由
新鮮度計算去猜。

### 3. lag 是負數＝時鐘壞了，判紅不判綠

`stale = item_lag >= stale_after_days` 這一行對負數是沉默的：
一個 `_corpus/2026-07-30/`（今天 07-26）算出 `lag = -4`，`-4 >= 2` 為假，
所以綠燈。而且時間往前走只會讓它更綠——這個洞**不會自癒**。

規則：**`lag < 0` 一律紅**，訊息要跟「太久沒抓到」分開寫，因為成因完全不同——
一個是鏈瞎了，一個是有人（或某支腳本）寫了一個未來日期的目錄，
資料本身可能是好的，壞的是日期。分不清這兩件事，人會往錯的方向找。

## 時區：`_as_date()` 拿掉偏移量之前先歸零到 UTC

`datetime.fromisoformat("2026-07-22T02:00:00+08:00").date()` 回傳 `2026-07-22`，
但那個瞬間的 UTC 日期是 `2026-07-21`。而 `today` 是
`datetime.now(timezone.utc).date()`。兩個不同時區的日期相減，答案可以差一天。

一天的誤差在 `stale_after_days: 2` 這種門檻上就是「叫」與「不叫」的差別。

規則：`_as_date()` 遇到帶時區的值，**先 `astimezone(utc)` 再取 `.date()`**。
不帶時區的值視為 UTC（這是既有語意，不改）。

實測目前 vault 的 `happened_at` 時區分佈是 48 × `+00:00`、3 × `-04:00`、
0 × 其他，所以這次修正的實際影響面是 3 則。**寫在這裡是因為它會再犯**——
只要哪天開始收本地時區的來源，影響面就會長回來。

> **2026-07-27 追記：那天到了，而且上面這段只修了一半。**
>
> `src-qwen-blog` 開始供稿，30 筆全是 `+0800`。更要緊的是：上面那條規則當時只改
> 了 `pulse-monitor._as_date()` 一個函式，沒有變成全鏈的規矩——而 `pulse-cluster.py`
> （**產生 `evt-<日期>-<hash>` id 的那支**）一直在做裸的 `.date()`。它到那天為止
> 都是綠的，純粹因為那 20 筆 Qwen 貼文沒有一則夠格變成 Event。
>
> 現在的規矩不再是「記得要 `astimezone`」，而是**只有 `lib/clock.py` 能取日期，
> 其他地方寫 `date.today()` 或裸 `.date()` 會被 selftest 擋下來**。
> 完整規格（含顯示層換算成台北）搬到 `references/timezones.md`。

## 量不到的年紀，不等於年紀是 0（紅線 8）

`--alert-unenriched-days` 的實作是：

```python
stale_unenriched = [e["age_days"] for e in review
                    if e["unenriched"] and e["age_days"] is not None]
oldest = max(stale_unenriched) if stale_unenriched else 0
```

`age_days` 來自 `ingested_at`。缺 `ingested_at` 的 Event 被 `is not None`
濾掉，全部濾光時 `max()` 沒東西可算，**回退成 0**——而 0 永遠低於任何門檻。

於是：庫裡有 3 則未潤稿、全都缺 `ingested_at` → 開關 rc=0，安靜。
這正是紅線 8 說的那件事的反面：**量不到被寫成了「沒事」**。

規則：**未潤稿又量不到年紀的 Event，自己就是一則警報。**
`scan()` 多回一個 `unenriched_undated`；只要 `--alert-unenriched-days` 有開，
這個數字大於 0 就叫，跟門檻天數無關（因為根本沒有天數可以比）。
訊息要明講「量不到」，不要假裝它放了 0 天。

`undated_review`（含已潤稿的）維持原樣只印不叫——那些是 2026-07-26 之前建的
歷史資料，補不回來也不影響鏈的運作，天天叫等於沒有燈。

## 沉默要拿它自己的時鐘量

`--alert-coverage` 判「這家必盯實體沉默太久」時，以前的護欄是這一句：

```python
and history_days >= w["max_silent_days"]
```

護欄的用意是對的：語料只有 3 天的時候，對著 14 天的門檻喊「這家 14 天沒出現」，
是在講一句自己都知道不成立的話，而新 vault 第一天就滿螢幕紅字，只會教人把警報關掉。
錯的是它拿來當尺的東西——`history_days` 是**整個語料庫**的歷史長度，
`max_silent_days` 是**單一觀察對象**允許沉默的天數。**兩個不同層級的數字被放進同一個
不等式**，於是同一個護欄在兩個方向上都會錯，而且錯法相反：

| 那條 watch entry 的處境 | 語料庫 3 天（現在） | 語料庫 300 天（將來） |
|---|---|---|
| 被看了半年，來源上個月死了 | **不叫**（`3 >= 14` 為假） | 叫 ✓ |
| 昨天才加來源，只被看了 1 天 | 不叫 ✓ | **叫**（`300 >= 14` 為真） |

左上是「該叫的不叫」，右下是「不該叫的叫」。兩格都是同一個錯誤造成的，
所以不能靠調門檻補——調高調低只會換一格錯。

**規則：護欄改成 `observed_days >= max_silent_days`**，`observed_days` 是這條 watch
entry **自己**被觀察了幾天，起算點取它底下那些來源之中**最早**開始被觀察的那一天
（只要有一條在看，這家就算被看著了）。

護欄壓下來的那一格要印出來，不能靜靜吞掉：`silent_pending_clock` 標的是
「**有來源、也真的沉默過久了，唯一沒判 silent 的理由是它自己的觀察期還沒到門檻**」，
報表上跟著印 `觀察期 n/md`。不印的話，人看到的只是一個沒有紅字的「從未」，
分不出是「還沒到時候」還是「判斷漏了」——而後者正是這一層要防的病。
判準只寫在 `coverage()` 一處，兩個 renderer 都讀它，不各自重推一次。

### 起算點怎麼量：兩個檔案都問，取最早

- `_probe/state.json` 的 `first_fetch_at` —— 這條來源第一次真的抓到東西。
- `_probe/source-runs.jsonl` 裡這條來源第一個**真的嘗試過**的班次日期。
  三種 skip（`robots_disallow` / `robots_unknown` / `skipped_lifecycle`）不算嘗試：
  被 robots 擋住、或還在 dormant 的那些日子，我們並沒有在看那條線。

**為什麼兩個都要問，不是二選一：**

- 只信 `first_fetch_at`，**從沒成功抓過的來源就永遠沒有起算點**，`observed_days`
  永遠是 0，那家實體永遠不會被判沉默——一條壞掉的來源把它自己造成的沉默一起靜音了。
  這正是本檔開頭那種病的形狀。
- 只信 `source-runs.jsonl`，會把歷史砍掉：那個檔 2026-07-26 才開始寫，在它之前
  跑過的班一筆都沒有記錄。

取**最早**的那一個，是因為「有沒有在看」問的是嘗試不是成功。一條試了 9 天才第一次
抓到東西的來源，那 9 天的沉默是真的沉默，不該從時鐘上扣掉。

### 未來日期的起算點不算證據

`first_fetch_at` 或班次日期落在 `today` 之後，代表寫它的那台機器時鐘壞了，
不代表我們從未來開始觀察。這種值直接不採計；全部不採計就等於沒有起算點，
`observed_days` 是 0，這家不判沉默。

**這是刻意把判斷讓給上面那條規則**：同一個壞掉的時鐘也會寫出未來日期的
`_corpus/<day>/`，而本檔第 3 條（`lag < 0` 一律紅）會抓到它，訊息也正確地指向
「日期壞了」而不是「來源死了」。在覆蓋率這一層再判一次，只會多一個指錯方向的警報。

## 零產出不是沉默

> 實作：`pulse-probe.py` 的 `adapt_sitemap()`（填 `diag`）、`zero_yield_reason()`
> （判 code）、`zero_yield_section()`（渲染）。不一致時以本節為準（紅線 9）。

`_probe/<日>/report.md` 的來源狀態表，對一條抓成功但沒東西的來源只印兩個數字：

```
| src-mistral-news | official | 200 | 0 | 0 | | True | |
```

**「站上今天沒有新東西」跟「我們解析不出來」印出來一模一樣。** 這是同一隻病換到
報告上：`items=0` 是一個比事實寬鬆的代理，在站方真的沒更新的日子裡跟事實重合，
正好在我們的 adapter 接不上的那天分岔——而那天，正是唯一需要它準的一天。

代價量得到：`src-mistral-news` 連續 7 班 `200 / 0 筆`，7 班之後沒有任何人能說出
它屬於哪一種，因為報告上沒有留下任何中途數字。

### 規則一：中途數字要留下來，不能只留回傳值

`adapt_*()` 回的是一個 list，空清單只有一種形狀，但走到空清單有四條不同的路。
所以 adapter 多收一個 `diag: dict`，把**每一步之後各剩幾條**寫進去：
index 有幾張子 sitemap、hints 命中幾張、展開幾張、抓成功幾張、過濾前幾條 URL、
過濾後幾條。這些數字全部是計數，不是判斷。

### 規則二：判斷要有 code，不能只有散文

`zero_yield_reason(diag)` 把那些計數翻成一個 code 加一句人話。分界線只有一條：
**這 0 筆是站方那邊沒有東西，還是我們這邊接不上。**

| code | 是誰那邊 | 什麼情況 |
|---|---|---|
| `source_empty` | 站方 | 入口是通的，裡面就是沒有 URL |
| `hints_matched_nothing` | 我們 | index 有子 sitemap，但沒有一張對得上 `sitemap_hints` |
| `sub_sitemap_unreachable` | 中間那一跳 | 子 sitemap 選到了，抓不下來 |
| `prefix_filtered_all` | 我們 | URL 拿到了，`url_prefix` 一條都不放行 |
| `upstream_empty_body` | 還不知道 | 自己抓的 adapter：回 200 但 body 是空的 |
| `no_diagnosis` | 還不知道 | 這個 adapter 還沒有零產出診斷 |

### 自己抓的 adapter 要自己回報 status

`SELF_FETCH` 那一組（目前只有 `github-releases`）的 `endpoint` 不是 URL，
由 adapter 自己組 URL 並抓。`run_source()` 因此**沒有送出任何請求**——它以前
是這樣寫的：

```python
items = adapter(src, "", stat["diag"])
stat["status"] = 200          # ← 舊版
```

**用「adapter 沒有丟例外」代理「這一班真的成功」。** 兩者在順利的日子裡重合，
正好在 GitHub API 額度用完的那天分岔——而那天報告會說 `200 / 0 筆`，看起來
跟「這個 repo 這陣子沒有發新 release」一模一樣。API 額度會用完不是稀有情況，
同一支 workflow 裡的 `pulse-github.py` 甚至已經有一句
「本次未取得任何 repo（API 失敗或額度）」的 warn。

規則：**自己抓的 adapter 要把真實 status 寫進 `diag["self_fetch_status"]`，
`run_source()` 讀它，不寫死 200。** 非 200 的班次於是根本不會進〈零產出診斷〉
——它是一次抓取失敗，由 `error` 欄回答，而 401/403/429 在健康分那邊本來就
不記分（量不到不等於壞掉）。

只印散文不行的理由：報告上的字是給人看的，但「這條該不該去修」是要拿來做決定的。
散文要下一個人自己重讀一遍再判一次，而重判會因人而異——那就又是一個代理。

### 說得出「你設錯了」，也要說得出「那是什麼」

`hints_matched_nothing` 這一格 2026-07-27 首班就用上了：`src-mistral-news`
判成「index 有 1 張子 sitemap，hints 一張都沒命中——是我們的設定對不上」。
**判定完全正確，而下一步還是查不下去**，因為那 1 張的網址沒有印出來。

一個說得出「你設錯了」卻說不出「那是什麼」的診斷，只把人從「不知道哪裡錯」
推到「知道哪裡錯但不知道要改成什麼」。所以 `diag["index_sample"]` 記下 index
的前 5 個 `<loc>`，`hints_matched_nothing` 的說明把它們印出來。

上限 5 是刻意的：整份 index 可能有幾百張，倒進報告會把這一區變成沒有人讀的
一面牆——而一份沒有人讀的診斷跟沒有診斷是同一件事。

`no_diagnosis` 是刻意留的（紅線 8）。目前只有 sitemap adapter 填 `diag`，rss /
atom / json-api / github-releases 都還沒有。**誠實印出「分不出來」，好過印一句
看起來像判斷的空話。**

### 規則三：這一區空的時候要印「本輪沒有」

一個只在有東西時才出現的區塊，看不見的時候有兩種意思：本輪沒有零產出，或這段碼
壞了。這兩件事必須分得出來，所以零筆的時候印一句「本輪沒有 status 200 而 0 筆的
來源」，不是整段不印。

### 收哪些、不收哪些

只收 `status == 200 且 items == 0`。

- `304` 不收：那是「內容沒變」，本來就講得清楚。
- 非 200 不收：`error` 欄已經說了是哪一種失敗。
- `robots_disallow` / `robots_unknown` / `skipped_lifecycle` 不收：這三種**根本
  沒有抓**，混進來會讓「零產出」這個詞同時指兩件事（見 `source-lifecycle.md`
  關於這三種 skip 不算嘗試的那一段）。

### 這一節不保證什麼

- **不保證有人會因此被叫。** 目前 code 只渲染進 report.md 給人看，沒有寫進
  `_probe/source-runs.jsonl`，也沒有任何警報吃它。`prefix_filtered_all` 連續
  三十班，CI 一樣是綠的。要接的話得先想清楚門檻與消費者，否則就是再造一個
  「算得很認真、沒人讀」的欄位。這個缺口記在 `BACKLOG.md` 的 `零產出來源`。
- **不保證 `source_empty` 就是站方的錯。** 它只說「這個入口回來的東西裡沒有
  URL」。入口本身選錯（`endpoint` 指到一張不含新聞的 sitemap）也會長成這樣，
  而那是我們的設定問題。要分得更細，得比對站方 robots.txt 宣告的 Sitemap 清單，
  那超出這一節。

## 修好了但沒有人收：origin 上的分支

排程 runbook 給夜班的規矩是「**碼的問題自己開分支，不要直推 main**」，然後
「把分支名寫進摘要讓人去開 PR」。前半段夜班做得很好，後半段沒有人在做。

2026-08-21 量的：

```
fix/selftest-crash-missing-ruamel          08-13   selftest 缺 ruamel 從 KeyError 改成紅
fix/gitignore-digest-scratch-file          08-14   .gitignore + runbook + selftest
fix/gitignore-digest-json-2026-08-15       08-15   .gitignore
fix/nightly-runbook-deps-2026-08-17        08-17   .gitignore + runbook + selftest
fix/gitignore-digest-input                 08-20   .gitignore
fix/nightly-enrich-env-and-gitignore-gaps  08-21   三件一起
```

**同一組問題，九天內開了六支分支，前五支一支都沒被收。** 所以夜班每隔一兩晚
重新發現一次、重新修一次、重新寫一次 commit message——那是六個晚上的工，
產出躺在 origin 上沒有人讀。

這跟這個 repo 修過的其他病是同一個形狀：**產出沒有消費端**。分支名寫進摘要，
而摘要是一份沒有人固定去讀的自述——`references/digest-observability.md` 為
digest 那一步講過同一句話。

### 判準：不是 `main` 的祖先

```
git branch -r                          列出所有遠端分支
git merge-base --is-ancestor <b> main  它的 tip 在 main 裡嗎
```

不在的就是「有東西沒收」。實測 2026-08-21：42 支遠端分支裡 36 支已在 main
（含 9 支 `claude/*` 的夜間資料分支——那些是平台命名的殘留 ref，資料早就進去了），
6 支不在，全部是夜班開的 `fix/*`。

### 這條判準依賴一件事，而那件事可能會變

**它假設 merge 用的是 merge commit，不是 squash。** squash-merge 會產生一顆
新 commit，原分支的 tip 永遠不會變成 `main` 的祖先——那一天起，**每一支歷史
分支都會看起來沒被收**，這個警報會一次報 40 支，然後兩週內被關掉。

所以判準要自己防這件事：**不在 main 的分支超過總數一半時，不報「有 N 支沒收」，
報「這個判準可能失效了」。** 一個判準能說出自己什麼時候不該被相信，比它多抓幾支
分支重要。

### 量不到不是 0 支

`git branch -r` 只看得到 `origin/main` 的時候（單分支 clone、或沒有 fetch 全部
refspec），這條規則會算出「0 支沒收」——而那是這條規則最容易變成永遠綠燈的方式。

所以 reason 有四種，跟 `last_enrich_commit()` 同一個形狀：

```
ok           量到了
no-git       這裡不是 git 工作區
no-remotes   只看得到 main（或一支都沒有）→ **量不到**，不是 0
suspect      不在 main 的超過一半 → 判準可能失效（見上）
```

夜班那一邊的 clone 多半只有 main，所以它會回 `no-remotes`——那正確：
**這條判準要長在 Actions 那一邊**（`fetch-depth: 0`，看得到全部分支），
跟 `enrich_chain_line` 同一個理由。

### `origin/HEAD` 不是一支分支，但它的 short name 長得像

（2026-09-15 補）上面那條 `no-remotes` 從接上的那天起，在任何一個真實 clone 裡
都沒有觸發過。

`git branch -r --format=%(refname:short)` 對 `refs/remotes/origin/HEAD` 輸出的是
**`origin`**，不是 `origin/HEAD`。實作原本用 `b.endswith("/HEAD")` 濾掉它，濾不到，
於是 `branches` 永遠至少有一個元素，`if not branches` 那條路走不到，單分支 clone
一律算出 `ok / 0 支`。

這正是上一段要防的那件事本身，而守衛自己壞了。**「量不到」跟「0 支」在畫面上
長得一模一樣**（紅線 8），差別只在一個會讓人去補 `fetch-depth: 0`，另一個讓人
以為分支都收乾淨了。附帶的第二個後果：`suspect` 的分母多算一個，那條自保的門檻
跟著被稀釋。

過濾要按 **remote 名**判，不是按 ref 名的尾巴。`origin/HEAD` 的 short name 就是
remote 自己的名字，而 remote 名可以從 `main_ref` 的第一段拿到。

**測試的 fixture 也要有 `origin/HEAD`。** selftest 端到端那一格 clone 的是一個
空的 bare repo，而 clone 一個空 repo 不會建立 `origin/HEAD` symref。所以 fixture
裡從來沒有這個 ref，這個 bug 在測試那一邊根本不存在。fixture 要在 push 完 main
之後補一行 `git remote set-head origin main`，讓它跟真實 clone 一樣。

同一種病這份文件記過好幾次：**驗證環境比現場乾淨，於是測試量不到現場會發生的事。**

### 門檻與它擋不住什麼

`monitor.unmerged_branch_days`，預設 3。一支昨天剛開的分支不該叫；
一支開了三天沒人看的，夜班已經有機會重新發現同一件事了。

**擋不住「分支被收了但改壞了」**——這一層只問「有沒有人收」，不問收得對不對。
那是 code review 的事，沒有規則抓得到。

## 這一層不保證什麼

- **不保證語料是對的。** 一行 `{"title": ""}` 也算一行。這一層只回答
  「那天到底有沒有東西進來」，內容品質歸 quality-score 那一層。
- **不保證未來日期的目錄會被修掉。** 判紅只是讓人看見它；刪不刪是人的決定，
  因為那個目錄裡可能有真的語料，只是日期寫錯。
- **`observed_days` 量的是「來源開始跑」，不是「來源開始涵蓋這家公司」。**
  一條 2026-01-01 就在跑的科技媒體，今天才第一次寫到某家新創——時鐘會說
  「我們看了半年」，但實際上這半年裡那家公司從來不在那條線的守備範圍內。
  要更準，得記下「這條 watch entry 是哪天被加進 `sources.yaml` 的」，
  而那個日期現在沒有任何地方存著（git log 不算：設定檔重排一次就洗掉了）。
  這次先修到「用自己來源的時鐘」這一層，剩下的差距寫在這裡，免得下次又推導一遍。

## 最後一次遮不住中間的洞：缺日

潤稿鏈、每日精選、health 新鮮度這三條判準量的都是「**最後一次**是哪一天」。
那個形狀抓得到「鏈斷了以後一直沒回來」，抓不到「中間掉了一晚，隔天又好了」。

2026-09-11 實測：那一晚夜班把活做完了，`nightly: enrich + narrative 2026-09-11`
這顆 commit 也建了，但它只落在 Cowork session 自己的分支上，沒有落到 `main`。
那顆 commit 的 parent 就是當時的 `main` tip，fast-forward 就進得去，所以不是被
non-fast-forward 拒絕。隔天 9/12 的夜班從 `main` 起頭、正常推回，於是：

| 判準 | 9/12 當天看到的 | 叫了嗎 |
|---|---|---|
| 潤稿鏈 | 最後一次推回 09-12，lag 0 | 沒有 |
| 每日精選 | 最後一篇 09-12，lag 0 | 沒有 |
| 沒收的修碼分支 | 門檻 3 天，09-14 才到 | 三天後才叫，而且字面說「修碼分支」，指向另一件事 |

那一晚的產出躺在 origin 的一支分支上三天沒有人知道。Event 那一批被 9/12 的夜班
重做掉了，沒有損失；每日精選那一篇沒有，因為**它只寫當天，不回頭補**。所以 9/11 這一天在站上永遠是空的，而那天的素材（四則 Anthropic 公告）在
9/10 與 9/12 的 digest 裡都沒有出現過。掉的不是一天的版面，是一組主線。

### 判準：窗內哪幾天沒有

量的是**日期集合的缺口**，不是集合裡最後一個元素。兩個消費者共用同一支純函式，
因為這份文件已經記過六次「規矩寫在一個地方，新接上來的消費者沒有一起接到」。

```
missing_days(days, today, window_days)   → 窗內缺的日期，由舊到新
```

窗口不含今天：今晚的夜班還沒跑，今天缺是正常的。

### 窗口起手 1 天，刻意不設更長

**缺口不會自癒。** 9/11 這一天永遠不會再有 enrich commit，所以窗口設 7 天的話，
這條警報會連紅七天，然後在第三天被人關掉。這個 repo 對這件事有前科：
`data-refresh.yml` 自己的註解寫過「標了 pending 的已知缺口不觸警，否則 CI 天天紅，
人只會學會忽略 CI，連帶忽略真正的回歸」。

代價要寫清楚：**窗口 1 天等於只叫一次。** 那天的 CI 紅是唯一的痕跡，沒有人看就
過去了。要它再叫，得把那一天補進來，或把窗口調大，兩件事都是人的決定，不是判準
自己該做的。門檻在 `_config/gate.yaml` 的 `monitor.chain_gap_window_days`。

### 「沒有夜班 commit」不等於「夜班沒跑」

夜班的 commit message 不是固定的。2026-09-08 那一晚的成果確實進了 `main`
（那天的每日精選在 `Digests/` 裡），但 commit message 是
`chore: nightly refresh 2026-09-08`，`--grep=^nightly: enrich` 抓不到它。
只看 message 的話，9/08 會被算成一個缺口，而那是假警報。

所以 enrich 這一條的缺口判準取兩個條件的**聯集**：message 前綴命中，或 commit
的作者是夜班那個帳號（`ai-pulse-enrich`；資料鏈的 bot 是 `ai-pulse-bot`，兩個
帳號分得開）。作者是 commit 本身的屬性，不是〈量什麼：commit 本身，不要代理欄位〉
那節說的代理欄位。

### 這支旗標一樣只准掛在推得上去的那一邊

`night_shift_commit_days()` 讀的是 `git log`，跟 `last_enrich_commit()` 同一個
限制：它分不出「commit 了」與「推上去了」。夜班那一邊跑它，會讀到自己剛建、
還沒推出去的那顆，算出「昨天有」、綠燈，而那正好是它要抓的那個故障。

所以 `--alert-chain-gap` 跟 `--alert-enrich-stale` 一樣，只准長在
`.github/workflows/data-refresh.yml`。selftest 那條「潤稿 runbook 的步驟 17
不准帶警報旗標」判的是任何一行同時含 `pulse-monitor` 與 `--alert` 的命令，
所以這支旗標一接上就自動被它守著，不必另寫一條。

### 這一節不保證什麼

- **不保證那一晚真的潤了稿。** 判準問的是「昨天夜班有沒有往 `main` 推東西」。
  夜班推了補跑的 probe、而潤稿那一段沒推上去的話，這一格是綠的。要抓得更準，
  得再問那顆 commit 有沒有動到 `Events/` 或 `Digests/`，那一層還沒做。
- **不保證缺的那一天會被補回來。** 這一層只負責讓人在隔天看見它。補不補、怎麼補，
  是人的決定：`Digests/` 是資料產物，手改它會被下一班的規則覆蓋（見 `CONTRIBUTING.md`
  〈兩條路，別走錯〉）。2026-09-15 對 9/11 的決定就是不補。
- **量不到的時候不算缺口。** 淺 checkout 與非 git 工作區回「量不到」、不觸警，
  跟 `last_enrich_commit()` 同一個形狀。空的 `Digests/` 目錄交給既有的
  「從來沒有產出過」那條，不在這一層重複判一次。

## 來源已死但每班照樣有貨：`stale_source`

> 實作：`pulse-monitor.py` 的 `coverage()`（判準）、`render_health()` 與 CLI 報告（渲染）、
> `--alert-stale-source`（exit code）。門檻在 `_config/gate.yaml` 的 `monitor.stale_source_days`。
> 不一致時以本節為準（紅線 9）。

`silent_sources` 的判準是 `items == 0`：**「這班抓回幾筆」被拿來代表「這條來源還在出東西嗎」。**
一條死掉的來源每班照樣把舊貨吐回來，`items` 永遠不是 0，那一格永遠綠。2026-07-27 量到
`src-meta-research` 最新一筆停在 2023-05-17 而儀表顯示正常；2026-09-13 複量，它落後 1215 天，
`src-kol-karpathy` 136 天、`src-media-venturebeat` 17 天，三條都在「可跑來源」裡、都不在
「零產出」裡。這是本檔開頭那隻病的又一個實例：代理指標在來源活著的日子跟事實重合，
正好在它死掉那天分岔。

### 判準：最新一筆 `published` 距今幾天，門檻按 `frequency` 分

每條會跑的來源，在 `coverage()` 的窗口內取 `max(published)`，跟今天相減，
門檻查 `gate.yaml` 的 `monitor.stale_source_days.<frequency>`。

`published` 的解析走 `lib.quality.parse_dt`（吃 RFC 2822 與 ISO 8601），再 `clock.utc_date()`。
**不用 `pulse-monitor._as_date()`**——它只吃 ISO，而 RSS 來源寫的是
`Mon, 14 Sep 2026 00:00:00 GMT`，用它量會把二十幾條來源全部量成「沒有日期」。
2026-09-13 第一次量就是這樣量錯的，門檻差點依一張全是 None 的表訂出來。

### 六種狀態，每一種都有自己的名字

| `stale_reason` | 什麼情況 | 進 `stale_sources`？ | 觸 `--alert-stale-source`？ |
|---|---|---|---|
| `ok` | 落後 < 門檻 | 否 | 否 |
| `stale` | 落後 ≥ 門檻 | **是** | **是** |
| `no_items` | 本窗口 0 筆。這條歸 `silent_sources`，這裡不重判 | 否 | 否 |
| `no_published` | 有筆，但沒有一筆解析得出日期 | 否 | 否 |
| `no_threshold` | `frequency` 缺、不在表裡、或整個 key 不存在 | 否 | 否 |
| `future_published` | 落後是負數：來源自己標了未來日期（`src-openai-blog` 實測 −1） | 否 | 否 |

判準的優先序照表的順序：`no_items` → `no_published` → `no_threshold` → `future_published` → `stale`／`ok`。
唯一會重疊的是「日期在未來、而門檻又缺」，判 `no_threshold`：先說量不到門檻，再談日期。

`stale` 跟 `silent`（有來源、0 筆）**必須是兩個名字**。合成一個「這條來源怪怪的」，
下一個人得再查一次才知道要修抓取端還是換端點。

後面四種不是「沒事」，是「量不到」或「不歸這裡」。health.md 與 CLI 各印兩行：一行點名 `stale`
（附最新一筆日期、落後天數、門檻），一行列量不到的條數與名字、三種成因各自標名；零條印「無」，
不是整行不印。`--json` 只有 `stale_sources` 這一個聚合清單，量不到的要逐列讀 `sources[].stale_reason`
——機器讀的那一邊不需要第二份摘要，兩份遲早不同步。哪一種都不得靜靜落成 `ok`（紅線 8）。
**門檻表缺 key 或缺這個 frequency 時不塞預設數字**：一個誰都沒決定過的數字，
跟一個假數字沒有差別。

### 門檻的起手值是量出來的，不是想出來的

2026-09-13 拿 30 天語料量：正常出貨的來源裡最大落後 daily 13（`src-msr-blog`）、
weekly 13（`src-kol-oneusefulthing`）、monthly 4（`src-kol-raschka`）、quarterly 71
（`src-kol-lilianweng`）。起手值 daily 14／weekly 30／monthly 60／quarterly 120，
讓上面三條被點到、其餘全部 `ok`。要調走 PR（CONTRIBUTING：改門檻先改文件）。

### 這一節不保證什麼

- **不保證 CI 會因此變紅。** `--alert-stale-source` 存在且有子行程的 exit code 測試，
  但**沒有接進 `data-refresh.yml`**：讓整條鏈紅燈的條件是人的決定，不該隨一個修 bug 的 PR
  一起上。要接的時候是一行 workflow 的改動。
- **`future_published` 不觸警。** 一條來源要是永遠把最新一筆標成明天，它永遠不會被判 stale。
  目前只有 `src-openai-blog` 這樣，而它同時是真的在出貨。這一格印出來給人看，判斷留給人。
- **量的是 `published`，不是「這條來源涵蓋了什麼」。** 一條天天出貨但全是別的題目的來源，
  這一層看不出來；那是 `coverage_watch` 的事。

## 整條網路斷掉不是 N 條來源同時出事：control probe

> 實作：`pulse-probe.py` 的 `control_probe()`、`main()` 的 `--control-url` / `--skip-control`、
> 離開碼 4。egress 攔截簽名（`is_egress_intercept()`）的單一真相源也在 `pulse-probe.py`，
> `verify-article-metadata.py` 從它取。不一致時以本節為準（紅線 9）。

`verify-policy-sources.py` 與 `verify-article-metadata.py` 都有 control probe：先證明機器
連得出去，連不出去就整份中止、不下任何判決。**生產的 probe 沒有這一關。** 整條網路斷掉
（或跑在有 egress allowlist 的容器裡）時，它會寫出 27 條各自獨立的 `robots_unknown`，
讀起來像 27 個來源同時出事。單條的處理是保守的、沒寫錯；缺的是**「問題在我們這邊」這個
彙總訊號**。2026-07-27 的 C-4 誤讀就是這個缺口長在人身上的版本（`docs/design/2026-07-27-published-is-a-proxy.md` C-4′）。

### 規則

1. **抓任何來源之前先打一個已知連得到的 URL**（預設 `https://github.com/robots.txt`，
   跟 `verify-policy-sources.py` 同一個）。判準是「有沒有走到對方的伺服器」，不是
   「對方喜不喜歡我們」：任何 HTTP 狀態碼（含 403）都算連到了；連線層例外、或回應帶
   egress 攔截簽名才算連不出去。簽名的正本是 `pulse-probe.py` 的 `EGRESS_HEADER`
   （`x-deny-reason` 標頭）與 `EGRESS_BODY_MARKERS`（403 且 body 含 `not in allowlist` 或
   `network egress settings`）；這裡只是複述，加新簽名改那裡。
2. **連不出去就整班中止，離開碼 4。** 不寫 `_corpus/`、不寫 `state.json` / `seen.json`、
   不 append `source-runs.jsonl`、不 commit。heartbeat 狀態 `network_blocked`，
   stderr 一句話指向「問題在我們這邊」。離開碼 4 跟既有的 2（環境不見了）、3（0 個可跑來源）
   一樣是致命的，`data-refresh.yml` 那一步不吞它。
3. **`--dry-run` 與 `--only` 都不跳過 control probe。** 網路斷著的時候，單源除錯得到的
   結果一樣是假的。
4. **`--skip-control` 只給離線測試用，不得出現在 workflow。** selftest 釘住。

### 為什麼中止而不是標記

不中止、只在每條來源上多標一個「可能是我們的問題」，等於把一個彙總事實拆回 27 條散文，
而 monitor 那一邊的 `stale_after_days` 會照樣在隔天叫——那才是對的：一班沒抓到任何東西，
死人開關該叫。control probe 只負責讓那一班**不要留下一份看起來像資料的東西**。

### 這一節不保證什麼

- **不保證 control URL 永遠可用。** GitHub 掛掉的那天這一關會誤判成「我們連不出去」，
  整班中止。代價是那一天不抓；比起寫出 27 條假的 `robots_unknown`，這是便宜的那一邊。
  要換 URL 用 `--control-url`。
- **不保證抓到「部分來源連不到」。** 那是單條來源的事，`robots_verdict` 的原因碼已經分得開。
