# AI-Pulse：應做而未做

這份清單只寫「**已知有問題、但還沒動手**」的事。修掉的移到最後的〈附：已經修掉的〉；
**修好了但還沒併進 `main` 的，算沒修**——這條規矩不變，只是現在不必靠人記得：
現況數字由每班的鏈自己量（見下一節），而那條鏈跑在 `main` 上。

每一條有一個**不會變的名字**（`cron-收班`、`gate-未接線`…），沒有編號。
理由寫在下面〈為什麼這裡沒有編號〉——不是排版偏好，是量到的一個 bug。

## 現況

**現況數字不在這份檔案裡，在 [`_dashboards/backlog-status.md`](_dashboards/backlog-status.md)，
每班重新生成。**

這裡以前有一張手寫的表：`main` 的 commit、selftest 條數、變異數、可刪分支數、
Events 數、語料天數。它在 2026-07-27 那一版**寫下之後 3 小時就過期了**——
四條分支被合併，六格同時作廢。

那是同一種病的第 9 個實例（見〈已經修掉的〉底下的清單）：**用一張量過的表代理現況**。
更值得記的是**上一版的修法失敗了**：當時的做法是把量測時間寫進標題、在最後一節
請下一個人複量。那是一個**靠人記得**的機制，而這份清單存在的理由就是不要有
那種機制。三小時就證明它不夠。

所以照這個 repo 一貫的分法辦——**量測是機械的，判斷是人寫的**（跟
`gate.yaml` 的標記涵蓋檢查同一句話）：

- **數字**歸 `scripts/pulse-backlog-status.py`，每班跟著夜間鏈重生成，
  規格在 `references/vault-pages.md`。
- **判斷**留在這裡：哪一條重要、壞了會不會變紅、現在有沒有在騙人。
  **這份檔案不再有任何一個會過期的數字。**

