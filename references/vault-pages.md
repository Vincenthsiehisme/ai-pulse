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

## 排在哪裡

兩支都排在 `Source health (0 LLM)` 之後（才讀得到這一班的分數）、
`Commit & push data changes` 之前——它們產生的是要進版控的 vault 檔案，
排在 commit 之後就等於整天不會被推上去。selftest 有一條測試釘住這件事。

**而且兩支必須各佔一個 step，不得共用同一個 `run:`。** GitHub Actions 的 `run:`
是 `bash -e`：前面那行非零，後面那行根本不會執行。兩支曾經同處一個 `run:`，
後果是這樣串起來的——`_probe/state.json` 被寫壞成非 dict（`pulse-source-notes.py`
在那裡沒有防呆）→ 筆記產生器丟例外 → `--write-health` 不會跑 → `health.md` 的
`generated_day` 停在昨天 → 死人開關報「排程整個死掉」。

鏈其實是好的，死的是一支觀測腳本。一個指向錯誤位置的假警報比沒有警報更花時間，
而這兩件事本來就該分開判（見本檔開頭：「幾天沒抓到東西」與「排程死了」是兩個問題）。
selftest 解析 workflow 的 YAML 結構去釘這件事，不比對字串位置——比對字串位置的
測試會在改個 step 名字時紅，卻看不見兩個指令被塞回同一個 `run:`。
