---
type: "health"
generated_day: "2026-08-26"
status: "green"
last_success: "2026-08-26"
probe_lag_days: 0
last_run_day: "2026-08-26"
run_lag_days: 0
stale_after_days: 2
sources_runnable: 28
items_observed: 2173
events_total: 190
events_published: 157
---

# 健康監看

> 由 `pulse-monitor.py --write-health` 每班自動產生（零 LLM）。**手動編輯會在下一班被覆蓋。**

> 這頁自己就是死人開關：鏈沒跑就沒人重寫它，`generated_day` 會停在 2026-08-26 不動。所以先看那個日期是不是今天，再看下面的燈。

> [!success] 綠燈：資料新鮮度在門檻內。

## 四態（全系統）

| 層 | 數字 | 這一格不對勁代表什麼 |
|---|---|---|
| 收錄 | 28 條可跑來源 | 設定檔現在有幾條會被抓 |
| 已觀測 | 累計 2173 筆，來自 25 條來源 | 這裡是**歷來**累計，含現在已停用的來源，所以不能直接跟上一格相減。本窗口誰零產出看下面「覆蓋範圍」那一節 |
| 有效產出 | 190 則事件 | 抓到了但沒聚成事件＝聚類沒認出來 |
| 已發布 | 157 則 | 卡在門禁是設計，不是故障 |

## 鏈的兩條時間軸

| | 最後一次 | 距今 | 這條停了代表什麼 |
|---|---|---|---|
| 有跑班（`_probe/`） | 2026-08-26 | 0 天 | 排程死了 |
| 有抓到東西（`_corpus/`） | 2026-08-26 | 0 天 | 鏈在跑但瞎了（來源全壞、或全站沒更新） |

「靜默死掉」與「靜默瞎掉」是兩種病，所以兩條軸分開印。2026-07-24 漏抓 Claude Opus 5 的那晚，上面那條是綠的。

## 佇列

- 已上線 **157**／review **31**（待處理 16、設計上擋著 15）／人工判定不追 **2**
- 未 enrich **4** 則，最久放了 **0** 天
- 待處理卡最久 **27** 天（天數＝**進庫**多久，不是新聞發布多久）

| blocker | 則數 |
|---|---|
| `stale_backfill` | 11 |
| `thin_research_analysis` | 10 |
| `thin_fact` | 5 |
| `thin_by_policy` | 4 |
| `placeholder_content` | 4 |
| `missing_category` | 4 |
| `missing_track` | 4 |
| `generic_entity` | 2 |

## 覆蓋範圍

近 30 天（實有語料 31 天）。「沉默過久」是拿**每條實體自己的觀察期**判的（底下來源最早開始被觀察那天起算），不是拿語料庫長度——見 `references/health-alarms.md`。

| 必盯實體 | 來源 | 看見 | 事件 | 上線 | 最後看見 |
|---|---|---|---|---|---|
| OpenAI | 2 | 1161 | 51 | 48 | 0d 前 |
| Anthropic | 1 | 365 | 12 | 10 | 0d 前 |
| Google DeepMind | 1 | 178 | 6 | 5 | 0d 前 |
| Google | 1 | 525 | 6 | 5 | 0d 前 |
| Meta | 1 | 210 | 1 | 1 | 0d 前 |
| Microsoft | 1 | 158 | 2 | 2 | 0d 前 |
| NVIDIA | 1 | 430 | 25 | 24 | 0d 前 |
| Hugging Face | 1 | 171 | 8 | 3 | 0d 前 |
| xAI | 1 | 20 | 7 | 6 | 13d 前 |
| Mistral AI | 1 | 2 | 0 | 0 | 16d 前 |
| Alibaba | 1 | 11 | 0 | 0 | 2d 前 |
| DeepSeek | 0 | 259 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| Safe Superintelligence | 0 | 2 | 0 | 0 | 29d 前 ○ 已知未覆蓋（不觸警） |
| Thinking Machines Lab | 0 | 0 | 0 | 0 | **從未** ○ 已知未覆蓋（不觸警） |
| Cohere | 0 | 27 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| Perplexity | 0 | 9 | 0 | 0 | 7d 前 ○ 已知未覆蓋（不觸警） |
| Anysphere (Cursor) | 0 | 0 | 0 | 0 | **從未** ○ 已知未覆蓋（不觸警） |
| Cognition | 0 | 7 | 0 | 0 | 5d 前 ○ 已知未覆蓋（不觸警） |
| Scale AI | 0 | 257 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| Z.ai | 0 | 7 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| Moonshot AI | 0 | 4 | 1 | 0 | 23d 前 ○ 已知未覆蓋（不觸警） |
| MiniMax | 0 | 60 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| ByteDance | 0 | 8 | 0 | 0 | 9d 前 ○ 已知未覆蓋（不觸警） |
| Baidu | 0 | 0 | 0 | 0 | **從未** ○ 已知未覆蓋（不觸警） |
| Tencent | 0 | 0 | 0 | 0 | **從未** ○ 已知未覆蓋（不觸警） |
| AMD | 1 | 39 | 0 | 0 | 0d 前 |
| TSMC | 0 | 0 | 0 | 0 | **從未** ○ 已知未覆蓋（不觸警） |
| Broadcom | 0 | 4 | 0 | 0 | 27d 前 ○ 已知未覆蓋（不觸警） |
| Groq | 0 | 5 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| Cerebras | 0 | 17 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |
| CoreWeave | 0 | 11 | 0 | 0 | 16d 前 ○ 已知未覆蓋（不觸警） |
| AWS | 0 | 57 | 0 | 0 | 0d 前 ○ 已知未覆蓋（不觸警） |