兩格刻意不搬過去也不留在這裡：**selftest 條數**與**變異結果**。它們不是每班
量得到的事實，放進那一頁只會變成一個「上次不知道什麼時候量的」數字。要它們就
自己跑，指令在〈附：怎麼重新盤點這份清單〉。

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
| [`跨語言重複-event`](#跨語言重複-event) | 沒有版本號的同一件事，中英文會變成兩則 Event | 不會 | — |
| [`榜單描述沒有中文`](#榜單描述沒有中文) | GitHub 動能榜 225 條全是英文原文，中文從沒翻過一次 | 不會（已印在 health.md） | 否 |
| [`候選詞被普通英文洗版`](#候選詞被普通英文洗版) | 字典補漏清單大半是 June / Here / One 這種詞 | 不會 | 否（沒宣稱過它們是實體） |
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
- ~~**`clustering.unknown_entity`**~~ **2026-07-27 接上**
  （`fix/dictionary-gaps-report-to-nowhere`）：`report_to` 指的那一頁現在真的會
  被產生，兩個晉升門檻也搬進 `gate.yaml` 給兩個消費者共用。
  剩下 `action` 與 `key_from_title_hash` 標成 **C 類（刻意不接）**，理由寫在
  設定檔那兩行旁邊。
- **`evidence.need_independent_tier2: 2`** 描述的「兩個獨立 Tier-2 也可以放行」這條
  替代路徑**不存在**；實際只有 `missing_primary_evidence` 一條規則在擋。
- ~~**`evidence.translation_chain`**~~ **2026-07-27 接上**
  （`fix/translation-chain-counts-a-rewrite`），詳見〈已經修掉的〉。四個 leaf
  全部有消費者，各自有一條變異證明它真的被讀。**中文媒體的那道前置門開了。**
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

**在這個容器裡查不出來的原因要講清楚**：proxy 擋外部連線（403），沒辦法在本地
抓那張 sitemap 驗證。要查只能在 CI 裡查。

**診斷輸出已經做了**（`fix/sitemap-zero-yield-is-not-silence`，規格
`references/health-alarms.md`〈零產出不是沉默〉）：`_probe/<日>/report.md` 多一區
〈零產出診斷〉，把「200 / 0 筆」拆成四個 code——`source_empty`（站方那邊）、
`hints_matched_nothing` / `prefix_filtered_all`（我們這邊）、
`sub_sitemap_unreachable`（中間那一跳），並印出中途數字與過濾前的樣本 URL。

**2026-07-27 02:38Z 首班的判決出來了**：

```
| src-mistral-news | hints_matched_nothing | 我們 |
  index 有 1 張子 sitemap，hints ['news','blog'] 一張都沒命中
```

**是我們的設定對不上，不是站上沒東西。** 那份 sitemap-index 只有一張子 sitemap，
而它的網址不含 `news` 也不含 `blog`。剩下的動作只有一個：**下一班會把那張的網址
印出來**（`fix/hints-miss-without-showing-candidates` 補的——首班判對了卻沒印候選，
下一步還是查不下去），拿到網址就把 `sitemap_hints` 或 `url_prefix` 改對。
**不要用猜的改設定**：猜對了也沒有證據，猜錯了下一個人要重查一次。

以下是首班之前寫的：

**所以這條剩下的不是動手，是等一班。** 那條分支併進 `main` 之後跑過一班，去讀
`_probe/<日>/report.md` 的〈零產出診斷〉，`src-mistral-news` 屬於哪一種當場就有
答案。**併之前先跑，等於什麼都不會發生**——這個 repo 已經量過兩次了。

還沒接的那一半也要記著：那個 code 目前只渲染給人看，**沒有寫進
`_probe/source-runs.jsonl`，也沒有任何警報吃它**。`prefix_filtered_all` 連續三十班
CI 一樣是綠的。不順手接上去是刻意的——接之前得先想清楚門檻與消費者，否則就是再
造一個 [`value-沒人用`](#value-沒人用)。

---

## `跨語言重複-event`

**這是 `translation_chain` 接上之後才看得清楚的那一半。**

轉載鏈防的是「同一則 Event 裡有一篇翻譯被算成第二個聲音」。但那件事要先發生，
兩篇得**落進同一則 Event**——而 `belongs_to_event()` 只有兩條路：

| 路 | 跨語言行不行 |
|---|---|
| 同 `fingerprint` + 同 `facet` + 時間窗 | **行**。`event_fingerprint()` 帶 CJK 對照（通义→qwen…），`event_facet()` 的正則也收中文（发布 / 融资 / 事故…） |
| 標題相似度 ≥ 門檻（96 小時窗） | **不行**。中英文標題的 token 交集趨近於零 |

也就是說：**認得出具名模型版本的新聞，轉載鏈罩得住；認不出的（融資、事故、
人事、政策——大部分新聞）會直接變成兩則各自獨立的 Event。**

排在這裡而不是更前面，是因為它今天**不會發生**：沒有任何中文來源。
它是「中文媒體進來的那一天會立刻出現」的東西，所以要在加來源之前決定怎麼辦，
不是加完之後才發現庫裡每件事都有兩則。

修法的方向（還沒動手，也還沒寫規格）：讓 `belongs_to_event()` 在標題相似度
之外也看**實體集合**——`lib/entities.entity_ids()` 已經是現成的，轉載鏈就是
靠它跨語言的。但那會動到聚類門檻本身，屬於紅線 9 要先改文件的那一類，
而且改壞的方向很惡劣：門檻放太鬆會把不相干的事件併成一則，**併錯了不會有
任何東西變紅**，只會有一則標題與內容對不上的 Event 靜靜躺在庫裡。

---

## `候選詞被普通英文洗版`

`_dashboards/dictionary-gaps.md` 第一次跑出來，達標清單長這樣：

```
Industry 16 / Research 16 / LLMs 16 / Union 10 / LLM 10 / June 9 / Here 9
/ Energy 9 / July 8 / Building 7 / … / Gemma 5 / San Francisco 5 / …
```

`Gemma` 是真的該收的產品線，`LLM` / `LLMs` 是真的該收的技術詞。其餘大半是
**一般英文大寫詞**：`June`、`July`、`Here`、`One`、`Learn`、`Building`、
`Understanding`。

病灶在收割層不在這一頁：`pulse-probe.CAND_LATIN` 抓的是「大寫開頭的拉丁詞」，
而 `CAND_STOP` 只有二十來個字。英文標題的字首大寫、月份、地名、動名詞全都通得過。

**這條之所以現在才出現在清單上，正是那一頁的價值**：在此之前這些詞每班各自算
各自的，沒有任何地方把它們加起來，所以「雜訊佔了大半」這件事量不到。

修法方向（還沒動手）：`CAND_STOP` 要從「手寫二十個字」變成有判準的東西——
月份與星期是封閉集合可以整批排除；常見英文詞需要一份停用詞表，而那份表一旦手寫
就會是下一個「手寫清單」（第 6 個實例）。**先想清楚判準再動手**，否則只是把雜訊
換一批。

---

## `榜單描述沒有中文`

`_github/desc-zh.json` **在整個 git 歷史裡從來沒有出現過**
（`git log --all -- _github/desc-zh.json` 是空的）。GitHub 動能榜上 225 條 repo
的描述**全部是英文原文**，而那個榜是給中文讀者看的。

病灶在潤稿端的 C2 段第 9 步：它要先跑 `pulse-github.py` 重建榜單，而潤稿端是
Cowork 容器、**沒有 `GITHUB_TOKEN`**，未認證額度很緊。runbook 對這一步的規定是
「這步失敗就整個 C2 段跳過」——跳過是對的，翻譯不該擋住抓取鏈。

**2026-07-27 已經修掉的是「跳過不留痕跡」那一半**
（`fix/c2-skips-in-silence`）：現在 `_dashboards/health.md` 每班印一行，而且
分得出「量不到 / 從來沒翻過 / 有過然後停了」。在此之前，**「跳過了」跟「沒有東西
要翻」印起來一模一樣**。

**2026-07-27 也修掉了第二半**（`feat/actions-prepares-the-desc-worklist`，走路線 2）：
待譯清單改由 **Actions 那班**準備並進版控——它有 `GITHUB_TOKEN`、每班都跑得到榜單。
潤稿端 clone 下來就有清單，C2 的第 9 步（自己重建榜單）整個拿掉，**那是整段唯一
需要外部服務的地方**。順手補掉兩層「量不到寫成 0」：抓取全失敗留下的佔位榜單現在
標 `measured: false`，prep 看到就不覆寫既有清單並回離開碼 2。

**所以現在缺的只剩「真的有人去翻」那一步**——也就是潤稿排程照新版 runbook 跑一次
C2。下一晚 19:00Z 那班就會走到，屆時看 `_dashboards/health.md` 的〈GitHub 動能榜的
中文描述〉那一行從「從來沒有成功翻過一次」變成「N/M 條」，就是成了。

沒成的話，兩條路：

原本評估的兩條路（保留當紀錄）：

1. **把 `GITHUB_TOKEN` 傳進潤稿排程** —— 如果那個排程環境給得出 token，C2 直接
   就活了，一行碼都不用改。要先確認。
2. **讓 Actions 那班準備好 worklist** —— Actions 有 token、每班都跑得到榜單。
   由它跑 `pulse-github-desc-prep.py` 把待譯清單寫進版控，潤稿端就不必自己重建
   榜單，第 9 步整個可以拿掉。這條比較穩，但要改 runbook 與 workflow。

先確認第 1 條再說——它可能是零成本的。

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
| `fix/sitemap-zero-yield-is-not-silence` | 「200 / 0 筆」拆成四個 code：站方那邊沒東西 vs 我們這邊接不上。規格 `references/health-alarms.md`〈零產出不是沉默〉 |
| `fix/evidence-forgets-what-it-saw` | 證據記錄留下 `title` 與 `published`；reload 不再拿 url 頂替 title（頂替之後，拿標題比相似度會**照樣算得出一個數字**，只是算的是網址）。新增 `references/evidence-tiers.md`——那個檔名被指了兩次而一直不存在 |
| `fix/translation-chain-counts-a-rewrite` | `evidence.translation_chain` 四個 leaf 全部接上：跨語言 + 實體集合 Jaccard ≥ 0.80 + 48h 窗 → 標 `suspected_repost`、不計入獨立性。實體比對層抽到 `lib/entities.py`（單一真相源）。M43–M47 各守一個設定值真的被讀 |
| `feat/event-titles-in-chinese` | Event 標題 51/51 全是英文原文——六層 prose 是中文、站台框架是中文，只有讀者唯一會看到的那一行不是。`title_zh` + `title_zh_src` 進版控，原文變了譯文自動失效退回原文；驗章跟榜單描述共用 `lib/zhtext.py` |
| `fix/c2-skips-in-silence` | 潤稿端 C2 段（榜單描述中文化）失敗時整段跳過，**而跳過跟「沒東西要翻」印起來一樣**——`desc-zh.json` 從沒進過版控也沒人發現。觀測改由一定會跑的 Actions 那班量，分得出「量不到 / 從來沒翻過 / 有過然後停了」 |
| `fix/dictionary-gaps-report-to-nowhere` | `clustering.unknown_entity.report_to` 指的那一頁以前不存在，現在每班產生；晉升門檻搬進 `gate.yaml`，`_probe` 當班區塊與累積頁讀同一份 |
| `fix/backlog-status-is-hand-written` | 現況表從手寫改成每班重生成（`_dashboards/backlog-status.md`）。**這是第 9 條實例的第二次修法**——第一次（把量測時間寫進標題、請下一個人複量）三小時就失效了 |

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
9. 用「一張量過的現況表」代理「現況」。最刁的一點：它是往**變好**的方向失準的
   （303→322），沒有人會覺得不對勁。**這一條的第一次修法也失敗了**——把量測
   時間寫進標題、請下一個人複量，是一個靠人記得的機制，三小時就過期了。
   真正的修法是把數字整個搬出手寫檔案（`_dashboards/backlog-status.md`，每班
   重生成），**手寫檔案裡一個數字都不留**。

## 附：怎麼重新盤點這份清單

**大部分的數字已經不用你自己跑了**：`_dashboards/backlog-status.md` 每班重生成，
Events、語料、來源、`coverage_watch`、`gate.yaml` 接線數、最後一班 probe 都在那裡。
下面剩下的是**那一頁刻意不放的**——它們不是每班量得到的事實：

```bash
python3 scripts/selftest.py | tail -1                 # 有幾條測試
python3 scripts/mutate.py                             # 有幾格守不住（幾分鐘）
git fetch origin --prune                              # 先 fetch，不然下面全是舊的
git log --oneline -1 origin/main
git branch -r --no-merged origin/main | grep -v HEAD  # 未併分支
git branch -r --merged origin/main | grep -v 'HEAD\|origin/main' | wc -l   # 可刪幾條
git merge-tree --write-tree origin/main <branch>      # 那條能不能乾淨併
grep -n 'heat' _config/narratives.yaml                # 站上還在說謊嗎
grep -n "cron:\|stale-days" .github/workflows/data-refresh.yml   # cron-收班 收了沒
# 零產出來源：每條來源每一班的 status，不是只看最後一班
#（那一頁只印最後一班的；要看趨勢還是得自己跑）
python3 -c "
import json;from collections import Counter
runs=[json.loads(l) for l in open('_probe/source-runs.jsonl')]
for sid in ('src-mistral-news','src-media-theregister','src-kol-thezvi'):
    print(sid, Counter(s['status'] for r in runs for s in r['sources'] if s['id']==sid))"
```

要在本機看那一頁現在會長什麼樣（不寫檔）：

```bash
VAULT_DIR=$PWD python3 scripts/pulse-backlog-status.py --dry-run
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
