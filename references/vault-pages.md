# 機器產生的 vault 頁面：`Sources/` 與 `_dashboards/health.md`

> 這份是**規格**，`scripts/pulse-source-notes.py` 與 `scripts/pulse-monitor.py
> --write-health` 是它的實作。不一致時以本檔為準，並且先改本檔再改碼（紅線 9）。

## 為什麼要有這兩頁

兩個都不是「多做一點視覺化」，兩個都是在補**已經被引用、但根本不存在**的東西。

**`Sources/<id>.md`** —— `pulse-render.py` 從第一天就往每一則 Event 的證據區塊寫

```
- [[Sources/src-nvidia-blog|src-nvidia-blog]] — NVIDIA and Japan Bring ...
```

而 `Sources/` 資料夾裡只有一個 0 bytes 的檔案。也就是在 Obsidian 裡打開任何一則
事件，證據那一行**全部是紅色斷鏈**。情報模型講「Event 是唯一事實節點，
Track / Actor / Source 靠 backlink 自動成關聯圖」——關聯圖的其中一整邊是空的。

**`_dashboards/health.md`** —— 部署規格從第一天就寫著「健康監控：`health.md` 的
`last_success` 過期即紅燈，無人值守最怕靜默死掉」。這個檔案從來沒有存在過，
`gate.yaml` 的 `monitor.stale_after_days` 因此也一直沒有消費者。

這兩件事是同一種病的兩個病灶：**寫好了但沒有人叫它**。紅線 8 是對自己誠實，
處理方式是把東西做出來，不是把那句話從文件裡刪掉。

## 共同規則

**不編造。** 每個欄位不是抄自 `_config/`（人寫的設定），就是數自 `_corpus/` /
`Events/` / `_probe/`（機器量到的事實）。沒有一句生成的散文，零 LLM。

**只寫到「日」。** 一天 12 班，任何帶時分秒的欄位都會讓檔案每兩小時產生一次
沒有資訊量的 diff。33 個 Sources 頁 × 12 班 = 一天 396 次無意義的檔案異動，
真正的變化會被埋掉。所以 `robots_checked_at` 只取前 10 個字元存成
`robots_checked_day`，健康頁只有 `generated_day`。

**內容沒變就不重寫檔案。** 同一天內第 2～12 班通常什麼都不寫。

**要寫的時候走原子寫。** `health.md` 用 `lib/atomicwrite`（tmp + `os.replace()`）。
`ulimit -f 2` 重現過直接寫的下場：一頁 frontmatter 沒閉合的 2048 bytes 被 CI
提交上去——而這一頁就是死人開關本身，告訴人「鏈是活的」的那一頁自己是壞的。
見 references/atomic-writes.md。

**只放 allowlist 欄位（紅線 6）。** `endpoint` 是公開 URL 可以進；
headers、api key、本機路徑、私有備註一個都不准進 vault。

## `Sources/<id>.md`

每條來源一頁，四態並排：

| 層 | 來源 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `sources.yaml` 的 `lifecycle` | `draft`/`dormant` ＝根本不會被抓 |
| 已觀測 | `_corpus/` 裡相異的 `url_canonical` 數 | 抓到了但站方那陣子沒發東西 |
| 有效產出 | `Events/*.md` 的 `evidence[].source_id`（不含 `status: dropped`） | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 上一格之中 `status: published` 的 | 綁上了但門禁擋著——設計，不是故障 |

「有效產出」數的是**事件數不是證據筆數**：同一則事件引同一條來源三次，
對「這條來源有沒有促成一則事件」這個問題來說是一次。同樣的理由，它**不數
`status: dropped` 的事件**——被丟掉的事件不是產出，把它算進來會讓「抓到了但
聚類沒綁上」跟「綁上了但被丟掉」看起來一樣。

### 「已觀測」數的是相異項目，不是行數

`_corpus/<日>/<來源>.jsonl` 是**當天看到的清單**，不是當天新增的清單：一則
還掛在 feed 上的新聞，每天都會再被寫進當天的檔案一次。所以累計行數數的是
**項目 × 天**，不是項目數——2026-07-26 實測 956 行對 461 個相異項目，虛胖了一倍。

虛胖本身還不是最糟的，最糟的是它**跟旁邊那一格不同單位**：「有效產出」是刻意
去重過的事件數。兩個不同單位的數字並排放在同一張表裡比較，得到的印象一定是錯的。
所以「已觀測」數 `(source_id, url_canonical)` 的相異數；`url_canonical` 是
`pulse-probe.py` 寫每一列時就算好的，這裡不重算、也不做任何新的正規化。

