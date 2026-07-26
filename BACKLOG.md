# AI-Pulse：應做而未做

盤點時間 2026-07-26，`main` 已在 `037d8ae`（全部分支已併入，遠端零未合併分支）。

這份清單只寫「**已知有問題、但還沒動手**」的事。已經修掉的不列。每一條都寫清楚
壞在哪、看得出來還是看不出來、以及為什麼還沒做。

---

## 零、必須在 07-27 發生的一件事（有時限）

`data-refresh.yml` 現在的 cron 是 `0 */2 * * *`，一天 12 班。這是媒體線剛開時
臨時調快的，`robots --stale-days` 也一起從 7 調成 1。排程任務
`trig_01F52Q24UntdNVTd3DWbxFgs` 會在 **2026-07-27 12:00Z** 觸發，把兩個值改回
`0 16 * * *` 與 7。任務目前 enabled、next_run 正確。

**如果 07-27 過了而 workflow 裡還是 `*/2`，代表那個任務沒跑到，要手動改。**
workflow 檔案第 16-17 行已經把這段話寫在註解裡了。一天 12 次去打人家的 robots.txt
是不禮貌的，而且我們自己沒有那個量的需求。

---

## 一、看起來在運作、其實從來沒有執行過的判斷（最危險的一類）

這一類的共同特徵是：**儀表板上有數字、排序也合理，只是那個數字量的不是它名字說的
東西。** 壞掉的時候沒有任何紅燈。

### 1.1 `unsupported_heat` 一次都沒有擋過任何東西

實測 48 個 Event：`uniqueAuthors`(權重 30)、`velocity`(20)、`platformBreadth`(7)、
`regionBreadth`(6) — 這四個因子**全部 0/48**。63% 的權重恆為零。實際會動的只有
`independentSources × 8` 加上 `freshness × 0.08`，而 47/48 的
`independentSources` 是 1。

所以 heat 的理論上限約 48，而 `gate.yaml` 的 `heat_threshold` 是 70。
**熱度支撐檢查從系統上線到現在，一次都沒有觸發過。**

門檻沒設錯，是輸入不存在：24 條來源全是 blog / newsroom 形態，量不出平台廣度；
EU 三條 dormant、CN 只剩 Qwen，量不出地域廣度。已記錄在 `399687a`，刻意只記錄
不改公式（紅線 9）。

**該做的事**：要嘛承認 heat 現在就是「獨立來源數 × 新鮮度」，把它改名、把那 30 分
權重刪掉、門檻降到實際值域裡；要嘛去補能量出平台廣度的來源形態。
**兩件事都不做、就這樣掛著，是目前的狀態，也是最糟的狀態。**

### 1.2 `gate.yaml` 還有 12 個 key 沒有任何程式碼讀它

`docs/gate-unconsumed`（已併）把它們全部標成 `⚠ 未接線` 並用 selftest 釘住標記，
所以**現在不會再騙人了**。但標記不等於修好。剩下的 12 個：

- **`dedup:` 整塊未接線**（`minhash_jaccard: 0.80`、`ngram: 4`、
  `event_window_hours: 72`）。真正在跑的是 `lib/cluster.py` 裡硬寫的 token-Jaccard
  加上 96h / 7d / 21d 三段窗口。把 `event_window_hours` 從 72 改成 48 重跑，聚類
  結果不會有任何變化 —— 下一個人會去懷疑資料，而不是懷疑這個欄位。
- **`clustering.version_derivation` 整塊未接線**。`claude@opus-4.8` 這種衍生實體
  目前不會產生。
- **`clustering.unknown_entity` 整塊未接線**，而且它的
  `report_to: _dashboards/dictionary-gaps.md` 指向的檔案**不存在**（`_dashboards/`
  下只有 blocked / dropped / health / published 四張）。字典缺口目前沒有任何地方
  在收集，只能靠人翻語料發現。
- **`evidence.need_independent_tier2: 2`** 描述的是「兩個獨立 Tier-2 也可以放行」
  這條替代路徑 —— **這條路徑不存在**。實際只有 `missing_primary_evidence` 一條
  規則在擋。
- **`evidence.translation_chain` 未接線**，後果很具體：一篇英文原文加上一篇中文
  改寫，現在會被算成**兩個獨立來源**。`feat/media-line` 那七條媒體線之所以全部
  只收英文，就是在閃這個坑（`sources.yaml` 第 92 行寫著）。中文媒體要進來之前，
  這個必須先接上。
- `quality.freshness_full_hours` / `freshness_zero_days` 未接線（實際是
  `lib/quality.py:_freshness()` 的硬寫階梯）。

---

## 二、資料進不來的地方

### 2.1 九條可跑來源本窗口零產出

`src-mistral-news`、`src-kol-thezvi`，加上七條 `src-media-*`。

七條媒體線是 `feat/media-line` 剛併進來的，**還沒在 CI 跑過任何一班**，零產出是
正常的 —— 但下一班之後如果還是零，就要當成 adapter 沒接上來查。

