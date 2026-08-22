# Incident — OpenAI 把 Codex harness 開源，三班都沒看到，而三個守衛全是綠的

- **發現日期**：2026-08-22（人問「為什麼沒有抓到 OpenAI agent 開源」）
- **事發日期**：2026-08-19
- **嚴重度**：中（沒有紅線違反；漏抓一則一級來源的一手發布）
- **狀態**：部分處置。**開源這個「題材」補了觀測能力，開源這則「公告」的入口仍然沒有。**

---

## 一句話

來源在、實體在、probe 是活的、燈是綠的——但 `src-openai-blog` 訂的是
`openai.com/news/rss.xml`，而那則公告發在 `developers.openai.com/blog`，
**兩個不同的發布面**。這是 07-24 那個病的第三次變形。

---

## 那則公告

> **Codex as a platform: build on the open agent harness**
> `https://developers.openai.com/blog/codex-as-a-platform`，2026-08-19

內容是把 Codex CLI、app-server、Codex SDK 當開源元件發布，repo 是
`github.com/openai/codex`。原文自己劃的界線是
「The open-source layer is the harness and integration surface;
model access and managed services remain separate」——開源的是 harness，模型仍是服務。

---

## 事實（每一條都量過，沒有推論）

| # | 量到什麼 | 怎麼量的 |
|---|---|---|
| 1 | `openai.com/news/rss.xml` 有 200 則、時間序、最新是 08-20，**不含這一則** | 整份拉下來逐條看 |
| 2 | 全語料 25 天 × 32 條來源，`developers.openai.com` 出現 **0** 次 | `grep -l` 全 `_corpus/*/*.jsonl` |
| 3 | 08-19/20/21 三晚 `src-openai-blog` 都有新料 | 語料裡 `is_new: true` 各有一筆 |
| 4 | quota 50 對 200 則 feed，約兩週餘裕 | `quota_per_run` vs feed 長度 |
| 5 | HN 那條也沒有 | 用它自己的端點 `hn.algolia.com` 查 08-13 之後 `openai + open source`，只有第三方專案 |
| 6 | `developers.openai.com/robots.txt` 是 `Allow: /`，並自報 `Sitemap: /sitemap-index.xml` | 直接取 |
| 7 | 那張 sitemap 展開後 `/blog/` 有 **24 個 URL**，**全檔沒有任何 `lastmod`** | 直接取 |
| 8 | **那 24 個裡面沒有 `codex-as-a-platform`** | 對整份 XML 搜字串，`harness` 也是 0 |

第 3、4 條合起來排除「抓失敗」：probe 是活的、quota 沒爆。
第 1、8 條合起來是這次的核心：**這則公告在我們能合規走到的每一個機器可讀入口裡都不存在。**

---

## 為什麼三個守衛全是綠的

三個各自都合格，合起來仍然漏。這是重點，不是背景。

### 1. `coverage_watch` 盯的是**實體**，不是**發布面**

`openai` 掛 `max_silent_days: 14`，而 `openai.com/news` 每天出三則企業案例
（Asana、Stampli、RingCentral……）。**OpenAI 這一格永遠不會沉默。**
看板綠著的同時，整條 OpenAI 開源線是黑的。

### 2. `coverage-gap.md` 盯的是**能力**，而詞彙表裡沒有「開源發布」

事發時 `CAPABILITIES` 有 15 個值，沒有一個是開源釋出。
`oss_release` 這個字在這個 repo 裡**存在**，但存在於 `corpus_type`——
那是描述欄位，不進覆蓋率矩陣。

所以「沒人在看 OpenAI 開源」在那張矩陣上**連一格都不會出現**。
它不是紅的，它不存在。這比紅著糟，理由跟 `sources.yaml` v2.5 那段一樣：
沒列是盲點，不是取捨。

### 3. 對得上的來源型態早就在跑，只是只指向一個 repo

`src-gh-vllm-releases`，adapter `github-releases`，endpoint `vllm-project/vllm`，
每晚穩定產 20 筆，而且**進得了 Event**（`evt-2026-07-25-74ed64` v0.26.0、
`evt-2026-08-11-dc5cff` v0.27.1，兩則都 `status: published`）。