`health.md` 的 `items_observed` 走同一支 `lib/corpus.observed()`，所以兩頁的
數字**保證同義**。改這個定義會讓那個數字一次性下降，那不是資料掉了，是單位換了。

### 沒抓過就寫沒抓過（紅線 8）

`items_observed: 0` 有兩個完全不同的意思：**量到 0** 跟**量不到**。前者是這條
來源成功抓過、只是那段時間站上沒東西；後者是它從來沒有成功抓過一次，我們對它
的產出量一無所知。用同一個 `0` 表示兩者，就是「用空值代表兩種不同的事」——
而且它出現在給人看的頁面上。

判準是 `_probe/state.json` 的 `first_fetch_at`：那個欄位只在一次成功抓取之後
才會被 `setdefault` 寫下去，寫了就不再改。**沒有它就是從沒抓過**（光有
`state.json` 的條目不算——失敗也會留下 `etag` / `last_run`）。

- 從沒抓過：frontmatter 的 `items_observed` 留空（不是 0），四態表印
  **「尚未抓取過」**，並且多印一行說明「這是量不到，不是量到 0」。
- 抓過但相異數是 0：照舊印 `0 筆`，那是真的量到 0。

### 「收錄」那一格印的是事實，不是設定意圖

`lifecycle` 是**設定意圖**，`_probe/source-health.json` 的 `last_status` 是
**上一班的事實**，而兩者會分岔：一條 `lifecycle: probing` 的來源如果每班都被
robots 擋掉，設定說「會被抓」，事實是一次都沒抓到。只印 lifecycle 就是拿一個
比事實寬鬆的代理指標代表事實——這一頁本來就是為了不讓那種事發生才存在的。

所以 `last_status` 是下面這幾種「沒有真的送出請求」的理由時，這一格印理由而不是
「會被抓」：

| `last_status` | 印什麼 | 是故障嗎 |
|---|---|---|
| `robots_disallow` | 每班都被跳過：站方明文 Disallow | **不是**，是合規 |
| `robots_unknown` | 每班都被跳過：robots.txt 取不到，保守跳過 | **不是**，也不是站方拒絕 |
| `skipped_lifecycle` | 不會被抓：lifecycle 不在可跑清單裡 | **不是**，是設定 |

三種都不扣健康分——它們不是故障。頁面說實話跟健康分扣不扣是兩回事。

另外三個條件式提醒，只在該情況成立時才印：
`robots_ok` 為空時說明「空值＝還沒量到，不是允許也不是禁止」；
`can_satisfy_primary: false` 時說明它只能佐證不能當一手；
有 `media_group` 時說明同集團兩條來源加起來只算一個獨立聲音（紅線 5）。

```bash
VAULT_DIR=... python scripts/pulse-source-notes.py
VAULT_DIR=... python scripts/pulse-source-notes.py --prune   # 一併移除孤兒頁
```

`--prune` 只在 `sources.yaml` 真的刪掉一條時才有事做。CI **不掛** `--prune`：
自動刪 vault 檔案是不可逆的，而孤兒頁的代價只是多一個沒人連的檔案。

## `_dashboards/health.md`

`pulse-monitor.py --write-health` 產生。內容全部來自 `scan()` 與 `coverage()`
已經算好的數字，加上 `_probe/` 的班次日曆與 `_probe/source-health.json`。

### 紅燈綁在哪個數字上

```
status = red  if  今天 − last_success ≥ monitor.stale_after_days   （gate.yaml）
             or  今天 − last_success < 0                           （時鐘壞了）
```

`last_success` ＝ `_corpus/` 裡最後一個**有語料**的日子。「有語料」的判準是
目錄裡至少有一行非空白的 `.jsonl`，而且目錄名要是真的日期——**光有目錄不算**。
負的 lag 也判紅，而且訊息跟「太久沒抓到」分開。這兩條規則跟它們各自要防的
「警報自己把自己關掉」的形態，寫在 `references/health-alarms.md`。

### 兩條時間軸為什麼要分開

```
_probe/<day>/report.md   每班都寫，不管有沒有抓到東西  → 鏈有沒有在跑
_corpus/<day>/*.jsonl    只有真的收到項目才會建        → 鏈有沒有看見東西
```

