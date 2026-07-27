# gate.yaml：哪些門檻真的在管事

> `_config/gate.yaml` 的註解說的是**打算**怎麼做，這份文件說的是**現在**怎麼做。
> 兩者不一致時以本檔為準，並且 selftest 有一條測試釘住這份清單（見最後一節）。

## 為什麼要有這份文件

紅線 8 是「對自己誠實：不把預留欄位、未被消費的配置講成已實現能力」。
`gate.yaml` 有一批 key **沒有任何一行程式碼讀它**。它們不是空的、不是註解掉的，
每一個都寫著看起來很正常的數字，旁邊還有一段解釋它為什麼是那個數字的中文。

> **2026-07-26 傍晚更新——這份文件自己犯了它在講的病。**
>
> 上一版這裡寫「現在有 12 個 key」，而那個 12 是**手工數的**；`selftest.py` 也是
> 拿一份手寫的 12 個名字去比對。手工清單只擋得住一個方向：「標了未接線、後來
> 卻接上了」。反方向——**有人新增一個沒接線的 key 而忘了標**——上一版誠實寫了
> 「測不到」，然後就沒有再管它。誠實地記下一個洞不會把洞補起來。
>
> 把 55 個 leaf key 全部機械列舉出來比對，當場掉出**兩個從來沒進過那張清單的**：
> `readiness.require_primary_evidence`，以及 `quality.weights` 整塊——五個數字、
> 總和剛好 100、寫著「五維上限」，**是整個檔案裡最像可以調的東西**。
>
> 也就是說那份「未接線清單」自己就是一份不完整的清單，而它不完整這件事
> 不會讓任何東西變紅。現在改成：**列舉是機械的，標記是人寫的，測試比對兩者**
> （見最後一節）。

這比空著危險。空欄位沒有人會去調；一個寫著 `event_window_hours: 72` 的欄位，
會讓下一個人（很可能是三個月後的我們自己）把它改成 48，重跑一次，
看到聚類結果沒變，然後開始懷疑資料出了問題——而不是懷疑這個欄位是假的。

**未接線本身不是 bug**，其中好幾個是還沒做的功能的預留規格，留著有價值。
是「沒有標出來」才是 bug。所以這個 PR 不刪任何一個 key，只做兩件事：
在 gate.yaml 標記，並用測試釘住標記與現實一致。

## 三種不同的「沒在管事」

分開講很重要，因為修法完全不同。

**A. 未接線**——沒有任何程式碼讀這個 key。改它不會有任何效果。
修法是去寫消費它的碼（或承認不做，但標記留著）。

**B. 接線了但條件走不到**——碼確實讀了，但那個 `if` 永遠不會成立。
改門檻依然沒有效果，可是原因完全不同，而且**調小門檻是錯的修法**。

**C. 刻意不接**——形式上跟 A 一樣（沒有消費者），但它**不該有消費者**。
目前只有一個：`readiness.require_primary_evidence`。分開列是因為 A 的待辦是
「去接上」，C 的待辦是「不要接上，而且要寫清楚為什麼」——把 C 混進 A，
下一個人會很熱心地幫我們接上，然後我們就有了一個可以把紅線關掉的開關。

## A. 未接線的 key

| key | 寫的是什麼 | 實際由什麼決定 |
|---|---|---|
| `quality.weights` 整塊（5 個） | 「五維上限（總和 100）」：authority 25、richness 25、freshness 20、originality 15、completeness 15 | **全部硬寫在 `lib/quality.py` 的五支函式裡**（`min(25, …)` / `min(15, …)` / `_freshness()` 的階梯）。沒有任何一行碼讀 `weights`。`quality.py` 第 7 行的 docstring 還寫著「各自上限見 gate.yaml.quality.weights」——指向一個沒有人讀的地方。這是 2026-07-26 傍晚機械列舉才掉出來的：它從來沒進過未接線清單，而它是這個檔裡**最像旋鈕的東西**。 |
| `quality.freshness_full_hours: 24` | 「< 此小時給滿分」 | `lib/quality.py:_freshness()` 的硬寫階梯：≤1h 給 20（滿分），≤6h 給 18，≤24h 給 **15**。也就是 24 小時內拿到的**不是**滿分，設定檔這句話是錯的。 |
| `quality.freshness_zero_days: 30` | 「> 此天數給 0」 | 同一支階梯：>720h（正好 30 天）給 **1**，不是 0。永遠不會歸零。 |
| `dedup.minhash_jaccard: 0.80` | 標題近似重複門檻 | `lib/cluster.py:title_similarity()` 用的是 **token Jaccard**，不是 MinHash；門檻由 `cluster_candidate()` 的參數傳入。 |
| `dedup.ngram: 4` | char n-gram 大小 | 沒有任何地方做 char n-gram。標題是按 token 切的。 |
| `dedup.event_window_hours: 72` | 同實體 ±此窗口併為一 Event | `lib/cluster.py:233-242` 硬寫三個窗口：一般 **96h**、`incident` 類 **7 天**、其餘同 facet **21 天**。沒有一個是 72。 |
| `clustering.key_eligibility` 整塊 | 哪些 term_type 能單獨當聚類主鍵 | 沒有消費者。`technology` 的 `co_occurrence_only` 限制目前不存在，技術詞可以單獨當主鍵。 |
| `clustering.version_derivation` 整塊 | 版本實體自動衍生 | 沒有消費者。`claude@opus-4.8` 這種衍生實體不會產生。 |
| `clustering.unknown_entity` 整塊 | 未知實體保留與補漏清單 | 沒有消費者。`report_to` 指的 `_dashboards/dictionary-gaps.md` **不存在**，也沒有任何碼會產生它。 |
| `clustering.cross_language` 整塊 | 跨語言限制聲明 | 沒有消費者。這塊本來就是聲明而非開關，但仍需標記，否則讀者會以為 `supported: false` 是某處讀到後關掉了什麼。 |
| `evidence.need_tier1_primary: 1` | 發布需 1 個 Tier-1 primary | 真正在擋的是 `pulse-gate.py` 的 `missing_primary_evidence`（`primary_evidence` 欄位為 0 就擋），而那個欄位由 `pulse-cluster.rescore()` 用 `tier == 1 and role != "aggregator"` 算出來。數字 1 是巧合地一致，不是被讀進去的。 |
| `evidence.need_independent_tier2: 2` | 或 2 個獨立 Tier-2 | 沒有消費者。目前**沒有**「兩個獨立 Tier-2 也可以」這條路：primary 缺席就是擋，補幾個獨立來源都沒用。 |

