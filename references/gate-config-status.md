# gate.yaml：哪些門檻真的在管事

> `_config/gate.yaml` 的註解說的是**打算**怎麼做，這份文件說的是**現在**怎麼做。
> 兩者不一致時以本檔為準，並且 selftest 有一條測試釘住這份清單（見最後一節）。

## 為什麼要有這份文件

紅線 8 是「對自己誠實：不把預留欄位、未被消費的配置講成已實現能力」。
`gate.yaml` 現在有 12 個 key **沒有任何一行程式碼讀它**（原本 13 個，
`monitor.stale_after_days` 已於 2026-07-26 接上）。它們不是空的、不是註解掉的，
每一個都寫著看起來很正常的數字，旁邊還有一段解釋它為什麼是那個數字的中文。

這比空著危險。空欄位沒有人會去調；一個寫著 `event_window_hours: 72` 的欄位，
會讓下一個人（很可能是三個月後的我們自己）把它改成 48，重跑一次，
看到聚類結果沒變，然後開始懷疑資料出了問題——而不是懷疑這個欄位是假的。

**未接線本身不是 bug**，其中好幾個是還沒做的功能的預留規格，留著有價值。
是「沒有標出來」才是 bug。所以這個 PR 不刪任何一個 key，只做兩件事：
在 gate.yaml 標記，並用測試釘住標記與現實一致。

## 兩種不同的「沒在管事」

分開講很重要，因為修法完全不同。

**A. 未接線**——沒有任何程式碼讀這個 key。改它不會有任何效果。
修法是去寫消費它的碼（或承認不做，但標記留著）。

**B. 接線了但條件走不到**——碼確實讀了，但那個 `if` 永遠不會成立。
改門檻依然沒有效果，可是原因完全不同，而且**調小門檻是錯的修法**。

## A. 未接線的 12 個 key

| key | 寫的是什麼 | 實際由什麼決定 |
|---|---|---|
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
| `evidence.translation_chain` 整塊 | 翻譯轉載不計入獨立性與 heat | 沒有消費者。這是媒體線的已知風險缺口——所以 `feat/media-line` 只收英文媒體。 |

### 已經從這張表畢業的

| key | 何時接上 | 消費者 |
|---|---|---|
| `monitor.stale_after_days` | 2026-07-26 | `pulse-monitor.py --write-health / --alert-stale`（規格見 `references/vault-pages.md`）。接線之前它連要寫的那個 `_dashboards/health.md` 都不存在。 |

留著這一列不是為了記功，是因為「本來未接線、後來接上了」是這份文件唯一
會發生的變化，把它記在原地才看得出這張表在縮短。

## B. 接線了但走不到：heat 那三個

`readiness.heat_threshold: 70` / `heat_min_independent_sources: 2` /
`heat_min_platform_breadth: 2` 確實被 `pulse-gate.py:96-136` 讀到，
組成 `unsupported_heat` 這條 blocker。但那個 `if` 的第一個條件是 `heat >= 70`，
而 **heat 目前的理論上限是 48**。

原因在 `pulse-cluster.py:141`：呼叫 `scoring.score_event(...)` 時 `metrics=[]`，
所以 `platforms` 與 `regions` 恆為 0。heat 公式裡這兩項佔 `7 + 6 = 13` 分，
再加上作者數／推文數兩項（沒有社群指標時也是 0），能拿到的只剩

```
_logscale(0,80)*30 + _logscale(0,300)*20 + min(independent,5)*8 + 0 + 0 + freshness*0.08
                                            ↑ 最多 40                    ↑ 最多 8
```

上限 48。selftest 有一條測試把這個 48 釘住。

**正確的修法是去真的收集社群指標**（讓 `metrics` 不再是空的），
不是把 `heat_threshold` 從 70 調到 45。後者會讓 `unsupported_heat` 開始有反應，
但那個反應是假的——紅線 4 明講「禁止把手工分數包裝成已測量熱度」，
把門檻調到手工分數搆得到的高度，是同一件事換個方向做。

在社群指標接上之前，`unsupported_heat` 這條防線的正確描述是
**「已寫好，尚未生效」**，不是「已生效」。

## 這份清單怎麼不腐爛

`scripts/selftest.py` 有兩條測試：

1. 上表 A 欄的每個 key 名，在 `scripts/**.py` 裡都必須**搜不到**。
   哪天有人真的去接線了，這條會紅——提醒他回來把 gate.yaml 的
   `⚠ 未接線` 標記與這份文件一起改掉。
2. `gate.yaml` 裡每個 A 欄的 key 附近都必須帶著 `⚠ 未接線` 字樣。
   刪掉標記會紅。

反過來的方向（有人新增一個沒接線的 key 而忘了標）測不到，
這一點誠實寫在這裡：那需要一個能把 YAML key 對應到消費點的靜態分析，
現在沒有。目前擋的是「標記與現實不一致」，不是「所有未接線都被標記」。