只看 `_corpus/` 會把「今天大家都沒發新聞」誤判成鏈死了；只看 `_probe/` 會把
2026-07-24 那種「鏈跑得很完美但什麼都看不見」判成綠燈。**靜默死掉**與
**靜默瞎掉**是兩種病，所以健康頁兩條都印，紅燈只綁在下面那條。

### 這頁自己就是死人開關

鏈沒跑就沒有人重寫它，`generated_day` 會停在最後一次跑班的日期不動。
所以看這頁的順序是：先確認 `generated_day` 是今天，再看 `status`。
一個停在三天前的綠燈是紅燈。

```bash
VAULT_DIR=... python scripts/pulse-monitor.py --write-health
VAULT_DIR=... python scripts/pulse-monitor.py --alert-stale   # 過期 → exit 1
```

`--alert-stale` 掛在 workflow 最後那個 `if: always()` 的死人開關步驟裡，
跟 `--alert-coverage` 同一行。那一步在部署之後，紅燈不擋上線，只寄通知。

### 榜單的中文描述：一格「跳過不留痕跡」的補丁

`_dashboards/health.md` 多一區〈GitHub 動能榜的中文描述〉。實作：
`lib/ghdesc.py` 的 `next_coverage()` / `days_without_zh()`（判準）、
`pulse-github.py` 的 `write_desc_coverage()`（每班寫 `_github/desc-coverage.json`）、
`pulse-monitor.py` 的 `desc_zh_line()`（渲染）。

**為什麼要有這一格。** 榜上的英文描述由潤稿端的 C2 段翻成中文，而
`scripts/enrich-runbook.md` 對 C2 的規定是：

> 這步失敗就整個 C2 段跳過，不影響其他段——榜會維持上一晚的英文原文。

跳過是對的（翻譯是加分項，不該擋住抓取鏈）。**沒有留下痕跡不對**：
「跳過了」跟「沒有東西要翻」在 repo 這端印起來一模一樣——兩種情況下
`_github/desc-zh.json` 都不存在。2026-07-27 實測：那個檔在**整個 git 歷史裡
從來沒有出現過**，而沒有任何一天有人發現。

**修法不是叫潤稿端更努力回報。** 它失敗的時候本來就寫不進 repo。
觀測要住在**一定會跑的那一邊**——Actions 每班跑 `pulse-github.py`，讓它量一次
結果、寫進版控。這跟「健康分沒有輸入」那次是同一句話。

**分母是整頁，不是其中一個榜（2026-07-29 補）。** 那一頁從 07-29 起是兩個榜
（星速 `repos` ／ 竄升 `surging`），它們是同一批 repo 的兩種排序、各自截前
`top_n`，所以 `surging \ repos` 非空是結構上一定可能發生的。原本這條翻譯鏈
從頭到尾只認 `repos`：待譯清單不掃竄升榜（那些 repo 永遠是英文）、寫回端不認
竄升榜（翻回來會被退件、理由是「不在目前榜單上」，而它就在榜上）、覆蓋率的
分母是星速榜的條數（榜上一半是英文的時候照樣印得出滿分）。

四個地方現在共用 `ghdesc.board_union(repos, surging)`：`pulse-github-desc-prep`、
`pulse-github-desc-apply`、`pulse-github.py` 的 `write_desc_coverage`、以及榜單頁
那行 JS。**輪流取不是接起來**——`--limit` 的額度要對兩邊一樣狠，不然星速榜偏袒
大 repo 那條偏袒會從排序爬回翻譯順序。

差集實際多大這裡量不到（api.github.com 在 Cowork 容器是 403）。

### 三種狀態要分得出來

| `desc-coverage.json` | 印什麼 | 這是什麼 |
|---|---|---|
| 檔案不存在 / `ranked` 是 `null` | 量不到 | 那一班沒抓到榜單，這一格沒有資訊——**不是 0** |
| `with_zh: 0`、`last_with_zh_day: null` | 從來沒有成功翻過一次 | **缺工**，不是故障 |
| `with_zh: 0`、`last_with_zh_day` 有值 | 最後一次有中文是 X（N 天前） | **故障**：翻譯鏈斷了 |
| `with_zh > 0` | N/M 條 | 正常 |

`last_with_zh_day` 是**黏的**——只有真的量到中文才更新。分不出「從來沒有」與
「昨天還有」的話，第一種會被讀成第二種。

### 這一格刻意不判紅燈