也就是說「看某個 repo 的 release」這條路整條是通的、驗過的、有成品的。
它從頭到尾只指向一個 repo，而沒有任何東西會因此變紅。

---

## 這是同一個病的第三次變形

| 日期 | 缺的是什麼 | 補了什麼守衛 |
|---|---|---|
| 07-24 | 清單裡沒有 Anthropic — **實體**缺席 | `coverage_watch.must_watch` + `pending` |
| 07-25 | `robots_ok: false` 假陰性把整條線靜靜關掉 — **來源**被誤殺 | `pulse-robots-recheck` + `source-history.jsonl` |
| 08-19 | 來源在、實體在、燈是綠的，但那條來源訂的是另一個發布面 — **面向**缺席 | **今天沒有任何守衛量得到** |

前兩種都是「這一格是空的」，看得出來。
第三種是「這一格是滿的，但它裝的是別的東西」，看不出來。

---

## 處置

### 做了的

1. **`oss_release` 進 `CAPABILITIES`**（15 → 16）。這讓「開源釋出」這個題材
   在覆蓋率矩陣上長出一列，也讓 `pulse-signal-review --reason oss_release`
   變成合法的裁決理由（`REASONS` 是衍生的，不用另外改）。
2. **加 `src-gh-openai-codex`**：adapter `github-releases`、endpoint `openai/codex`。
   跟 vllm 那條同型，零新碼、零 robots 疑慮。
3. **順手修掉一個被自己踩出來的缺陷**：`pulse-monitor` 的
   「N 條宣稱了但語料裡從來沒有過」，在加來源的當下從 3 變 4——而第 4 條
   是**一班都還沒跑**，不是**跑了 25 班一筆都沒有**。
   把「沒有」跟「還不知道」寫成同一個數字，正是這個 repo 一直在修的病，
   而它出現在一個專門用來抓「宣稱兌不了現」的指標上。
   代價很具體：**每一次補來源都會先製造一筆假的壞消息**，讀的人學會忽略它之後，
   真的該追的那三條也一起沒人看。已拆成兩格，`runs` 走
   `_probe/source-health.json`，參數必填（給預設值等於讓忘了傳的呼叫端
   靜靜退回舊行為，而測試全綠——同 `pulse-gate.evaluate` 的理由）。

### **沒有**做到的，要講清楚（紅線 8）

**上面兩條都接不住 08-19 那一則。**

- `src-gh-openai-codex` 抓的是**版本釋出**，那則是**公告文**。兩者不同。
  這一條補的是「OpenAI 的開源專案在動」這個面向，不是「OpenAI 宣布開源」那一則。
- dev blog 那個面向**沒有補**，而且是刻意不補的——見下一節。

所以：這次的缺口沒有被關上，只是**從看不見變成看得見**。

### dev blog 這條來源的退件理由

站方 robots 自報的 sitemap 是唯一合規入口（紅線 7 只走站方指出的路），
而那張 sitemap 實測有兩個問題：

- **沒有 `lastmod`**，所以排不出時間序。「今天發生什麼」這個問題它答不了。
- **它自己就漏了那則公告**。08-22 取的時候，08-19 發的文不在裡面。

第二點是決定性的：一張**證明過會漏掉新文**的 sitemap，接上去之後
`coverage_watch` 會因為它有到貨而維持綠燈，而它漏掉的東西沒有人會知道。
那就是這整份紀錄在講的那件事，再做一次。

比照 DeepSeek 的前例（`sources.yaml` 官方線末尾）：**退件，並且把退件理由寫下來，
讓這一格紅著**，直到有一個帶時間、且內容完整的機器可讀入口。

---

## 沒做的：面向層的守衛

真正對症的東西是一張新表——每一家的**發布面清單**（news / dev blog /
github / research）各自有沒有來源在看，比照 `coverage_watch` 的 `pending` 慣例
白紙黑字承認缺口。

那不是改一個門檻，是一張新表加一個消費端，所以不在這一輪。
在它落地之前，`coverage_watch` 對「面向缺席」是空轉的——這句話寫在這裡，
是為了不讓下一個人以為那張表已經在看了。