### 已經從這張表畢業的

| key | 何時接上 | 消費者 |
|---|---|---|
| `monitor.stale_after_days` | 2026-07-26 | `pulse-monitor.py --write-health / --alert-stale`（規格見 `references/vault-pages.md`）。接線之前它連要寫的那個 `_dashboards/health.md` 都不存在。 |
| `evidence.translation_chain` 整塊（四個 leaf 全部） | 2026-07-27 | `pulse-cluster.py`（讀設定、標記、扣獨立性）+ `lib/cluster.py:suspected_reposts()`。規格 `references/evidence-tiers.md`。四個值各有一條變異證明它真的被讀（M43–M47）——接線之後仍然「改了沒效果」的話，等於把假旋鈕搬了個家。 |

留著這一列不是為了記功，是因為「本來未接線、後來接上了」是這份文件唯一
會發生的變化，把它記在原地才看得出這張表在縮短。

## C. 刻意不接：`readiness.require_primary_evidence`

`gate.yaml` 裡寫著 `require_primary_evidence: true`。它**沒有任何消費者**——
整個 repo 只有兩處註解提到這個名字（`lib/sources.py:28`、`sources.yaml` 的頭幾行），
沒有一行碼讀它。真正在擋的是 `pulse-gate.py` 裡**無條件**的
`missing_primary_evidence`：`primary_evidence` 為 0 就擋，沒有 `if` 包著它。

同樣是 2026-07-26 傍晚機械列舉掉出來的。它跟 A 欄那些不一樣的地方在於：
**它不該被接上。**

把它接上長這樣：`if r.get("require_primary_evidence", True): blockers.append(...)`。
一行，看起來很整齊，而且會讓這個 key 從假的變成真的。但那一行做出來的東西是
**一個能把紅線 2 的唯一執法點關掉的開關**——而且是一個寫在設定檔裡、
改它不需要碰任何程式碼、不會有人 review 的開關。

一個假開關的傷害是：有人改了它，發現沒效果，開始不信任這個檔案。
一個真開關的傷害是：有人改了它，**很有效果**，然後整個 vault 開始發布沒有一手
證據的東西，而 selftest 全綠——因為每一條測試都是拿預設值跑的。
第二種比第一種嚴重得多。

所以這個 key 標成 `⚠ 未接線（刻意）`，留著當政策聲明，不做成開關。
要放寬紅線 2 的門檻，該走的路是改 `references/evidence-tiers.md` 再改碼（紅線 9），
不是在 YAML 裡翻一個布林值。

## B. 接線了但走不到：heat 那三個

> 2026-07-26 改寫。完整規格與決策過程在 `references/readiness-gate.md`；
> 這一節只留結論與現況。

`readiness.heat_threshold: 70` / `heat_min_independent_sources: 2` /
`heat_min_platform_breadth: 2` 確實被 `pulse-gate.py` 讀到，組成
`unsupported_heat`。它走不到——但**走不到只是症狀，不是病**。

病是：`heat` 這個欄位名稱說的是傳播熱度，實際量到的是「獨立來源數 + 新鮮度」。
公式六項裡有四項要社群訊號（作者 30、推文 20、平台 7、地域 6，合計 63 分），
這四項在全部 51 個 Event 上都是 0，而且**不是資料還沒進來**：
`pulse-cluster.py:144` 呼叫 `scoring.score_event(...)` 時第四個參數寫死
`metrics=[]`。那條線從來沒有接過——不是輸入端沒東西，是連接線沒有接。