第一天本來就是 0 條中文。把它接成警報，CI 從上線第一天就天天紅——而
**一個天天紅的 CI 跟一個永遠綠的一樣沒有資訊**（這句話在本 repo 已經寫過三次）。
要判紅的是「**有過然後停了**」，而那個天數已經印在這一格上，接警報的時候直接讀
`days_without_zh()` 就好。**現在不接**，因為門檻要幾天沒有人知道——等它真的斷過
一次，那個數字才有依據。

## `_dashboards/backlog-status.md`

> 實作：`scripts/pulse-backlog-status.py`。

### 為什麼要有這一頁

`BACKLOG.md` 以前有一張手寫的〈現況〉表：`main` 的 commit、selftest 條數、
變異數、可刪分支數、Events 數、語料天數。2026-07-27 那一版**寫下之後 3 小時
就過期了**——四條分支被合併，六格同時作廢。

那是這個 repo 那個老毛病的第 9 個實例：**用一張量過的表代理現況**。
但真正值得寫進規格的是**第一次修法為什麼失敗**：當時的做法是「把量測時間寫進
標題、在最後一節請下一個人複量」。那是一個**靠人記得**的機制——而那份清單存在
的理由，就是不要有那種機制。三小時就證明它不夠。

所以照本 repo 一貫的分法：**量測是機械的，判斷是人寫的**（跟 `gate.yaml`
標記涵蓋檢查同一句話）。數字每班重生成，`BACKLOG.md` 只留判斷，
**手寫檔案裡一個會過期的數字都不留**。

### 放什麼

只放**每班量得到、且只讀 vault 就量得到**的東西：

| 區塊 | 來源 |
|---|---|
| Events 總數與 `published` / `review` / `dropped` / `stale_backfill` | `Events/*.md` |
| `_corpus/` 天數與起訖 | `_corpus/` |
| 來源總數、`lifecycle` 與 `language` 分佈、`coverage_watch` 的 pending 數 | `_config/sources.yaml` |
| `gate.yaml` 的 leaf 總數 / 標未接線 / 有消費者 | `lib/gate_keys.parse()` |
| 最後一班 probe 的時間、條目數、status 分佈、零產出來源清單 | `_probe/source-runs.jsonl` |

這一支**不碰網路、不呼叫 git、不跑子行程**。加上任何一項，這一頁就會在
沒有網路的環境（例如本機重現）長得不一樣，而一頁在不同環境長不一樣的儀表板
不能拿來對帳。

### 刻意不放的三格

- **selftest 條數**與**變異結果**。它們不是每班量得到的事實：跑一次要幾十秒到
  幾分鐘，而且各自已經有自己的 workflow 在紅綠。放上來只會得到一個「上次不知道
  什麼時候量的」數字——**而這一頁存在的理由就是不要有那種數字**。
  它們留在 `BACKLOG.md`〈附：怎麼重新盤點這份清單〉的指令裡，由人在需要時跑。
- **`main` 的 commit**。這一頁自己住在 repo 裡，它是哪一版產生的，`git log`
  比任何自我宣稱都準。頁面自報 commit 是一個可以跟事實分岔的欄位。

### 零產出那一格只列 id，不重算判定

最後一班「200 但 0 筆」的來源只列 `id`。**屬於哪一種 0 不在這裡重算**——
那個判定住在 `pulse-probe.zero_yield_reason()`，結果寫在
`_probe/<日>/report.md`〈零產出診斷〉（規格 `references/health-alarms.md`）。
在這裡重算一次就會有兩份判準，而兩份判準遲早會給出不同的答案。

### 這一頁自己會不會過期

會，而且它不自己叫。它的新鮮度靠的是**跟 `health.md` 同一班寫出來**：
排程死了，`health.md` 的 `generated_day` 就會停住，死人開關會叫（本檔開頭那一節）。
也就是說這一頁的守護者是隔壁那一頁，不是它自己。

代價要講清楚：**如果只有這一支炸掉**（它有 `continue-on-error: true`，跟另外兩支
一樣），`health.md` 照常更新、CI 全綠，而這一頁停在昨天——沒有任何東西會紅。
這是已知的洞，不是設計的完整性。**它比手寫表好的地方只有一個：手寫表要等人想起來
才更新，這一頁要 CI 壞掉才停。** 補法（還沒做）是讓 monitor 把
`backlog-status.md` 的 `generated_day` 跟 `health.md` 的比對，差一天以上就叫。

### 共同規則照舊

`generated_day` 只到日、內容沒變就不重寫、原子寫、allowlist 欄位、零 LLM。
缺席的欄位印「量不到」不印 0（紅線 8）。

## `_dashboards/dictionary-gaps.md`

