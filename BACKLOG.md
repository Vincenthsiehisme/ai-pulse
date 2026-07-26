# AI-Pulse：應做而未做

這份清單只寫「**已知有問題、但還沒動手**」的事。修掉的移到最後的〈附：已經修掉的〉；
**修好了但還沒併進 `main` 的，算沒修**——這一版量的時候遠端零條未併，所以那一區是空的，
但規矩不變：分支上的數字不能寫進〈現況〉。

每一條有一個**不會變的名字**（`cron-收班`、`gate-未接線`…），沒有編號。
理由寫在下面〈為什麼這裡沒有編號〉——不是排版偏好，是量到的一個 bug。

## 現況（2026-07-26 23:30Z 量的 ／ 台北 07-27 早上）

| 量到什麼 | 值 | 怎麼量的 |
|---|---|---|
| `main` | `124a58c Merge pull request #10 …/docs/backlog-tidy` | `git fetch && git log --oneline -1 origin/main` |
| `main` 的 selftest | **322/322** | 在 `origin/main` 的 worktree 上 `python3 scripts/selftest.py` |
| `main` 的變異 | **32 條：32 被殺、0 存活** | 同上，`python3 scripts/mutate.py` |
| 遠端分支 | **34 條** = `main` + **0 條未併** + **33 條已併可刪** | `git ls-remote --heads`、`git branch -r --no-merged/--merged origin/main` |
| 夜間鏈 | 每 2 小時一班，最近一班 07-26 23:03Z：425 items / 32 sources | `data-refresh.yml` + `_probe/source-runs.jsonl` |
| Events | 51 則：`published` 36 / `review` 14 / `dropped` 1 | `grep -l '^status: …' Events/*.md` |
| `_corpus/` | **3 天**（07-24…07-26） | `ls _corpus/` |

複量指令在最後一節。上面每一格都是跑出來的，沒有一格是估的。

### 上一版這張表在合併的那一刻就過期了

上一版量的是 `4f3b23f` / 303 / 25 / 2 條未併，而且特別註明「分支上的 322 與 32
描述的是分支，不是 `main`」——那句話當天是對的。三條分支在台北 07-27 06:58–07:04
全部併進 `main` 之後，分支上的數字**變成了** `main` 的數字，表上卻還寫著 303 / 25。

**這是這份清單自己在講的病，第二次發生在它自己身上。**〈為什麼這裡沒有編號〉那節
講的是「用編號代理清單上的某一件事」；這一節是**用一張量過的表代理現況**。形態一樣：
沒有進展的日子裡兩者重合，正好在有進展的那天分岔，而有進展正是最多人來讀它的時候。
方向還特別不利——數字是往**變好**的方向跑掉的（303→322、2 條未併→0），沒有人會
因為看到一個偏低的測試數而起疑。

所以這一版把量的時間寫進標題，並且在最後一節重申：**不要相信上面的數字，直接複量。**
這條進了〈已經修掉的〉底下的實例清單，第 9 個。

## 為什麼這裡沒有編號

再上一版有 P0–P10。2026-07-26 梳理的時候（`docs/backlog-tidy`，PR #10），
在 repo 裡量到兩處指著編號的字：

```
scripts/selftest.py:794          # …不是拿整個語料庫的長度（BACKLOG P4）
references/readiness-gate.md:112 負責人：BACKLOG P2 收在這裡
```

寫下去的當天兩句都是對的。到那天 `P4` 指的是 gate 未接線、`P2` 是一條已經併掉的事，
**兩句話都在指別的東西了**，而且沒有任何一條測試會因此變紅——編號是位置，位置會
隨著清單重排而改變，但引用它的人不會跟著改。

這就是這個 repo 一直在抓的同一隻病：**用一個比事實寬鬆的代理指標去代表事實**。
「P4」代理的是「gate 未接線那件事」，兩者在清單沒動過的日子裡重合，正好在清單有
進展的那天分岔——而有進展，正是最多人會去讀它的時候。