`src-mistral-news` 不一樣：**它已經連兩天 HTTP 200、robots True、產出 0 筆。**
設定是 `adapter: sitemap` 指到 `sitemap-index.xml`，配 `url_prefix: /news/`。
兩個可能：sitemap-index → 子 sitemap 的展開沒做（或 `max_sitemaps: 3` 抓到的三張
剛好都不含新聞），或是 `url_prefix` 對不上實際路徑。

**我今天沒查出來的原因要講清楚**：這個容器的 proxy 擋外部連線（403），我沒辦法在
本地抓那張 sitemap 驗證。要查只能在 CI 裡查，作法是讓 sitemap adapter 在零產出時
把「展開到幾張子 sitemap、過濾前的前幾條 URL」印進 `_probe/<日>/report.md`。
那個 debug 輸出本身就值得做 —— 現在的 report 只告訴我們「200 / 0 筆」，
分不出「站上真的沒新東西」跟「我們解析不出來」。

### 2.2 覆蓋盲點還有 21 家標著 pending

DeepSeek、SSI、Thinking Machines、Perplexity、Cursor、Cognition、Scale AI、Z.ai、
Moonshot、MiniMax、ByteDance、Baidu、Tencent、TSMC、Broadcom、Groq、Cerebras、
CoreWeave、AWS、Cohere。

這些在設定檔裡標了 `pending`，所以**不觸警** —— 這是誠實的做法（紅線 8），但
「誠實地承認沒覆蓋」跟「覆蓋到了」是兩回事。其中 DeepSeek(22)、Scale AI(22)、
MiniMax(6)、Broadcom(2)、Cerebras(2) 已經**在別人的語料裡被看見**，代表它們有新聞
在流動，只是我們沒有第一手來源。

---

## 三、做了一半的

### 3.1 People layer 第三步沒開始

`person_id` 的獨立性計算（連通分量）已經接上、selftest 有釘。但
**每一列語料的 `author` 還沒有真的綁到 `person_id`** —— 現在 `person_id` 只從
`sources.yaml` 的來源層設定來。所以「同一個人在兩個平台發文」這件事，只有在那個人
自己有一條專屬來源時才抓得到；他投稿到媒體、或在 podcast 上講，綁不起來。

`pulse-probe.py` 第 74 行已經留了註解說明這件事。

### 3.2 `_corpus/<day>/` 要不要累積 —— 這題還在你手上

現在是每天一個目錄、只放當天新看到的列。覆蓋範圍檢查因此只有 3 天的實有語料，
monitor 自己會印「語料期間不足 30 天，沉默天數僅供參考」。要不要改成累積視窗，
我沒有動，因為那會改變所有「近 30 天」統計的意義。

### 3.3 11 則 `stale_backfill` 擋著的 Event

monitor 顯示 review=14 裡有 11 則是「設計上擋著」的舊聞回填，不是卡住。這是對的
行為，但**沒有任何路徑讓它們離開這個狀態** —— 它們會永遠留在 review。
要嘛給一個 `archived` 終態，要嘛定期清掉。現在只是靠 monitor 把它們跟真正的待處理
分開印，不讓數字互相污染。

---

## 四、環境層面的、我做不到需要你動手的

### 4.1 17 條已合併的遠端分支刪不掉

`main` 現在是 `037d8ae`，遠端上除 `main` 外的 **16 條分支全部已完整併入**，
可以安全刪除：

```
docs/config-sources-machine-written   docs/gate-unconsumed
docs/heat-dead-terms                  docs/pr-first-workflow
feat/health-dashboard                 feat/media-line
feat/official-sources-coverage        feat/people-layer
feat/source-health                    fix/author-classifier
fix/backfill-flag-erased-by-second-run  fix/doc-narratives-direct-push
fix/keywords-nondeterministic         fix/probe-mislabels-403-as-disallow
fix/traditional-placeholder           fix/unenriched-age-uses-news-date
test/backfill-sticky-flags
```

`git push origin --delete` 這個指令被這個 session 的安全分類器擋著，我送不出去。
GitHub 網頁的 branches 頁面有一鍵刪除已合併分支。

### 4.2 GitHub API 在這個環境被 proxy 擋（403）

所以我**開不了真正的 PR**，只能推分支 + 你在網頁上合，或像今天這樣直接在本地合
了再推 `main`。這不影響「發現問題自己開分支」那條規則，但要知道
「PR」在這裡實際上是「分支 + 我在對話裡寫的 review 說明」。

---

## 五、下一班 CI 是真正的驗收

今天併進 `main` 的東西裡，有幾樣**還沒有在 GitHub Actions 上跑過一次**：

- `feat/media-line` 的七條媒體來源（本地 selftest 綠，但沒真的抓過）
- `feat/source-health` 的 lifecycle 自動升降級（會**寫回 `sources.yaml`**）
- `feat/health-dashboard` 的 `Vault pages` 步驟（會產生 32+ 張 `Sources/*.md`）
- `fix/unenriched-age-uses-news-date` 的 `ingested_at`（新 Event 才會帶）

本地驗證狀態：selftest **174/174**、monitor 三個 alert flag 全開 **rc=0**。
但第一班之後值得看一眼 commit diff，特別是 lifecycle 自動降級有沒有誤殺來源。
