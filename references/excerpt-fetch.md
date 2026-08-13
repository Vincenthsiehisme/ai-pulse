# 摘要補抓 —— 什麼時候可以去讀那一頁，什麼時候不行

> 消費者：`scripts/pulse-probe.py` 的 `excerpt_allowed()` / `extract_excerpt()` /
> `fill_missing_excerpts()`，`_config/sources.yaml` 的 `excerpt_fetch` 欄位，
> `scripts/selftest.py` 的六條判準。
> 規格先於實作（紅線 9）：這一頁先寫，碼才動。

## 問題

2026-08-13 盤點語料，四條來源從頭到尾一筆摘要都沒有：

```
src-anthropic-news  600 筆  0 有摘要   sitemap
src-xai-news        600 筆  0          sitemap
src-hf-blog         180 筆  0          rss
src-amd-ir           10 筆  0          rss
```

合計 1,390 筆，佔語料 21%。後果落在潤稿那一端：只綁到這些來源的事件，
六層 prose **一層都寫不出來**——潤稿紅線第 2 條是只依證據不編造，
而證據裡除了標題什麼都沒有。當天 15 則待潤事件裡有 9 則卡在這裡。

它每晚都會被 `pulse-enrich-prep` 撿起來、每晚都潤不出來，
而「未 enrich」那個數字會一直掛著，看起來像潤稿端偷懶。

## 為什麼不是「把四條都補抓內文」

第一版的修法就是這句，而它錯在三個地方。記下來是因為這三個錯都不是打錯字，
是**沒有去讀已經寫在檔案裡的東西**。

### 錯一：那四條不是同一種來源

只有兩條是 sitemap adapter。`src-hf-blog` 與 `src-amd-ir` 是 rss——
它們的 feed 解析得很好（標題是正常的原文標題，不是 slug 還原的），
只是 feed 裡沒有 `<description>`。從「零摘要」推回「sitemap adapter」，
是拿一個統計現象去猜成因，而成因就寫在 `_config/sources.yaml` 的 `adapter` 欄位裡。

### 錯二：這個決定 repo 裡早就寫過

`_slug_to_title()` 的 docstring 第三行：

> sitemap 沒有標題欄位，要嘛從 slug 還原、要嘛去抓內文；
> **抓內文超出 license_note 的 "titles + links only"**，所以選還原。

`adapt_sitemap()` 的合規邊界（紅線 7）也寫著「不猜路徑、不爬全站、**不抓任何一篇內文**」。

### 錯三：有一條線不是我們畫的

`x.ai/robots.txt`：

```
Content-Signal: ai-train=no, search=yes, ai-input=no
```

`ai-input=no` 說的是「不要把這裡的內容當成 AI 的輸入」。
抓 x.ai 的內文去餵潤稿，正好就是那件事。

**這條跟 `license_note` 不同層**：`license_note` 是我們自己寫下的保守約束，
要放寬是我們自己的決定；Content-Signal 是站方公開宣告的偏好，不是我們能決定的。
兩者在檔案裡長得很像（都是一行字），在道理上完全不同，所以這裡把它們分開寫。

## 三層判準

一條來源要能補抓摘要，三層都要過。缺一層就不抓，而且**不抓不是失敗**——
留空摘要是這個系統的正常狀態，空摘要比生出來的摘要好（紅線 2）。

```
第一層  站方 robots.txt 允許取那個路徑            量得到，每班驗
第二層  站方沒有宣告 ai-input=no                  量得到，人工登記於 license_note
第三層  我們自己的 license_note 允許 excerpt      我們寫的，改它要走 PR 並寫理由
```

今天的結論：

| 來源 | robots | Content-Signal | license_note | `excerpt_fetch` |
|---|---|---|---|---|
| `src-hf-blog` | `Allow: /` | 無 | titles + **excerpt** + link | **true** |
| `src-anthropic-news` | `Allow: /` | 無 | titles + links only | false |
| `src-xai-news` | `Allow: /` | **ai-input=no** | titles + links only | false（且不得改）|
| `src-amd-ir` | 未查 | 未查 | titles + links only | false |

`src-anthropic-news` 那一格是**我們自己的線**，站方沒有拒絕。
2026-08-13 決定不動它：它解不掉當時卡著的那 6 則（見下一節），
而這條自我約束是這套系統可信度的一部分。要改的話改 `license_note`
並在這裡寫下改的理由——這一格審計時會被問。

`src-xai-news` 那一格不同：**不管誰要求都不改**。

## 補抓解不掉的那一類

那 6 則 Claude 4.x（`Claude Sonnet 4.6` / `4.5`、`Claude Opus 4.5`–`4.8`）
日期是 2026-07-21～07-23，而語料最早只到 07-24。
`coverage: backfilled` 那一格早就把話說完了：**事情發生時我們還沒開始看**。

掃過非官方來源提到 Claude 的 41 筆去重紀錄，沒有一筆在講這四個版本的發布。
不是抓漏，是我們當時不在。

所以就算 Anthropic 那條線開了、內文抓下來了，這 6 則能多出來的也只是
「那一頁**現在**長什麼樣」，不是「當時發生了什麼」。
**改抓取端解不掉回填期。** 它們的事實層要寫的是這句實話，
然後由 `thin_fact` 照常擋著——那是正確的結果，不是待修的狀態。

這一段寫在這裡，是因為下一個看到「未 enrich 一直不歸零」的人，
第一個念頭多半還是「去補抓內文」。

## 實作邊界

### 只補「feed 自己沒給」的那一格

`fill_missing_excerpts()` 只處理 `summary` 是空字串的項目。
feed 給了摘要就用 feed 的——那是發布方主動放進 feed 的東西，
跟我們自己去讀那一頁是兩件事。

### 只補這一班第一次看到的項目

已經在 `seen.json` 裡的 URL 不再取。否則同一頁每晚重取一次，
而它的內容不會變，請求量卻跟語料規模同階成長。

### 主機必須跟 endpoint 同一台

robots 與 Content-Signal 是**對某一台主機**驗的。feed 裡的項目指到別的網域時，
那台主機我們一次都沒驗過——照抓等於把一次合規檢查的結論套到沒檢查過的地方。
所以跨主機一律跳過並記進 diag。

這條也順便擋掉一種供應鏈問題：feed 被動手腳、項目指向任意網址時，
我們不會跟著去取。

### 每班有上限

`excerpt_fetch_max`（預設 10）。回填首班可能一次冒出幾十筆新項目，
沒有上限的話第一次跑就是對別人站台的一陣連發。超過上限的照樣留空摘要。

### 抓不到就留空，不猜

非 200、逾時、頁面裡沒有 `og:description` 也沒有 `description`——
三種都是留空並記進 diag，不退去抓 `<p>`、不拿標題充數。
**「我們讀不到」不可以長得像「這篇沒有摘要」**，所以 diag 分四格記：

```
excerpt_tried          有資格且真的送出請求的
excerpt_ok             取到文字的
excerpt_skipped_host   跨主機跳過的
excerpt_failed         送出了但沒拿到文字的（狀態碼 / 沒有 meta）
```

### 取的是 meta，不是內文

`og:description` 或 `<meta name="description">`，截到 `SUMMARY_CHARS`（300）。
那一格是發布方**寫給別人轉述用**的一句話——它存在的目的就是被摘錄。
不解析 `<article>`、不抽第一段 `<p>`：那才是「抓內文」。

這個界線要守得住，靠的是碼裡只有一條 meta 的正則、沒有第二條路徑。
哪天有人加了 `<p>` 的 fallback，變異盤點那條會紅。