- 可跑來源 28 條，本窗口零產出 6 條：`src-amd-ir`、`src-gh-openai-codex`、`src-kol-thezvi`、`src-media-theregister`、`src-mistral-news`、`src-qwen-blog`

## 來源層

- 機器自動降級中（連續成功即自己回來）：`src-gh-openai-codex`
- **隔離候選（等人看，機器不會自動停用）**：`src-gh-openai-codex`

逐條來源的四態見 `Sources/`。

## GitHub 動能榜的中文描述

- 榜單中文描述：37/38 條

這一格不判紅燈：第一天本來就是 0 條，一個天天紅的看板跟一個
永遠綠的一樣沒有資訊。**要判紅的是「有過然後停了」**，那個天數就在上面。

## 半夜潤稿那條鏈

- 潤稿鏈：最後一次推回 2026-08-25（1 天前）

它跑在沙箱裡、最後一步要 push。**推不上去的那一邊沒辦法通報自己
推不上去**——所以這一格由推得上去的 Actions 這一邊量。

## 每日精選那一段

- 每日精選：最後一篇 2026-08-25（1 天前）

**空日也該有文章**：`mode: retrospective` 一定挑得出一則。
所以這一格的判準是天數，不是「今天有沒有」——這支腳本 Actions 那一邊
也會跑，而它跑的時候夜班還沒開始。

## 夜班修的碼有沒有人收

- ⚠ 沒收的修碼分支：1 支，最久的 origin/fix/nightly-enrich-env-and-gitignore-gaps 已經 5 天（門檻 3 天）——夜班修好了推上去而沒有人收，它會每隔一兩晚重新發現同一件事，再開一支新的

判準是「tip 不是 `main` 的祖先」，所以它**假設 merge 用 merge commit**。
改成 squash 的那天每一支歷史分支都會長得像沒收——那時候這一格會說
「判準可能失效」，不會報一個 40 支的數字。

## 判斷層的記憶

- 判斷層帳本：106 筆，最近一次 2026-08-25（1 天前）；最近 7 天有 6 條主線改過主張（agent-refactor、capital-evolution、global-map、infra-cost、model-research、product-market）

`now` / `next` 是整段覆寫的（實測有過相鄰兩版只剩 10% 相同）。
沒有這份帳本，「我上週對這條線怎麼說」這個問題答不出來。

## 來源能力（宣稱 vs 觀察）

- 來源能力：running 28 條，全數已標；16 種能力裡**1 種沒有任何來源宣稱**（`procurement`）；**4 條宣稱了但語料裡從來沒有過**（`src-gh-openai-codex`、`src-kol-thezvi`、`src-media-theregister`、`src-mistral-news`）

這一格**不判紅燈**，理由寫在 `references/source-capabilities.md`：
健康分沒有壞，它只是**只看單班**——「這一班安靜」跟「25 班一次都沒到過貨」
在分數上都是 100。這一行補的是累計那一面；不觸警是因為今天三條裡有兩條
的成因是 robots 合規，會永遠紅，而永遠紅的警報兩週內就會被關掉。
