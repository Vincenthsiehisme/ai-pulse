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

sitemap 先天沒有標題也沒有發布時間，這不是實作缺陷。誠實的選項有三個，
各有代價，要拍板：

1. **接受 null**：那三條 tier-1 官方源失去時間定位與標題，事件頁印「未留存」。
2. **抓內文取 `<title>` 與發布日**：超出目前 `license_note` 的
   「titles + links only」，要重新確認合規（紅線 7）。
3. **換 adapter**：確認這三家有沒有 RSS/Atom。**這是成本最低的一條，應該先查。**

---

## 6. 明確的取捨

改完之後：

- 那三條 tier-1 官方源的事件會**失去可靠的時間軸位置**，聚類少一個維度。
- `lead_days` 對它們**算不出來**，而它們正是「官方承認」那一側——
  也就是這個指標的覆蓋率會明顯下降。
- 事件頁與時間軸上會出現更多「未留存」。

這些都是真的變難看。但現在的狀態是**看起來知道、其實不知道**，而且
「不知道」這件事在鏈上任何一層都不會被發現。**難看是誠實的代價，不是退步。**

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