於是 heat 印出 8–32 的數字，看起來像量過的。下游真的把它當量過的用了：
`_config/narratives.yaml` 裡有兩句 LLM 依這個數字寫成的話
（「四則皆單源、heat 偏低（8–14），還沒跨來源共振」）。一個沒接線的欄位
變成了敘述層的論據——紅線 2 與紅線 8 同時被繞過，**因為那個數字看起來像量出來的**。
（那兩句 2026-07-26 已改掉並補上擋線，見 `references/narrative-layer.md`。）

### 現在的狀態

一項傳播訊號都沒量到時 `scoring.score_event()` 回 `heat: None`，
不是一個低分（紅線 8：量不到就寫量不到）。**不印 0**：0 會被讀成
「量過了，很冷」，那是更難察覺的一種謊。

`score_factors.propagationSignals` 記下四項裡有幾項非零，把「什麼都沒量到」
寫成磁碟上的事實，而不是要下游從四個 0 自己推論。
新的 `unmeasured_heat` blocker 擋下「有 heat 數字但 `propagationSignals` 為 0」的
Event——包含未來有人把無條件計算加回來的那一天。

三個門檻**刻意不動**。兩條被否決的修法與理由：

| 修法 | 為什麼不做 |
|---|---|
| 把 `heat_threshold` 降到實際值域裡（70 → 45） | `unsupported_heat` 會開始有反應，但那個反應是假的：它會對「單一來源 + 剛發布」發火，那跟傳播沒有關係。紅線 4 明講禁止把手工分數包裝成已測量熱度；把門檻降到手工分數搆得到的高度是同一件事換個方向做。 |
| 重新分配那 63 分的權重給還活著的兩項 | 值域補滿之後，一個 0–100 的「熱度」看起來**比現在的 8–32 更像**真的量出來的。把謊講得更順不是修好。 |

所以 `unsupported_heat` 的正確描述是 **「休眠，等社群線（M3）」**，
不是「已生效」，也不是「廢設定」。`selftest.py` 釘住兩個方向：
`metrics=[]` 時 heat 是 `None`；四項餵滿時 heat 跨得過 70。
第二條哪天紅了，就表示這個門檻該重談，而不是繼續留著假裝有守。

## 這份清單怎麼不腐爛

判準在 `scripts/lib/gate_keys.py`，`selftest.py` 是執法點。核心是一句話：

> **列舉是機械的，標記是人寫的，測試比對兩者。**

上一版不是這樣。上一版的列舉也是人寫的（selftest 裡一份 12 個名字的
`_UNWIRED` 清單），於是「清單漏了誰」這件事沒有任何人在管——`quality.weights`
在裡面躺了不知道多久。**一份需要人記得去更新的清單，跟沒有清單的差別只是心裡
比較踏實**（同一句話在 `references/mutation-inventory.md` 也出現過，那次得病的
是變異清單）。

### 規則

`gate.yaml` 的**每一個** leaf key，都必須被下列兩種標記之一涵蓋——標在自己那一行，
或標在任何一層祖先上（整塊標一次比每個 key 重複標好讀）：

| 標記 | 意思 | 測試驗什麼 |
|---|---|---|
| `⚠ …未接線` | A 或 C 類：沒有消費者 | 那個 key 名**不准**以字串常值出現在 `scripts/**.py` |
| `消費者：<路徑>` | 已接線 | 指名的檔案要存在，而且裡面搜得到那個 key 名的字串常值 |

兩個標記都沒有 → **紅**。這就是上一版缺的那個方向：新增一個 key 而不說它接了
沒有，現在是 CI 失敗，不是一個沒有人會發現的省略。

比對用的是**帶引號的字串常值**（`"key_name"` / `'key_name'`），不是純子字串。
差別是實際踩到的：`require_primary_evidence` 這個名字出現在 `lib/sources.py`
的一句註解裡，純子字串比對會判它「有消費者」——**註解不是消費者**。

### 這條檢查不保證什麼

- **不保證標成已接線的真的被讀。** 它驗的是「指名的檔案裡有這個名字的字串常值」，
  不是「那一行真的影響行為」。一個 `x = cfg.get("discard_below")` 之後再也沒用到
  的變數會過關。要驗到那一層得做資料流分析，這裡沒有。
- **不保證標成未接線的每一個子 key 都沒被讀。** 驗證發生在**被標記的那一層**：
  `clustering.key_eligibility` 整塊標未接線，驗的是 `key_eligibility` 這個名字。
  它底下的 `company` / `product` / `policy` 這種通用字在碼裡到處都是，逐個驗會
  一直誤紅——而**一條會誤傷的檢查，會被下一個人用改寫繞過去，然後變成一顆永遠
  綠的燈**。寧可少驗一層，不要驗到會被關掉。
- **不保證 `gate.yaml` 以外的設定檔。** `sources.yaml`、`entities.yaml` 沒有同樣
  的檢查。它們有沒有同一個病沒有量過——**沒量過就是沒量過**，不寫在這裡當成
  「應該還好」。