所以改成**名字**：名字跟著事情走，事情結案了名字就進〈已經修掉的〉，
指著它的人至少搜得到自己引錯了。優先順序改由**表格裡的位置**表達，不由名字表達。
（上面那兩處已經在 PR #10 一起改掉了。`references/mutation-inventory.md` 裡
的「BACKLOG P1」不動——那些在「第一輪 / 第二輪」的段落裡，是歷史記錄，不是指標。）

## 排序準則

每一條的位置由兩個問題決定，不由它屬於哪個模組決定：

1. **它壞掉的時候，有沒有東西會變紅？** 不會變紅的排前面。會紅的東西自己會來找人，
   不會紅的東西要靠人記得。
2. **它現在是不是正在輸出一個錯的數字？** 「沉默的缺工」比不上「有聲的假數字」——
   空欄位沒人會信，假數字沒人會查。

所以順序大致是：**有時限 → 修了但沒生效 → 正在騙人且不會紅 → 守門的東西自己沒被守 →
資料進不來 → 做了一半 → 要你動手**。

這一版「修了但沒生效」與「正在騙人且不會紅」兩格是**空的**：三條分支都併進 `main` 了，
`main` 上也沒有已知的假話在對外輸出。空著是好消息，但這兩格是最會悄悄長回來的——
下一次盤點先問這兩格。