> 實作：`scripts/pulse-dictionary-gaps.py`，判準 `scripts/lib/dictgaps.py`，
> 門檻 `_config/gate.yaml` 的 `clustering.unknown_entity`。

### 為什麼要有這一頁

`gate.yaml` 從上線那天就寫著 `report_to: _dashboards/dictionary-gaps.md`。
**那個檔案不存在，也沒有任何一行碼會去產生它。**

字典缺口在此之前只出現在 `_probe/<日>/report.md` 的當班區塊——一天 12 班，
每一班各自算各自的，沒有任何地方把它們加起來。要發現「這個詞這週被講了 11 次」
只能靠人翻語料。寫進設定檔的那個路徑，於是變成一句「這件事有人在管」的宣稱。

跟 `references/evidence-tiers.md` 那次是同一個形態：**用「設定檔裡有一個路徑」
代理「那件事有產出」**。寫的人當天是誠實的，只是沒有任何一條測試會因為被指到的
檔案不存在而變紅。

### 次數是「相異項目」，不是「出現行數」

`_corpus/<日>/` 是**當天看到的清單**，不是當天新增的清單：一則還掛在 feed 上的
新聞每天都會再被寫進當天的檔案一次。跨天直接累加行數，數到的是**項目 × 天**。

這個坑 `Sources/*.md` 的 `items_observed` 踩過（實測 956 行對 461 個相異項目，
虛胖一倍），本檔前面那一節寫得很清楚。所以這一頁先把 `(source_id,
url_canonical)` 去重再計數——**去重之後它才跟當班區塊同單位**，兩張表的數字才
能一起讀。

### 門檻只有一份

晉升門檻（跨 ≥N 來源、≥M 次）住 `gate.yaml`，判準住 `lib/dictgaps.py`，
`_probe` 的當班區塊與這一頁**讀同一份**。在新腳本裡把門檻再寫一次是最省事的
作法，也是這個 repo 已經量過三次的失敗形態（`lib/sources.py`、`lib/entities.py`、
那份手寫的未接線清單）：兩邊在門檻沒動過的日子裡給一樣的答案，正好在有人調了
其中一邊的那天分岔，而不會有任何東西變紅。

門檻讀不到時退回預設 3 / 2，**不是退回 0**：0 會讓每一個一次性雜訊都晉升，
也就是設定檔壞掉的時候規則反而變鬆。

### `report_to` 不准指到 vault 外面

那個值是設定檔給的相對路徑，解析後必須仍在 vault 裡；越界就退回預設路徑。
設定檔走 PR，但一個能把檔案寫到 vault 外面的欄位不該存在。

### 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。第一次跑出來的達標
  清單裡有 `Gemma`（真的該收），也有 `June` / `Here` / `One` / `Industry`
  ——`CAND_STOP` 太短，一般英文大寫詞會洗版。**這是收割層的問題，不是這一頁
  算錯**；這一頁的價值正是讓它第一次看得見。記在 `BACKLOG.md`。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口。中文來源進來
  之後這一頁會系統性低估。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，同一個詞的兩種寫法分別計數，
  兩邊都可能因此構不到門檻。
- **它不會自己改字典。** 收不收是人的決定。

## 排在哪裡

四支都排在 `Source health (0 LLM)` 之後（才讀得到這一班的分數）、
`Commit & push data changes` 之前——它們產生的是要進版控的 vault 檔案，
排在 commit 之後就等於整天不會被推上去。selftest 有一條測試釘住這件事。

**而且四支必須各佔一個 step，不得共用同一個 `run:`。** GitHub Actions 的 `run:`
是 `bash -e`：前面那行非零，後面那行根本不會執行。兩支曾經同處一個 `run:`，
後果是這樣串起來的——`_probe/state.json` 被寫壞成非 dict（`pulse-source-notes.py`
在那裡沒有防呆）→ 筆記產生器丟例外 → `--write-health` 不會跑 → `health.md` 的
`generated_day` 停在昨天 → 死人開關報「排程整個死掉」。

鏈其實是好的，死的是一支觀測腳本。一個指向錯誤位置的假警報比沒有警報更花時間，
而這兩件事本來就該分開判（見本檔開頭：「幾天沒抓到東西」與「排程死了」是兩個問題）。
selftest 解析 workflow 的 YAML 結構去釘這件事，不比對字串位置——比對字串位置的
測試會在改個 step 名字時紅，卻看不見兩個指令被塞回同一個 `run:`。
