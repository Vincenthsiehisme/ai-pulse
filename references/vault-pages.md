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

**只放 allowlist 欄位（紅線 6）。** `endpoint` 是公開 URL 可以進；
headers、api key、本機路徑、私有備註一個都不准進 vault。

## `Sources/<id>.md`

每條來源一頁，四態並排：

| 層 | 來源 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `sources.yaml` 的 `lifecycle` | `draft`/`dormant` ＝根本不會被抓 |
| 已觀測 | `_corpus/**/*.jsonl` 累計行數 | 抓不到，或站方那陣子沒發東西 |
| 有效產出 | `Events/*.md` 的 `evidence[].source_id` | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 上一格之中 `status: published` 的 | 綁上了但門禁擋著——設計，不是故障 |

「有效產出」數的是**事件數不是證據筆數**：同一則事件引同一條來源三次，
對「這條來源有沒有促成一則事件」這個問題來說是一次。

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
```

`last_success` ＝ `_corpus/` 裡最後一個有語料的日子。

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

兩支都在 `Deterministic pipeline (0 LLM)` 裡、`pulse-render.py` 之後、
`Commit & push data changes` 之前——它們產生的是要進版控的 vault 檔案，
排在 commit 之後就等於整天不會被推上去。selftest 有一條測試釘住這件事。