| 名字 | 事 | 壞了會紅嗎 | 現在在騙人嗎 |
|---|---|---|---|
| [`cron-收班`](#cron-收班) | 07-27 12:00Z 要把抓取頻率調回一天一班 | 不會 | — |
| [`gate-未接線`](#gate-未接線) | 一批 `gate.yaml` 的 key 沒有任何碼讀它 | 不會（已標記，漏標會紅） | 部分 |
| [`零產出來源`](#零產出來源) | 三條「可跑但零產出」，三種不同的病 | 不會 | — |
| [`pending-覆蓋`](#pending-覆蓋) | 20 家覆蓋盲點標著 pending | 刻意不會 | 否（誠實掛著） |
| [`people-第三步`](#people-第三步) | 語料的 `author` 還沒綁到 `person_id` | 不會 | — |
| [`corpus-累積`](#corpus-累積) | `_corpus/` 要不要改成累積視窗 | — | — |
| [`value-沒人用`](#value-沒人用) | 每則都算 `value`，全站沒有一處讀它 | 不會 | 否（沒宣稱過什麼） |
| [`stale-backfill-無出口`](#stale-backfill-無出口) | 12 則被擋著的 Event 沒有終態 | 不會 | 否 |
| [`分支刪不掉`](#分支刪不掉) | 33 條已併分支刪不掉、PR 開不了 | — | — |

---

## `cron-收班`

**唯一有時限的一條：2026-07-27 12:00Z（台北當天晚上 8 點）——寫這一版的時候還沒到。**

`data-refresh.yml` 現在的 cron 是 `0 */2 * * *`，一天 12 班；`robots --stale-days`
也一起從 7 調成 1。一天 12 次去打人家的 robots.txt 是不禮貌的，而且我們自己沒有
那個量的需求。

排第一只有一個理由：**這是唯一一條「今天不做，明天就沒得做」的事。**
其他每一條都可以晚一週，這條晚一週就是連續一週失禮。

兩層都還在（2026-07-26 23:30Z 複查，`enabled: true`、`ended_reason` 空）：

| 何時 | 任務 | 做什麼 | 下次 |
|---|---|---|---|
| 2026-07-27 12:00Z（一次性） | `trig_01F52Q24UntdNVTd3DWbxFgs` | 把兩個值改回 `0 16 * * *` 與 7 | 07-27 12:00Z（未觸發） |
| 每週一 16:00Z | `trig_015SHn9yjL6LtA9TsbeyGCdo` | 讀 `data-refresh.yml` 的實際值，超標就改回來 | 07-27 16:04Z |

複查當下 `data-refresh.yml` 仍是 `0 */2 * * *`，`--stale-days 1` 出現在第 68 與
第 212 行——**兩處都要改**，只改一處會讓「重驗頻率」跟「重驗門檻」對不上。

第二層不是備援心態，是這個 repo 的核心毛病：**一個只靠單次觸發的收班安排，如果
沒觸發，沒有任何東西會變紅**。所以第二層刻意**不去查第一層跑了沒**（那又是一個
代理指標），只讀檔案裡的實際值：cron 一天超過一班、或任一處 `--stale-days < 7`，
就改回來。收班不是改設計，所以它直接推 `main`、不開 PR。

也就是說這個頻率上限現在是**每週自癒**的，不是靠人記得。剩下要人管的只有一件：
兩個獨立排程同時失效——那就真的沒人管了。

---

## `gate-未接線`

`gate.yaml` 有一批 key 沒有任何程式碼讀它。它們**已經被標成 `⚠ 未接線`**，所以
現在不會再騙人——這也是它排在這裡而不是更前面的理由。**標記不等於修好。**

### 上一輪只做了止血補強（`fix/gate-keys-unmarked`，PR #9，已在 `main`）

上一版的標題寫「12 個」，那個 12 是**手工數的**；`selftest.py` 也是拿一份手寫的
12 個名字去比對。手工清單只擋得住一個方向：「標了未接線、後來卻接上了」。反方向
——**有人新增一個沒接線的 key 而忘了標**——上一版誠實寫了「測不到」，然後就沒有
再管它。**誠實地記下一個洞不會把洞補起來。**

把 55 個 leaf key 全部機械列舉出來比對，當場掉出兩個從來沒進過那張清單的：

- **`quality.weights` 整塊**（authority 25 / richness 25 / freshness 20 /
  originality 15 / completeness 15）。五個數字、總和剛好 100、名字對得上五個維度
  ——**這是整個檔案裡最像旋鈕的東西**。五個上限全部硬寫在 `lib/quality.py` 的五支
  函式裡，沒有任何一行碼讀 `weights`；`quality.py` 的 docstring 還寫著「各自上限見
  gate.yaml.quality.weights」，指向一組沒有人讀的數字。
- **`readiness.require_primary_evidence`**。這一個相反：它**不該**被接上。接線只要
  一行，而那一行會讓 `gate.yaml` 多一個能關掉紅線 2 唯一執法點的開關，然後 selftest
  全綠——因為每一條測試都是拿預設值跑的。假開關的傷害是有人改了它、發現沒效果、
  開始不信任這個檔案；真開關的傷害是有人改了它、**很有效果**。所以分成三類：
  **A. 未接線（待接）／B. 接線了但條件走不到／C. 刻意不接**。混在一起，下一個人會
  很熱心地幫我們接上。

現在的規矩：**列舉是機械的，標記是人寫的，測試比對兩者。** 每一個 leaf 都要被
`⚠ …未接線` 或 `消費者：<路徑>` 涵蓋（自己那一行或任何一層祖先），兩種都沒有就紅。
判準在 `scripts/lib/gate_keys.py`，它**不保證**什麼寫在
`references/gate-config-status.md` 最後一節。

### 還沒做的是接線本身

- **`dedup:` 整塊未接線**（`minhash_jaccard: 0.80`、`ngram: 4`、
  `event_window_hours: 72`）。真正在跑的是 `lib/cluster.py` 裡硬寫的 token-Jaccard
  加上 96h / 7d / 21d 三段窗口。把 `event_window_hours` 從 72 改成 48 重跑，聚類
  結果不會有任何變化——下一個人會去懷疑資料，而不是懷疑這個欄位。
- **`clustering.version_derivation`**：`claude@opus-4.8` 這種衍生實體不會產生。
- **`clustering.unknown_entity`**，而且它的 `report_to: _dashboards/dictionary-gaps.md`
  指向的檔案**不存在**。字典缺口目前沒有任何地方在收集，只能靠人翻語料發現。
- **`evidence.need_independent_tier2: 2`** 描述的「兩個獨立 Tier-2 也可以放行」這條
  替代路徑**不存在**；實際只有 `missing_primary_evidence` 一條規則在擋。
- **`evidence.translation_chain`**，後果很具體：一篇英文原文加上一篇中文改寫，現在
  算成**兩個獨立來源**。七條媒體線之所以全部只收英文就是在閃這個坑
  （`sources.yaml` 第 92 行）。**中文媒體要進來之前，這個必須先接上**——這是這一區
  裡唯一有前置關係的一條。
- `quality.freshness_full_hours` / `freshness_zero_days`（實際是
  `lib/quality.py:_freshness()` 的硬寫階梯）。
- **`quality.weights` 整塊**（見上）。要真的能調，得把 `lib/quality.py` 的五支函式
  改成讀這裡；在那之前它是一組會誤導人的正常數字。

---

## `零產出來源`

上一版把兩條寫成同一個病：「抓取端：從來沒抓過」。這一版改讀
`_probe/source-runs.jsonl`（每班每條來源的 status），**那兩條的「沒抓過」是兩件
不同的事**：

| 來源 | 每班的 status | 病灶 | 待修嗎 |
|---|---|---|---|
| `src-mistral-news` | `200`，items 全 0 | **解析端**：抓到了，解不出東西 | 是 |
| `src-media-theregister` | `robots_disallow` | **站方 robots 明說不行**（`sources.yaml` 的 `robots_ok: false` 是實測寫回的） | **不是。這是合規在正常運作** |
| `src-kol-thezvi` | `robots_unknown` | robots.txt 回 401/403 **取不到**，保守跳過——不是站方拒絕（`robots_ok` 仍是 `true`） | 是，但只能在 CI 裡查 |

**這份紀錄的範圍要講清楚**：`source-runs.jsonl` 目前只有 7 班、全部在 07-26
10:05Z–23:03Z 之間。所以上表說的是「這 7 班每一班都這樣」，不是「從上線以來」。
狀態穩定到這個程度已經夠判斷病灶，但別把它當成長期紀錄。

分開列的理由：**三條在儀表上都顯示成「零產出」，但只有第一條是我們的 bug。**
併成一句「三條零產出來源」，下一個人會平均地去修三條，其中一條無論怎麼修都不會有
產出——`theregister` 要有產出只有兩條路：站方改 robots，或我們決定不遵守。後者不會
發生，所以它該做的動作是**移出待修、標成「已知不會有產出」**，不是留著當缺工。
這跟「量不到 ≠ 0」是同一句話換個位置：**「被 robots 擋住」跟「壞了」不是同一件事，
擠在同一格裡就分不出來。**

`src-kol-thezvi` 的 401/403 是**打 robots.txt 就被擋**，跟 2026-07-24 漏抓
Claude Opus 5 那次同形態（容器／CI 的 IP 被 WAF 擋，不是站方拒絕）。現在的處理是
保守跳過、不記分、不降級——是對的；要注意的是別讓它日久被讀成「站方拒絕」。

`src-mistral-news` 的設定是 `adapter: sitemap` 指到 `sitemap-index.xml`，配
`url_prefix: /news/`。兩個可能：sitemap-index → 子 sitemap 的展開沒做（或
`max_sitemaps: 3` 抓到的三張剛好都不含新聞），或 `url_prefix` 對不上實際路徑。

**今天查不出來的原因要講清楚**：這個容器的 proxy 擋外部連線（403），我沒辦法在
本地抓那張 sitemap 驗證。要查只能在 CI 裡查，作法是讓 sitemap adapter 在零產出時
把「展開到幾張子 sitemap、過濾前的前幾條 URL」印進 `_probe/<日>/report.md`。
**那個 debug 輸出本身就值得做**——現在的 report 只說「200 / 0 筆」，分不出
「站上真的沒新東西」跟「我們解析不出來」。跟已經修掉的「量不到 ≠ 0」是同一個病灶，
只是換到了 report 上。

---

## `pending-覆蓋`

`_config/sources.yaml` 的 `coverage_watch.must_watch` 共 32 條，其中 **20 條 `pending`**：
DeepSeek、SSI、Thinking Machines、Perplexity、Cursor、Cognition、Scale AI、Z.ai、
Moonshot、MiniMax、ByteDance、Baidu、Tencent、TSMC、Broadcom、Groq、Cerebras、
CoreWeave、AWS、Cohere。

標了 `pending` 所以**不觸警**——這是誠實的做法（紅線 8），但「誠實地承認沒覆蓋」
跟「覆蓋到了」是兩回事。其中 DeepSeek、Scale AI、MiniMax、Broadcom、Cerebras
已經**在別人的語料裡被看見**，代表它們有新聞在流動，只是我們沒有第一手來源。

排這麼後面不是因為不重要，是因為它**沒有在騙人**：清單上寫著「沒有」，實際也沒有。
這是純粹的擴充工作，隨時可以做，做多少算多少。

---

## `people-第三步`

`person_id` 的獨立性計算（連通分量）已經接上、selftest 有釘。但
**每一列語料的 `author` 還沒有真的綁到 `person_id`**——現在 `person_id` 只從
`sources.yaml` 的來源層設定來。所以「同一個人在兩個平台發文」只有在那個人自己有
一條專屬來源時才抓得到；他投稿到媒體、或在 podcast 上講，綁不起來。

`pulse-probe.py` 第 74 行留了註解說明這件事。

---

## `corpus-累積`

現在是每天一個目錄、只放當天新看到的列，磁碟上有 **3 天**（07-24…07-26）。
覆蓋範圍檢查因此只有幾天的實有語料，monitor 自己會印「語料期間不足 30 天，沉默
天數僅供參考」。

要不要改成累積視窗，我沒有動，因為那會改變所有「近 30 天」統計的意義。
`fix/coverage-uses-own-clock` 併進去之後（已併），coverage 的守衛已經不再依賴語料庫
總長度，所以這題的急迫性降了一階——**但語料本身還是只有 3 天，決定權在你。**

---

## `value-沒人用`

`scoring.py` 每則 Event 都算一個 `value`，寫進 frontmatter，**然後沒有任何東西讀它**。
`pulse-render.py` 只依日期排序；全站沒有一處依 `value` 排序或篩選；
`dist/index.html` 裡 "value" 出現 **0 次**。

所以 heat 那次遷移造成的 rank delta（51 則裡 36 則換位、最大位移 12 名）**不是使用者
看得到的排名變動**。這件事必須這樣講，不然聽起來像動了排名。

一個算得很認真、沒人用的欄位有兩個誠實的出路：接上（讓它真的決定排序或門檻），
或刪掉。第三條路——繼續算著、繼續寫進 frontmatter、繼續沒人用——是紅線 8 那種
「留著看起來像有功能的東西」。

沒有排更前面是因為它**不騙人**：`value` 沒有對外宣稱它決定什麼。它只是浪費。
但它跟 heat 是同一個家族——`heat` 是「算了一個沒量到的東西」，`value` 是「算了一個
沒人要的東西」，兩個都是「這段碼看起來在做事」。

---

## `stale-backfill-無出口`

`Events/` 共 51 則（`published` 36、`review` 14、`dropped` 1），其中帶
`stale_backfill` 的有 **12** 則。

這些是「設計上擋著」的舊聞回填，不是卡住。行為是對的，但**沒有任何路徑讓它們離開
這個狀態**——它們會永遠留在 review，而且數量只會單調增加。要嘛給一個 `archived`
終態，要嘛定期清掉。現在只是靠 monitor 把它們跟真正的待處理分開印，不讓數字互相
污染。

---

## `分支刪不掉`

**需要你動手的兩件，我在這個環境做不到。**

### 一、刪掉已合併的 33 條分支

遠端現在 **34 條 head**：`main` + **33 條全部已完整併入**
（`git branch -r --merged origin/main | grep -v 'HEAD\|origin/main'` 數出來的），
可以安全刪除。上一版是 30 條，中間又併進三條。

`git push origin --delete` 被這個 session 的安全分類器擋著，我送不出去。
GitHub 網頁的 branches 頁面有一鍵刪除已合併分支。

### 二、GitHub API 在這個環境被 proxy 擋（403）

所以我**開不了真正的 PR**，只能推分支 + 你在網頁上合。這不影響「發現問題自己開
分支」那條規則，但要知道「PR」在這裡實際上是「分支 + 我在對話裡寫的 review 說明」。

**這件事就是「修好了但沒併進 `main` 的算沒修」那條規矩會被踩到的原因**：一條
「我做完、你來合」的交棒，如果你那頭沒動作，沒有任何東西會變紅。跟那個「隔離候選是
機器交棒給人的唯一介面，而它是斷的」是同一個形態，只是這次的介面是你我之間。
上一輪那兩條分支躺了半天才被合，就是這個介面的延遲——它自己不會叫。

---

## 附：已經修掉的

按併進 `main` 的時間排。**這一節只放已經在 `main` 上的**——躺在分支上的不算修好，
它們留在上面各自的條目裡，直到併進來為止。

| 事 | 修了什麼 |
|---|---|
| `fix/machine-writes-unbacked-robots-false`（PR #1） | 機器寫 `robots_ok: false` 也要交入場券；selftest 掛進 CI |
| `fix/retry-exhaustion-mislabels-429` | 重試耗盡不再謊報成重導；robots 回 200 但內容不是 robots.txt 不算放行 |
| `fix/ci-swallows-failures` | CI 不再吞掉 probe 的 exit 3；Vault pages 兩支拆成獨立 step，`bash -e` 管得到 |
| `fix/nonatomic-config-write` | 狀態檔一律 tmp + `os.replace()`，失敗刪 tmp |
| `fix/alarms-that-mute-themselves` | 目錄名不是證據（嚴格日期 + 內容驗證）；未來日期判紅；缺 `ingested_at` 本身就算警報 |
| `fix/health-snapshot-dry-run`（PR #2） | 隔離候選真的寫進磁碟快照（機器交棒給人的唯一介面接回來了）；`--json` 這種只看的跑法不再改持久狀態 |
| `fix/observed-counts-item-days`（PR #3） | `Sources/*.md` 不再把「量不到」印成「0 筆」；`items_observed` 改數相異 `(source_id, url)`；`events_bound` 排除 `dropped` |
| `fix/coverage-uses-own-clock`（PR #4） | 沉默判準改用每條實體自己的 `first_fetch_at`，不再拿整個語料庫的長度當尺 |
| `docs/backlog-refresh` | 這份清單本身；變異盤點層（`scripts/mutate.py` + `mutations.yaml` + 獨立工作流），並補掉它第一輪抓到的五個洞 |
| `fix/heat-claims-a-measurement`（PR #7） | `heat` 沒量到就寫 null 不編數字；新 blocker `unmeasured_heat`；`references/readiness-gate.md`；51 則遷移 + 回滾 |
| `fix/monitor-exit-codes-vs-main`（PR #8） | 死人開關的 exit code 走真子行程釘住；`FM_FROM_CONFIG` 白名單邊界改由行為守；`ingested_at` 黏性改成真的跑第二輪；併回 `main` 解衝突 |
| `fix/narrative-drops-the-fake-heat`（隨 PR #9 併入） | `narratives.yaml` 那兩句拿假 heat 當論據的話重寫；加上掃全檔（含 `thesis` / `lenses`，夜間鏈永遠不會重寫的兩段）的測試與拒收執法；M26–M28 三條說謊路徑 |
| `fix/gate-keys-unmarked`（PR #9） | 未接線清單從手寫改成掃 `gate.yaml` 全部 55 個 leaf key 機械列舉（`scripts/lib/gate_keys.py`）；掉出 `quality.weights` 與 `readiness.require_primary_evidence` 兩個從沒被列過的 key；A／B／C 三類分開；M29–M32 |
| `docs/backlog-tidy`（PR #10） | 這份清單的編號 P0–P10 改成不會變的名字；修掉 `selftest.py:794` 與 `references/readiness-gate.md:112` 兩處指著編號的死引用；補一條「原測試只比對 `path`，恆真」的空測試（`52752bd`） |

共同主題是**警報自己把自己關掉**：用一個比事實寬鬆的代理指標去代表事實。代理在
順利的日子跟事實重合，所以平常測不出來；它只在你最需要它準的那一天分岔。規格寫在
`references/health-alarms.md`。目前收集到的實例：

1. 用「目錄名」代理「那天真的有語料」
2. 用「隔離候選算出來了」代理「有人看得到它」
3. 用「語料庫有多長」代理「這條線被觀察多久」
4. 用「碼裡有沒有這句話」代理「跑起來會不會叫」（`references/health-alarms.md`「算對了不等於會叫」）
5. 用「測試有幾條」代理「壞掉會不會被抓到」（`references/mutation-inventory.md`）
6. 用「一份手工清單」代理「所有未接線的 key」（[`gate-未接線`](#gate-未接線)）
7. 用「入口已經修好」代理「站上沒有假話」（`fix/narrative-drops-the-fake-heat`：
   假 heat 的源頭修掉了，但已經寫成散文的兩句結論在 `lenses` 裡，而 `lenses` 是夜間鏈
   永遠不會重寫的欄位——堵住上游只擋得住新的謊）
8. 用「編號」代理「清單上的某一件事」（就是上面〈為什麼這裡沒有編號〉那一節）
9. 用「一張量過的現況表」代理「現況」（就是上面〈上一版這張表在合併的那一刻就過期了〉。
   最刁的一點：它是往**變好**的方向失準的，303→322 沒有人會覺得不對勁）

## 附：怎麼重新盤點這份清單

清單過期不會讓任何東西變紅，所以下次盤點請直接跑這些，**不要相信上面的數字**：

```bash
git fetch origin --prune                              # 先 fetch，不然下面全是舊的
git log --oneline -1 origin/main                      # 現況表的 commit
git branch -r --no-merged origin/main | grep -v HEAD  # 未併分支
git branch -r --merged origin/main | grep -v 'HEAD\|origin/main' | wc -l   # 可刪幾條
git merge-tree --write-tree origin/main <branch>      # 那條能不能乾淨併
python3 scripts/selftest.py | tail -1                 # 有幾條測試
python3 scripts/mutate.py                             # 有幾格守不住（幾分鐘）
python3 -c "import yaml;w=yaml.safe_load(open('_config/sources.yaml'))['coverage_watch']['must_watch'];print(len(w),sum(1 for x in w if x.get('pending')))"
for s in published review dropped; do printf "$s "; grep -l "^status: $s" Events/*.md | wc -l; done
grep -l stale_backfill Events/*.md | wc -l            # stale-backfill 幾則
grep -n 'heat' _config/narratives.yaml                # 站上還在說謊嗎
ls _corpus/                                           # 語料累積幾天
grep -n "cron:\|stale-days" .github/workflows/data-refresh.yml   # cron-收班 收了沒
# 零產出來源：每條來源每一班的 status，不是只看最後一班
python3 -c "
import json;from collections import Counter
runs=[json.loads(l) for l in open('_probe/source-runs.jsonl')]
for sid in ('src-mistral-news','src-media-theregister','src-kol-thezvi'):
    print(sid, Counter(s['status'] for r in runs for s in r['sources'] if s['id']==sid))"
```

`mutate.py` 那一行才是「測試守不守得住」的答案。`selftest | tail -1` 給的是**有幾條
測試**，那是兩件不同的事。

四個踩過的坑，複量的時候會再踩到：

- **`git branch -r --merged | grep -v main` 會少數**——`fix/monitor-exit-codes-vs-main`
  的名字裡就有 `main`。要 `grep -v 'HEAD\|origin/main'`。
- **`git log origin/main` 要在 `git fetch` 之後**，同一串命令裡順序寫反就會拿到舊的。
- **在分支上跑的 selftest 不描述 `main`**。要量 `main` 就開一個
  `git worktree add /tmp/ap-main origin/main`，跑完 `git worktree remove` 掉。
- **新容器要先 `pip install ruamel.yaml`**（CI 有裝，`data-refresh.yml` 第 52 行；
  乾淨的容器沒有）。少了它，`selftest.py` 不會說「缺套件」，而是死在一個看起來
  完全無關的 `FileNotFoundError: …/_probe/source-health.json`——因為 `_run_sh()`
  只回傳 `(returncode, stdout)`，子行程那句 `[fatal] --apply 需要 ruamel.yaml`
  寫在 stderr，被丟掉了。**紅的地方不是壞的地方**，2026-07-26 這次複量在這裡卡了
  十分鐘。
