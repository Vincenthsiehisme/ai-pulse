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

---

# 第三個現場：呈現層（2026-07-27）

上面兩節的結論是「**監控**自己的鏈只能用我們的時鐘」。這一節補的是另一半：
**對外呈現時，兩個時鐘都必須出現。**

判斷層用錯時鐘，只有我們自己看得到（CI 紅了、警報吵了）。呈現層用錯時鐘，
是對外的——而且不會有任何東西變紅。

## 病灶：版面宣稱了資料不支持的東西

`pulse-render.py` 的事件時間軸與事件頁的〈發展歷程〉，時間只有一個來源：
`happened_at` / `date`，也就是**外面的世界**那個時鐘。我們自己什麼時候開始看得到，
畫面上一個字都沒有。

2026-07-27 實測（重量指令在本節最後）：

| 量到的 | 當時的數字 |
|---|---|
| 已發布事件**只有一筆**證據 → 〈發展歷程〉只有一個項目，而它被標成「起點」 | 32 / 36 |
| 全部證據來自**同一次首抓**（來源的 `first_fetch_at` 相同）→ 是快照不是歷程 | 35 / 36 |
| 事件日期早於「其所有證據來源的首抓日」→ 事情發生時我們一條相關來源都沒有 | 30 / 36 |
| 來源的首抓日在 07-25 或更晚 | 19 / 26 |
| 時間軸實際顯示的跨度 | 07-07 → 07-25 |

三個詞在說謊：

- **「發展歷程」**——97% 的情況下它是一次撈取的快照。
- **「起點」**——判準是 `classify_dev(sid, sources, is_first)` 裡的
  `if is_first: return "origin"`，也就是**排序位置**。88% 的情況下那個「第一」
  同時是「唯一」。這是拿一個關於**我們資料的位置**的事實，去印一個關於**世界**的宣稱。
- **時間軸的日期跨度**——看起來像三週的持續觀測，實際是首抓時撈回的存量。

跟 `HEAT_UNMEASURED = "未量測"` 是同一條規矩：那裡不印 `0`，因為 `0` 會被讀成
「量過了，很冷」。這裡一個沒有標示的舊日期會被讀成「我們當時在看」。

## 判準（確定性，0 LLM）

```
observable_from(event) = min(first_fetch_at[s] for s in 該事件證據的來源)
coverage(event) = "observed"    if happened_at >= observable_from
                = "backfilled"  otherwise
                = "unknown"     if 任一來源沒有 first_fetch_at
```

封閉集：`observed` / `backfilled` / `unknown`。

三件事要講清楚：

1. **資料全部現成，不新開真相源。** `first_fetch_at` 住在 `_probe/state.json`，
   已經被 `pulse-monitor.py` 的 `silent_pending_clock` 消費（`fix/coverage-uses-own-clock`
   就是把沉默判準從「語料庫總長度」改成這個欄位）。這裡讀同一份。
2. **這不是發明新概念，是讓既有旗標多活一跳。** 訊號層本來就有 `is_backfill`
   （`pulse-probe`），gate 層本來就有 `stale_backfill`——但旗標到 Event 就斷了，
   2026-07-27 實測 Event frontmatter 沒有任何 backfill 欄位。
3. **`unknown` 不得併進 `observed`。** 量不到就說量不到（紅線 8）。併進去的話，
   任何 `state.json` 的缺格都會靜靜變成「我們當時在看」——**往說謊的方向倒**。

關於 `unknown` 的誠實話：2026-07-27 實測它套用到 **0 則**事件。唯一沒有
`first_fetch_at` 的來源是 `src-arxiv-cs-cl`（robots 擋掉、從未成功抓取，見
`references/incidents/2026-07-24-arxiv-robots.md`），而從未抓取的來源也綁不出證據，
所以這條路徑今天走不到。**它仍然要存在**，理由不是它現在有用，是缺格時的預設值
必須倒向誠實那一邊——`state.json` 被重設、來源改 id、或首抓失敗但證據從別的路徑
綁進來，都會讓這一格空掉，而那時候沒有人會記得回來補這個判斷。

