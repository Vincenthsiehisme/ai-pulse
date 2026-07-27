---
title: published 不是 published——進料層的代理欄位與它的十七個消費者
status: proposal
author: 設計協作（Cowork）
date: 2026-07-27
review_cycle: 一次性提案，拍板後拆進 references/ 與各 adapter 的規格再進實作
supersedes: —
red_lines_touched: [對自己誠實 (#8), docs-first (#9)]
---

# published 不是 published

> 這份不是 bug 清單。清單在最後，但它們是同一句話的實例，逐條修會再長回來。
>
> **一句話**：`published` 這個欄位在五個 adapter 裡有四個放的不是 published，
> 它往下驅動十七個決定（包括一個不可逆的 id），而這十七個之中**沒有一個會變紅**。

---

## 0. 這份文件從哪來

2026-07-27 有人指出對外站上一則事件頁的模型名稱、發布時間、先後順序都是錯的
（`events/claude-opus-5-0fa5/`）。逐點查下去，三個錯是**同一個根因**；再往外掃，
那個根因是一個更大的形態在終端的三個症狀。

這個 repo 已經替這個形態命過名——`BACKLOG.md` 開頭那句
「**用一個比事實寬鬆的代理指標去代表事實**」。它的特徵是：兩邊在平常的日子裡一致，
正好在有事的那天分岔，**而不會有任何東西變紅**。這份文件是把它從單點提升到系統層。

---

## 1. 進料層：四個 adapter 在 `published` 裡放的不是 published

逐行核對 `scripts/pulse-probe.py` 的五個 adapter（`rss` 與 `atom` 共用
`adapt_rss`，沒有獨立的 Atom 路徑）。分類：**真值** / **代理**（來源給的是意義
相鄰但不同的東西）/ **推導**（來源根本沒有，我們自己造）/ **空**。

| adapter | title | summary | url | published | author | 來源數 | 語料筆數 |
|---|---|---|---|---|---|---|---|
| rss | 真值 | 真值（截 300） | 真值＋退 guid | **代理**：缺 `pubDate` 退 `updated` | 真值 | 23 | 901 |
| atom | 真值 | 真值 | 真值＋退 guid | **代理，且結構性常態** | 真值 | 4 | 110 |
| sitemap | **推導** | 空 | 真值 | **代理**：`<lastmod>` | 空 | 3 | 240 |
| json-api | 真值 | 真值→實測全空 | 真值＋退討論串 | **代理**：HN 投稿時間 | **代理**：投稿者 | 1 | 90 |
| github-releases | 真值＋退 tag | 真值（未剝 md） | 真值 | 真值 `published_at` | **代理**：發版者 | 1 | 80 |

三個要點：

**`sitemap` 的 `published` 是 `<lastmod>`。** 那是 sitemap 協定定義的
「這個檔案最後被修改的時間」——改個錯字、換個模板、靜態站重生成都會動它，
它跟「世界什麼時候發布了什麼」沒有任何定義上的關係。實測 `src-xai-news`
每一筆都是 `T00:00:00.000Z`，一個只有日期卻穿著時間戳外衣的值。

**`atom` 那條退化是結構性的，不是偶發。** RSS 幾乎一定帶 `<pubDate>`，
而 Atom 唯一**必填**的日期元素就是 `<updated>`。所以四條 atom 來源
（`src-media-theregister`、`src-media-theverge`、`src-kol-karpathy`、
`src-kol-simonwillison`）本來就常態走在退化路徑上。

**`sitemap` 的 `title` 是從 URL slug 反推的。** `_slug_to_title()` 的 docstring
很誠實地寫著「這是**推導**不是原文標題」——但值寫進了叫 `title` 的欄位，
而下游沒有任何東西帶著那個但書。實測傷害：`claude-opus-4-7` → 「Claude Opus 4 7」、
`grok-4-5-everywhere` → 「Grok 4 5 Everywhere」。**版本號的小數點沒了，
而版本號正是區分兩則發布事件的那個 token。**

---

## 2. 傳導層：`published` 驅動十七個決定，沒有一個會變紅

| # | 消費者 | 決定什麼 | 錯了會怎樣 |
|---|---|---|---|
| 1 | `pulse-score.py:105-110` | `lead_days > 7` → **訊號直接丟棄**（`gate.yaml` 啟用中） | 靜默 |
| 2 | `lib/quality.py:110-127` | freshness 階梯，佔品質分 1–20 | 靜默 |
| 3 | `lib/quality.py:152` | completeness +3 | 靜默 |
| 4 | `lib/quality.py:182,186` | `stale` / `missing-date` 旗標 | 靜默 |
| 5 | `pulse-score.py:121` | 品質總分 `< 40` → 丟棄；`≥70` → +10 eventability | 靜默 |
| 6 | `pulse-cluster.py:487` | 排序 tie-break：**決定哪個訊號開場**（連帶標題、slug、關鍵詞、公司） | 靜默 |
| 7 | `lib/cluster.py:227-242` | 聚類窗口：96h／21d／incident 7d | 靜默 |
| 8 | `pulse-cluster.py:504` | **Event id = `evt-<published 的 UTC 日>-<hash>`** | 靜默且**不可逆** |
| 9 | `pulse-cluster.py:511` | `happened_at` 與 `date` | 靜默 |
| 10 | `lib/scoring.py:54,70` | `freshness = 100·exp(−h/96)` → `value` | 靜默 |
| 11 | `lib/cluster.py:270-358` | 轉載鏈 ±48h 窗口與「最早的算原創」→ `independent_sources` → `confidence` | 靜默 |
| 12 | `lib/coverage.py:74-78` | `coverage`（observed / backfilled） | 靜默 |
| 13 | `pulse-gate.py:185,204` | `stale_backfill` blocker | 靜默 |
| 14 | `pulse-gate.py:186-199` | 把**已發布**的事件降回 review | 靜默 |
| 15 | `pulse-render.py` ×8 | 時間軸排序、分月、觀測起點線、證據時序、首頁 hero | 靜默 |
| 16 | `pulse-monitor.py:242` | 必盯清單的 30 天窗口 | 不紅 |
| 17 | `pulse-dashboard.py:56` | `published.md` 的日期分組 | 靜默 |

**十七個，沒有一個會讓燈變紅。** 而且是刻意的：2026-07-26 那次事故之後，
monitor 的每一支警報都改成看 `ingested_at` 而不看 `happened_at`
（`references/event-timestamps.md` 記著這件事）。那個修正**本身是對的**——
拿外面的時鐘量自己的鏈，是另一個病。但它的副作用是 `published` 端到端無人看守。

第 8 條要特別點出：**Event 的 id 包含 `published` 的日期，而 id 一旦寫進
`Events/` 就不能改**（`pulse-cluster.py` 的註解明寫）。一個錯的日期會被烙進
永久識別碼。

---

## 3. 結論層：這條鏈的終點正好是本專案自稱唯一的產物

`.github/workflows/data-refresh.yml` 的檔頭寫著：

> lead_days（事情被官方承認 vs 被個人談論的時間差）是這套系統唯一做得出來的產物。

而 `lead_days = first_observed_at − published`（`pulse-score.py:107`），
`recency_max_lead_days: 7` 是**啟用中的硬閘**。

三條 sitemap 來源的身分：

```
src-anthropic-news    tier=1  role=official  track=official  category=vendor
src-xai-news          tier=1  role=official  track=official  category=vendor
src-mistral-news      tier=1  role=official  track=official  category=vendor
```

**它們正是 lead_days 比較的「官方承認」那一側。** 所以這個系統對「官方什麼時候
承認」的量測，用的是官方網站的檔案 mtime。

這不是推論，是可驗的：那一則 Claude Opus 5 事件裡，Anthropic 官網五篇貼文的
`published` 排出來是

```
07-22 00:06  Claude Opus 4 6
07-22 01:28  Claude Opus 4 8
07-23 04:09  Claude Opus 4 5
07-23 04:19  Claude Opus 4 7
07-25 02:03  Claude Opus 5
```

4.6 → 4.8 → 4.5 → 4.7。**不需要知道真正的發布日，光憑版本號的內部矛盾就能斷定
這不是發布時間**——那五個值全部擠在 28 小時內，是站方批次重生成留下的痕跡。

而這也是**上一輪誤判為「`clustering.version_derivation` 未接線」的那個聚類錯誤的
真正根因**：五篇真實相隔數週的貼文，因為 lastmod 被擠進 28 小時，才落進同一個
96 小時窗口，併成一則叫「Claude Opus 5」的事件。**日期錯了，聚類跟著錯。**

---

## 4. 同一個形態的其他實例

不是題外話——它們證明這是形態不是個案。全部逐條驗過。

**（甲）判斷層的 rule-tag 是凍結快照，而它正在一頁上自相矛盾。**
`pulse-enrich-apply.py:77-80` 依當下的 `independent_sources` 寫出
「（單一獨立來源，暫標待證實）」並烙進 prose，之後不再重算；而同一頁的警示框是
render 即時算的。實測：`evt-2026-07-21-1bdb1a` 已發布、`independent_sources: 2`，
判斷層還寫著單一獨立來源，警示框沒出現。**同一頁兩個相反的宣稱，而且它是這一批
裡唯一正在對讀者說假話的。**

**（乙）四個從未量測的傳播因子，被印成粗體 0。**
`pulse-cluster.rescore()` 寫死 `metrics=[]`，所以 `uniqueAuthors` /
`platformBreadth` / `regionBreadth` / `velocity` 結構上永遠是 0。實測 **36 則
已發布事件全部**把這四格印成 0——就在同一格寫著「未量測」的 heat 旁邊。
`lib/scoring.py` 自己的註解寫著「不印 0——0 看起來像『量過了，很冷』，
那是更難察覺的一種謊」。修 heat 那次停在純量，沒往外一層的因子格看。

**（丙）語料天數有三處繞過 `lib/corpus.py` 重數一遍。**
那個模組存在的理由就是「目錄名不是證據，內容才是」。但
`pulse-backlog-status.py:72`、`pulse-dictionary-gaps.py:99`、`pulse-monitor.py:201`
各自用 `iterdir()` 數目錄名。實測塞一個空目錄，health 印「實有語料 23 天」而真值是 4。
而 `lib/atomicwrite.py:43` 在寫檔前先 `mkdir`，失敗正好會留下那種空目錄。
**這一條是 BACKLOG 已記的第 1 號實例重新長出來，而且長在它自己的解方裡**
（`backlog-status.md` 正是為了取代手寫現況表而生的頁）。

**（丁）`effective_role()` 缺值預設 `primary`。**
`lib/quality.py:41-43` 的 official 分支只由**註解**守著，實測
`effective_role(None, None, None) == "primary"`——最強的宣稱。它違反這個 repo
自己在別處立的規矩：「設定讀不到不可以讓門檻自己打開」。目前不會觸發
（每條來源都有 `track`），是結構性缺口不是現行缺陷。

**（戊）`verify-policy-sources.py:97` 把 401/403 印成 `robots_ok: false # verified`。**
其他所有消費者都在 2026-07-24 事故後改成 `robots_unknown` 了，只有這支還把
「我們讀不到」寫成「站方拒絕」，而它正是產生要貼進設定檔的那段文字的腳本。

**（己）遷移腳本用位置配對標題。**
`migrate-2026-07-27-evidence-titles.py:98-106` 依「同一來源的第 i 條 body 行」
配「第 i 個空欄位」，理論上會把 A 的標題貼到 B 的網址。**實測 main 上 0 筆錯**
（URL 逐筆比對 64 筆；唯一有風險那則的 diff 顯示只填了 body 有對應行的那一筆），
但機制不對。body 行本來就帶著 URL，改成用 URL 配對整類消失。

**（庚）三條來源已經死了幾個月到三年，而監控結構上看不見。**
2026-07-27 逐條量 `_corpus/` 裡每個 source 的**最新一筆 `published`**：

| source | 語料筆數 | 最新一筆 | 落後 |
|---|---|---|---|
| `src-meta-research` | 40 | **2023-05-17** | **3 年 2 個月** |
| `src-qwen-blog` | 30 | 2025-09-23 | 10 個月 |
| `src-media-venturebeat` | 14 | 2026-05-19 | 2 個月 |

`pulse-monitor.py:322` 的 `silent_sources` 判準是 `r["items"] == 0`——
**「這班抓回幾筆」被拿來代表「這條來源還在出東西嗎」**。`src-meta-research`
每班穩定回 40 筆，所以永遠不會進沉默名單；那 40 筆全部來自 2023 年。
兩個指標在平常的日子裡一致，正好在來源死掉那天分岔，而沒有任何東西變紅。

這一條的代價是具體的：**Meta 這家公司在本系統裡等於不存在。**
`_config/entities.yaml` 把 `muse-spark` 標成 `status: unverified`，
註解寫「僅見於單一次級來源，需 Tier-1 證據確認」——而 Tier-1 證據就在
`ai.meta.com/blog/`（2026-07-21 還在更新，且 7 月就有兩則 Muse 發布）。
我們配的是 `research.facebook.com/feed/`，一條研究部落格，而且死了三年。
**不是拿不到，是沒在看。**

**（辛）`pulse-probe.py` 沒有 control probe，而它的一次性小弟有。**
`verify-policy-sources.py:237` 的 `control_probe()` 先證明機器連得出去，
連不出去就整份中止、不下任何判決。生產的 probe 沒有這一關：整條網路斷掉時，
它會寫出 27 條各自獨立的 `robots_unknown`，讀起來像 27 個來源同時出事。
（現行行為在單條上是保守的、沒有寫錯——缺的是「問題在我們這邊」這個彙總訊號。）

---

## 5. 提議的修法

**核心規矩一句話：推導值與代理值不可以住在事實的名字裡。**

這個 repo 已經有兩個做對的先例——`heat` 印「未量測」、證據印「日期未留存」。
這份提案是把同一條規矩推到**進料層**，讓下游有機會知道自己拿到的是什麼。

### 階段 A：進料層說實話（不改任何判斷）

adapter 的輸出區分三種來源，欄位名自己說清楚：

```
published        只放來源真的給的發布時間；沒有就是 null
published_proxy  代理值本身（lastmod / submitted_at / updated）
published_kind   real | lastmod | submitted | updated | none   ← 封閉集
title            只放來源真的給的標題；沒有就是 null
title_kind       real | derived_from_slug | none
```

`published_kind` 是封閉集，跟 `coverage` 三態同一個做法：**量不到就說量不到，
而且說得出是哪一種量不到。**

這一階段**刻意不改任何下游判斷**——所有消費者繼續讀 `published`，只是它現在
可能是 null。先讓資料誠實，再談判斷怎麼變。

### 階段 B：逐個消費者決定「沒有真值時怎麼辦」

十七個消費者不會有同一個答案，這正是要分開處理的理由：

- **可以用代理**：聚類窗口（時間相近就是相近，lastmod 也是訊號）、
  排序 tie-break、時間軸分月。條件是畫面上標明。
- **不可以用代理**：`lead_days`（那是這個系統的產物，用代理等於產物是假的）、
  `coverage`（它問的正是「事情發生時」）、`freshness → value`。
  這些在 `published_kind != real` 時應該**回報量不到**，不是算一個數字。
- **要單獨拍板**：Event id 的日期。它不可逆，而且 id 已經寫進 51 份檔案。
  建議 id 改用 `ingested_at`（我們自己的時鐘，永遠是真值），但那是破壞性遷移。

### 階段 C：把三條 sitemap 來源的採集方式重新評估

**2026-07-27 已查證，選項從三個變兩個，而且問題比原本估計的嚴重。**

#### C-0：三家都沒有官方 feed（已查證）

| | 標準路徑 | 首頁 autodiscovery |
|---|---|---|
| Anthropic | `/rss.xml`、`/news/rss.xml`、`/news/feed` 全 404 | 無 `<link rel="alternate">`，頁面未提 RSS |
| Mistral | `/news/rss.xml`、`/feed.xml`、`/news/feed.xml` 全 404 | 無，未提 RSS |
| xAI | `/news/rss.xml` 404、`/rss.xml` **403** | 無，未提 RSS |

旁證：搜尋 Anthropic 的 RSS，跳出來的全是**第三方在替它做**
（`taobojlen/anthropic-rss-feed` 在抓網頁生 feed，RSSHub 有兩張 feed 請求 issue）。
官方有 feed 的話不會有人去做這些。

**但書（紅線 7 的規矩）**：`x.ai/rss.xml` 回的是 **403 不是 404**。照本 repo 自己
在 2026-07-24 事故後立的界線——**「我們讀不到」不等於「站方沒有」**——xAI 那條
嚴格說只能判「autodiscovery 沒有、標準路徑讀不到」，不能寫成「確定沒有」。

**所以「換 adapter」這條出路不成立。**

#### C-1：問題比原本估計的嚴重——標題不是「少了小數點」，是換了一個字串

原本以為 `_slug_to_title` 的損害是標點（`4-6` → `4 6`）。實測五組對照：

| URL slug 推導出來的（我們現在存的、印在對外站上的） | 網站上真正的標題 |
|---|---|
| Claude Opus 5 | Introducing Claude Opus 5 |
| **Introducing Google Workspace Addon** | **Grok in Google Workspace** |
| Robostral Navigate | Introducing Robostral Navigate |
| **Manage Prompts And Skills In Studio** | **Your Prompts and Skills need a system of record.** |
| Leanstral 1 5 | Leanstral 1.5: Proof Abundance for All |

**五組裡有兩組是完全不同的字串。** 也就是說，這三條來源產生的 Event，標題有一類
**根本不是那篇文章的標題**——不是不精確，是不同的東西。而 Event 標題會進 id 的
hash、進聚類的相似度比對、進對外站的每一張卡片。

#### C-2：標題可以完全解決，日期只能部分解決（已查證）

實測 Anthropic 與 xAI 的文章頁：

- **`og:title` 有，而且是真值。** `"Introducing Claude Opus 5"`、
  `"Grok in Google Workspace"`。單一 meta tag，確定性可取，不需要解析內文。
- **機器可讀的發布時間全部 ABSENT。** 沒有 `article:published_time`、
  沒有 `<time datetime>`、沒有 JSON-LD `datePublished`。兩家都是。
- **只有人看的日期**：Anthropic 印「Jul 24, 2026」、Mistral 印「July 8, 2026」，
  在標題下方的自由文字裡，**沒有標籤詞**、格式各家不同、**沒有時區**。

順帶一個對照：那篇 Anthropic 文章頁上寫的是 **Jul 24**，而我們從 lastmod 取的是
**07-25T02:03:36Z**。差一天——lastmod 不是發布時間，這是第三個獨立證據。

#### C-3：因此正確的做法，與它逼出來的一個新欄位

**標題**：抓文章頁讀 `og:title`（缺則退 `<title>` 去掉站名後綴）。真值、確定性、
單一 tag。這一條把整類「編造的產品名」消滅掉。

**合規要重新理解，不是重新爭取**：目前 `license_note` 寫「titles + links only」，
而 `_slug_to_title` 的 docstring 說「抓內文超出這個範圍，所以選還原」。這個推論把
**抓取**跟**留存**混為一談了。抓一頁只讀它的 `og:title`、只留存標題＋連結＋日期，
留下來的東西**正好就是 titles + links**——而且是真的那個。反過來說，現在的做法
留存的是一個**編造的**標題，那離「titles only」更遠，不是更近。這一點要拍板，
但它是澄清不是放寬。

**日期**：沒有結構化來源，只有人看的日期。所以誠實的做法會逼出一個新欄位：

```
published            真值；沒有就是 null
published_kind       real | lastmod | submitted | updated | page_visible | none
published_precision  second | day | none          ← 這一格是這次查證逼出來的
```

從「Jul 24, 2026」解析出來的東西**只有日到位、而且沒有時區**。把它存成
`2026-07-24T00:00:00Z` 就是**編造精度**——跟這份文件從頭到尾在講的是同一隻病，
只是換一個維度。所以精度必須跟值一起存，而下游（聚類的 96 小時窗、lead_days）
必須知道自己拿到的是日還是秒。

#### C-4：動工前必須先驗的一件事

上面所有結論來自 WebFetch，而**它可能執行了 JavaScript**。這個 repo 的
`safe_fetch` 是單純的 HTTP GET——如果那三家的文章頁或列表頁是前端渲染的，
plain GET 拿到的會是空殼，整個設計就不成立。

**這一題有現成的工具，而且應該用它而不是我在這裡猜**：

```bash
VAULT_DIR=. python3 scripts/verify-policy-sources.py <url>
```

它用 probe 的 UA 做真實抓取、同時驗 robots，正是為這件事寫的。要驗三件事：
plain GET 的 HTML 裡有沒有 `og:title`、有沒有那個人看的日期、以及文章路徑的
robots 允不允許（現在的 `robots_ok: true` 是對 sitemap 而言）。

**驗到之前，C-3 是提案不是結論。**

#### C-4′：第一次驗證的結論是錯的，錯法正好是這份文件在講的那一隻病

**2026-07-27，這份文件的作者把 C-4 回報成「已驗證，而且是否定的」。那是錯的。**

當時手寫了一支只呼叫 `safe_fetch` 的臨時腳本，對
`https://www.anthropic.com/news/claude-opus-5` 拿到 `403 / 104 bytes`，
於是結論寫成「Anthropic 的 WAF 擋掉生產抓取器，C-3 不成立」。

那 104 bytes 的內容是：

```
Host not in allowlist: www.anthropic.com. Add this host to your network
egress settings to allow access.
```

標頭是 `x-deny-reason: host_not_allowed`。**擋人的是執行環境的 egress
allowlist，不是站方。** 同一個容器對 `openai.com`、`deepmind.google`
也回一模一樣的東西——而那兩條來源在 CI 裡每天正常出貨。

也就是說：**用一個比事實寬鬆的代理指標（「這台機器讀不到」）去代表事實
（「站方拒絕」）**。兩者在平常的日子裡一致，正好在有事的那天分岔。
這份文件從第一行開始講的就是這個形態，而作者在驗證它的過程中犯了它。

**更難看的一點**：`verify-policy-sources.py` 的 `control_probe()` docstring
一字不差地寫著這個陷阱——「沒有它，公司代理或 egress allowlist 對每個 host
回 403，看起來會跟『每個站都拒絕我們』一模一樣」。C-4 自己也已經指名要用那支。
工具在、警告在、指示在，繞過去的是人。用對工具之後它立刻給出正確判決：

```
robots: UNKNOWN  (intercepted by local egress proxy (x-deny-reason:
        host_not_allowed) -- undetermined; this is NOT a refusal by the site)
```

**所以 C-4 的正確狀態是「未驗」，不是「已否決」。C-3 仍然是提案。**

#### C-4″：把那道防線做成結構性的——`scripts/verify-article-metadata.py`

靠人記得用對工具，是這個 repo 一直在拆掉的那種機制。所以這次不留在教訓層：

新增 `scripts/verify-article-metadata.py`，直接 import `pulse-probe.py` 的
`safe_fetch` 與 `robots_verdict`（**生產路徑本人**，不自己寫一套 HTTP），
並且把三件事變成結構：

1. **control probe 不通過就不出判決**（exit 4）。它刻意不看狀態碼是不是 200——
   要區分的是「有沒有走到對方的伺服器」，不是「對方喜不喜歡我們」。
2. **認得 egress 攔截的簽名**（`x-deny-reason` 標頭 / body 的 allowlist 字樣），
   判 `no_verdict` 而不是 `site_refused`。反方向同樣守著：站方自己的 403
   **沒有**那些簽名，必須留在 `site_error`——把確定的壞消息洗成不確定，
   是同一隻病的鏡像。
3. **退出碼 `no_verdict(4) > no_og_title(3) > site_error(2) > ok(0)`。**
   沒有判決排最前面：壞判決至少是關於站方的，沒有判決是關於我們自己的。

`.github/workflows/verify-article-metadata.yml`（`workflow_dispatch`）
讓它跑在 **CI**，因為那才是 `safe_fetch` 真正跑的網路。selftest 釘住
`--skip-control` 不得出現在 workflow、驗證那一步不得 `continue-on-error`。

**下一步是人按一次那個按鈕**：Actions → Verify article metadata (C-4) →
Run workflow → preset `sitemap-sources`。跑完會留下 `c4-report.json` 這個
artifact，那份 JSON 才是可以寫進本文件的證據。

| 退出碼 | 意思 | 對 C-3 的影響 |
|---|---|---|
| 0 | 三頁都讀到 HTML 且都有 `og:title` | C-3 前提成立，可以動工 |
| 3 | 讀到 HTML 但缺 `og:title` | 前提不成立，要換做法（回頭看 C-5 的列表頁） |
| 2 | 站方 4xx/5xx 或明文 Disallow | 這是**站方的**答案，可以寫進設計 |
| 4 | 沒有判決 | 什麼都不要寫。連 CI 都被擋，代表問題在我們這邊 |

#### C-5：順帶發現的一條更省的路（同樣待驗）

Mistral 的 `/news` 列表頁本身就同時列出**真標題與日期**
（實測拿到三篇的標題與「July 8, 2026」這種日期）。若 plain GET 也看得到，
那麼**一次抓列表頁**就同時解決標題與日期，比「抓 sitemap 再逐篇抓文章頁」
少一個數量級的請求，對站方也更客氣（紅線 7 的 rate-limit 那一半）。

這條要跟 C-4 一起驗。**不要因為它比較省就先選它**——省是附帶好處，
選它的理由必須是「plain GET 拿得到真值」。

---

### 階段 D：模型演變時間線——它跟「得修」是同一件工程，不是兩件

**需求原話**：「open ai, claude, gemini, grok, meta 等主流模型這幾個要將模型
演變時間線補上；針對時間線，不需要補『以下全部是回填——首抓時撈回的存量，
事情發生時我們還沒有在看』。」

那句但書是對的，而且理由比「看起來囉唆」更硬：**回填語意根本不適用。**
`coverage` 三態問的是「事情發生時，我們的抓取器在不在線上」。模型演變時間線
問的是「這個模型什麼時候發布的」。前者是關於**我們**的陳述，後者是關於
**世界**的陳述。把 backfilled 的字樣貼到一份參考資料上，等於宣稱它是我們
觀測的產出——那是反方向的同一隻病。

#### D-1：先量能不能從語料長出來。答案是不能，而且差了一個數量級

| 家族 | source | adapter | 標題 | 日期 | 語料涵蓋 |
|---|---|---|---|---|---|
| OpenAI | `src-openai-blog` | rss | 真值 | 真值 `pubDate` | 2026-06-18 → 07-27 |
| Gemini | `src-deepmind-blog` | rss | 真值 | 真值 `pubDate` | 2026-05-16 → 07-22 |
| Claude | `src-anthropic-news` | sitemap | **推導** | **代理** `lastmod` | 2026-07-01 → 07-25 |
| Grok | `src-xai-news` | sitemap | **推導** | **代理** `lastmod` | 2026-01-28 → 07-24 |
| Meta | `src-meta-research` | rss | 真值 | 真值 | **2023-03-24 → 2023-05-17** |

最左邊那一欄能覆蓋的最早日期是 **2026-01-28**。一份 GPT / Claude / Gemini 的
**演變**時間線要回到 2018–2023，我們手上最長的一條是**六個月**，而其中兩條
的標題本來就不是真的。**這份時間線不可能是語料的產物。** 硬做出來的東西會是
一條「從 2026 年才開始有模型」的時間線——比沒有更誤導。

Meta 那一列不是「涵蓋比較短」，是**沒有來源**（見第 4 節（庚））。

#### D-1′：D-2 的結論後來被推翻了——規格移到 `references/model-timeline.md`

**底下 D-2 到 D-4 的內容保留原樣，因為它們是錯的，而錯法本身是紀錄。**

D-2 說「Tier-1 沒有現成的發布日期表」。那是查了廠商的**模型總覽頁**、
**feed**、**文章頁 metadata** 之後下的結論——三個表面都查了，但**還有第四個**：
release notes / changelog。四家都有、都有逐條日期、最早回到 2023-10。

「我沒找到」與「不存在」是兩個不同的宣稱。這個 repo 已經為了同一件事在
`robots_unknown` 上立過界線（紅線 7），而本文件的作者在同一天內於**兩個維度**
上各犯一次（C-4′ 是第一次）。

**這一層的規格因此移出本文件**，改由 `references/model-timeline.md` 承載
（紅線 9：先文件後碼）。那份文件裡有三類來源的分工、封閉集欄位、
為什麼不採用「單一 LLM 正規化」那一步（紅線 1），以及拿真頁面跑出來的
七個洞與六個數字。

`lib/modelline.py` 已實作純函式層，Anthropic 那家的實測是
**248 列 / 2024-05-10 → 2026-07-24 / 日期解析失敗 0**。
另外三家被開發容器的 egress 擋住，維持未驗——等 CI 的
`--preset release-notes --save-html` 帶回真 bytes。

---

#### D-2：再量 Tier-1 有沒有現成的發布日期表。答案也是沒有

2026-07-27 逐個查：

- **廠商文件頁沒有發布日期欄。** `platform.claude.com/docs/.../models/overview`
  的模型表有 API id、知識截止、訓練截止，**沒有 release date**。
  唯一的日期是 Fable 5「beginning June 9, 2026」這種上架敘述句。
- **Anthropic / xAI 沒有 feed**（C-0 已查證）。
- **文章頁沒有機器可讀日期**（C-2 已查證：`article:published_time`、
  `<time datetime>`、JSON-LD `datePublished` 三個全部 ABSENT）。
- **第三方時間軸站有一堆，而且互相矛盾、也跟我們的 Tier-1 矛盾。**
  搜尋當天的前排結果裡，一篇標題是「Claude Opus 5 Still Unreleased — July 23
  Miss」，另一篇說「Claude Sonnet 5 Launched June 30, 2026」——而我們的 sitemap
  在 `/news/claude-opus-5` 上有一筆 lastmod `2026-07-25`。這正是
  `references/evidence-tiers.md` 存在的理由：**拿 Tier-3 的猜測去填一份看起來
  像事實的表，是這份文件從頭到尾在反對的那件事，只是換一個入口。**

#### D-3：所以結論——時間線的每一格，都只能來自 C-3 要修的那個地方

把 D-1 與 D-2 併起來，唯一存在的 Tier-1 事實是：**廠商發布頁上，人看得到的
那個標題與那個日期。** 也就是說：

> **模型演變時間線的資料來源，與「得修」要修的是同一個東西。
> C-3 修好，時間線就有料；C-3 不修，時間線就只能靠編。**

這件事的順序因此是被決定的，不是被選擇的：

```
C-4 在 CI 按一次      →  og:title 與人看的日期，plain GET 拿不拿得到
  ↓ 綠
C-3 動工              →  title_kind / published_kind / published_precision
  ↓
Claude 與 Grok 的標題與日期變成真值
  ↓
階段 D 才有東西可畫
```

#### D-4：而在那之前，時間線可以先有一個誠實的形狀

不是「先做三家、缺兩家」——那正是「這是重要的環節，不該選便宜的做法」擋掉的
做法，而且缺的兩家（Claude / Grok）正好是使用者點名要的。改成先把**規格**
定下來，讓 C-3 一落地就能接上：

```yaml
# 每一列的欄位，以及它只能從哪裡來
product_line:   claude | gpt | gemini | grok | llama|muse-spark   # entities.yaml 的 id
version:        # 版本字串，來自 og:title 的真值，不是 slug
released_on:    # 廠商發布頁上人看的日期
date_precision: day        # 封閉集：second | day | month | none
date_kind:      page_visible   # 封閉集：real | page_visible | lastmod | none
source_url:     # Tier-1 廠商頁，逐列一條，沒有就這一列不存在
source_tier:    1          # 只收 1。Tier-3 的時間軸站一律不進
```

三個硬規矩，每一個都對應這份文件裡已經犯過的一個錯：

1. **`source_url` 缺就整列不存在。** 不留「待補」的空列——空列在畫面上
   跟已知的列長得一樣。
2. **`date_precision` 跟值一起存。** 「Jul 24, 2026」是日精度、沒有時區，
   存成 `2026-07-24T00:00:00Z` 就是編造精度（C-3 已經因為同一個理由
   逼出這個欄位）。
3. **這份表要自己說它不是觀測。** 頁面上寫「廠商發布頁的整理，不是本系統
   觀測到的事件」——與 `coverage` 三態分屬兩層，互不冒充。這正是使用者說
   「不需要補那句回填」的正確實作：不是把話拿掉，是換成對的那一句。

**明確不做**：在 C-4 綠燈之前，不建立這份 YAML、不畫這個時間軸。
現在建立等於先寫一份靠記憶填的表，然後永遠沒有人回來換掉它。

---

## 6. 明確的取捨

**2026-07-27 查證後，取捨的形狀變了：標題不再是取捨，日期才是。**

**標題沒有取捨**——`og:title` 是真值，抓得到就該用，現在存的是編造的。
唯一的成本是每篇多一次請求（或改抓列表頁，見 C-5），以及要拍板
「titles + links only」的正確讀法（見 C-3，那是澄清不是放寬）。

**日期才是真的取捨**，而且只剩兩個選項：

1. **接受 `published: null`**：那三條 tier-1 官方源失去時間定位，
   `lead_days` 對它們算不出來，時間軸上它們沒有可靠位置。
2. **取人看的日期，並誠實標成 `precision: day`**：拿得到日，拿不到時分秒，
   也沒有時區。聚類的 96 小時窗要改成能吃「日」這種精度，
   `lead_days` 的解析度會退到「天」。

兩條都會讓畫面與指標變難看，而且第二條還多一份解析脆弱性（版面一改就壞，
所以必須是「解析不到就回 null」而不是猜）。

但現在的狀態是**看起來知道、其實不知道**，而且「不知道」這件事在鏈上任何
一層都不會被發現。**難看是誠實的代價，不是退步。**

要強調的是：不管選哪一條，**標題都該修**，而且它是這三個症狀裡唯一能
100% 修對的一個。

---

## 7. 明確不做

- **不猜真實發布日。** 不去外部服務查、不用啟發式回推——那是拿另一個代理換這個代理。
- **不回頭改既有 Event 的 id。** id 不可逆是既定規格，要改是另一份提案。
- **不因為 `published` 是代理就丟掉那三條來源。** 它們是 tier-1 一手來源，
  問題在時間欄位不在來源本身。
- **不在這份提案裡逐點修第 4 節那六條。** 它們是同一個形態的實例，
  逐條修會再長回來；甲、乙兩條因為正在對讀者輸出，可以先單獨止血。

---

## 8. 驗收與測試方向

拍板後要能回答：

- 每一個 adapter 的每一個輸出欄位，`*_kind` 說的跟實際來源一致
  （selftest 逐 adapter 餵 payload 驗）。
- `published_kind != real` 時，`lead_days` / `coverage` / `freshness`
  回報量不到而不是回報數字。
- 畫面上任何一個時間，讀者看得出它是真值還是代理。
- **變異**：把 `published_kind` 一律填 `real`、把代理值搬回 `published`、
  讓 `lead_days` 在代理上照算——三格都必須被行為測試殺掉，
  而不是只有 meta 測試紅（那一課記在 `references/event-timestamps.md`）。

## 9. 這份提案不保證什麼

- **不保證改完 lead_days 就準。** 它只保證算不出來的時候會說算不出來。
- **不保證第 4 節那六條都值得修。** 丁、戊兩條目前不會觸發，是結構性缺口；
  排序與取捨留給拍板。
- **沒有量過 rss / atom 的退化實際發生率。** 已知 Atom 結構上常態退化，
  但「有多少筆的 `published` 其實是 `updated`」需要在 adapter 加上
  `published_kind` 之後才量得到——**這正是階段 A 先做的理由**。