`observable_from` 只看**該事件證據的來源**，不看整個 watch set。理由是可 explain：
每一則都能指到具體來源與具體日期——「證據來自 `src-X`，我們 07-26 才第一次抓它，
而事情 07-14 就發生了」。用整個 watch set 會得到一個沒有人能逐則複查的門檻。

## 呈現規則

### 事件頁的〈發展歷程〉

| 條件 | 區塊標題 | 第一項的標籤 |
|---|---|---|
| 證據 1 筆 | 〈證據〉 | 無標籤 |
| 證據 ≥2 筆，但全部來自同一次首抓 | 〈首抓快照〉 | 無標籤 |
| `coverage: observed` 且證據橫跨多次抓取 | 〈發展歷程〉 | 「起點」 |
| `coverage: backfilled` 或 `unknown` | 〈證據〉 | 無標籤 |

**只有第三列會出現「起點」。** 一個只有一項的清單不叫歷程，它唯一的那一項也不叫起點。

### 事件時間軸

- 畫一條**觀測起點線**，線以下標明：「回填區：首抓時撈回的存量，不代表我們當時在追」。
- `coverage: backfilled` 的卡片帶標記。`unknown` 用另一個字樣，不共用同一個標記——
  「確定是回填」與「不知道」是兩件事。

### fallback 不得編造

`journey_html()` 現在查不到語料時，**標題退回來源名、日期退回事件日**。兩個都要改：

```
標題：evidence[].title → corpus_idx → 「標題未留存」（不得印來源名）
日期：evidence[].published → corpus_idx → 「日期未留存」（不得印事件日）
```

2026-07-27 實測這條路徑只有 1/46 觸發（`load_corpus_index` 同時用 `url` 與
`url_canonical` 建鍵，所以命中率很高），**但機制本身不安全**：印事件日會讓一則
事件的所有證據看起來同一天出現，而那正是讀者用來判斷「這件事怎麼發展」的唯一線索。

### 一條沒被記下來的依賴

〈發展歷程〉的標題與日期目前**完全依賴 `_corpus/` 永久保存**。而
`BACKLOG.md` 的 `corpus-累積` 是一條**未決**的「要不要改成滾動視窗」——
改成滾動會靜默打壞所有舊事件的這一區，而做那個決定的人沒有任何地方看得到這條依賴。

所以上面「標題／日期優先讀 `evidence[]`」不只是排序偏好，它是**讓這一區不再依賴
語料保留期**的手段。做完之後 `corpus-累積` 才是一個可以自由決定的問題。

## 遷移

新欄位 `coverage` 寫進 Event frontmatter。既有 52 則的補法：

1. `coverage` 由 `_probe/state.json` 的 `first_fetch_at` 與 Event 自己的
   `happened_at` **每班 rescore 重算**，不是一次性寫死。所以既有事件在下一班
   自動獲得這一格，不需要遷移腳本。
2. `evidence[].title` / `evidence[].published` 是 2026-07 才加的欄位，
   2026-07-27 實測 62 筆只有 1 筆有。補法分兩半：
   - **title**：從 note 內文〈證據〉區解析（`- [[Sources/x|x]] — 標題（url）`），
     2026-07-27 實測 61/61 全部帶標題，**不需要網路、不需要語料**。
   - **published**：只能從現存語料補，補不到的留空，由上面的 fallback 印「日期未留存」。
3. **不回頭抓舊語料補歷史。** 那要連網、碰 robots（紅線 7），而且是拿外部行為
   去補我們自己的觀測紀錄——正是本檔前兩節在反對的事。

`coverage` 是**推導欄位不是 sticky 欄位**：它每班從 `state.json` 重算，
所以不受 `event_markdown()` 整份重寫的影響（跟 `ingested_at` / `title_zh`
那批要讀回來再寫出去的欄位不同，見 `references/obsidian-schema.md`）。

## 回滾

三層各自可獨立關掉，關掉後回到現狀、不留半套：

| 關掉什麼 | 做法 | 回到什麼 |
|---|---|---|
| 時間軸的觀測起點線與標記 | render 不讀 `coverage` | 現狀的時間軸 |
| 〈發展歷程〉的改名與標籤紀律 | `classify_dev` 回到 `is_first` | 現狀的歷程區 |
| `coverage` 欄位本身 | cluster 不寫這一格 | frontmatter 少一格，無消費者會炸 |

三層之間沒有反向相依：先上第三層（欄位）也不會改變任何畫面。建議順序就是
欄位 → 歷程區 → 時間軸，每一層自己可驗收。

## 要新增的 selftest

- `coverage`：`happened_at` 早於 `observable_from` → `backfilled`；等於 → `observed`；
  任一來源缺 `first_fetch_at` → `unknown`，且 `unknown` 不得等於 `observed`。
- `observable_from` 只取**該事件證據來源**的 `first_fetch_at`，不取全體最小值。
- 單筆證據的事件：區塊標題不得是「發展歷程」，且不得出現「起點」標籤。
- 證據全部來自同一 `first_fetch_at`：不得出現「起點」標籤。
- fallback：查不到語料時，標題不得等於 `prettify_source(sid)`、日期不得等於事件日。
- 時間軸：`backfilled` 與 `unknown` 的標記字樣必須不同。
- `coverage` 每班重算：改 `state.json` 的 `first_fetch_at` 後重跑，該格要跟著變
  （證明它不是被寫死的 sticky 欄位）。

## 要新增的 mutation（接在 M84 之後）

| id | 變異 | 為什麼這格值得釘 |
|---|---|---|
| M85 | `coverage` 的 `unknown` 併進 `observed` | 缺格會靜靜變成「我們當時在看」——往說謊的方向倒 |
| M86 | `backfilled` 事件照樣發「起點」標籤 | 這就是修正前的行為，不釘住會原地長回來 |
| M87 | 單筆證據照樣叫「發展歷程」 | 88% 的事件走這條路，壞了畫面看起來完全正常 |
| M88 | 日期 fallback 改回退事件日 | 失效是靜默的：頁面照印，只是所有證據看起來同一天 |
| M89 | `observable_from` 改取全體來源最小值 | 幾乎所有事件會變成 `observed`，而「數字變好看」不會讓任何測試變紅 |

五格全部必須被測試**殺掉**，而不是以 crash 代替失敗。

## 重量指令

```bash
cd <vault> && python3 - <<'PY'
import json, glob, yaml
from collections import Counter
st = json.load(open('_probe/state.json'))
ff = {k: (v.get('first_fetch_at') or '')[:10]
      for k, v in st.items() if isinstance(v, dict)}
pub = []
for f in glob.glob('Events/*.md'):
    d = yaml.safe_load(open(f).read().split('---')[1])
    if d.get('status') == 'published':
        pub.append(d)
one = same = unobs = 0
for d in pub:
    ev = d.get('evidence') or []
    firsts = {ff.get(e.get('source_id')) for e in ev if ff.get(e.get('source_id'))}
    if len(ev) == 1:
        one += 1
    if len(firsts) == 1:
        same += 1
    if firsts and str(d.get('date')) < min(firsts):
        unobs += 1
print(f"published {len(pub)}｜單筆證據 {one}｜同一次首抓 {same}｜當時看不到 {unobs}")
print("來源首抓日分佈:", dict(sorted(Counter(ff.values()).items())))
PY
```

## 這一節不保證什麼

- **不保證 `backfilled` 的事件不重要。** 它們有資訊價值，只是不能假裝是我們追到的。
  這一層只管標示，不管取捨——不刪、不降權、不排除在時間軸外。
- **不保證改完之後畫面好看。** 2026-07-27 的數字下，36 則裡會有 30 則被標成回填，
  首頁會空很多。這是這個修正唯一真正的代價，而且**它會自己好**：每過一天
  observed 區就多一天真實觀測，回填區永遠停在那裡，變成一段誠實的「開站前存量」。
  反過來，不改的話那個「看起來有三週歷史」的假象是永久的，而且事件越累積越難撤回。
