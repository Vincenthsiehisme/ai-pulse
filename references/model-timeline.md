---
title: 模型演變時間線——第四層資料，以及它為什麼不是 Event
status: draft
date: 2026-07-27
red_lines_touched: [熱迴圈 0 LLM (#1), 證據分級 (#2), robots/授權 (#7), 對自己誠實 (#8), docs-first (#9)]
supersedes: docs/design/2026-07-27-published-is-a-proxy.md 的〈階段 D〉初稿
---

# 模型演變時間線

> **一句話**：這一層回答「這個模型什麼時候發布、現在是什麼狀態」，
> 而那是關於**世界**的陳述；`coverage` 三態回答「事情發生時我們在不在線上」，
> 那是關於**我們**的陳述。兩者分屬兩層，互不冒充，也不共用字樣。

---

## 0. 這一層是被兩次錯誤逼出來的

**第一次**（2026-07-27 上午）：對外站上一則事件頁的模型名稱、發布時間、
先後順序都是錯的。根因是 `adapt_sitemap` 把 slug 反推成標題、把 `lastmod`
當成 `published`（`docs/design/2026-07-27-published-is-a-proxy.md`）。

**第二次**（同日下午）：本文件的作者查完 `platform.claude.com` 的**模型總覽頁**
（只有知識截止與訓練截止，沒有 release date）、查完三家的 feed（沒有）、
查完文章頁的 metadata（三個機器可讀日期全部 ABSENT），於是下了結論：

> 「唯一存在的 Tier-1 事實，就是發布頁上人看得到的標題與日期。」

**那個結論是錯的，而且錯在同一個地方：把「我查過的幾個表面」當成「所有表面」。**
第三個表面是 **release notes / changelog**，四家都有、都有逐條日期、
而且從 2023–2024 年就開始記：

| 廠商 | 頁面 | 起點 | 日期格式 |
|---|---|---|---|
| Anthropic | `platform.claude.com/docs/en/release-notes/api` | 2024-05 | `### July 24, 2026` |
| OpenAI | `developers.openai.com/api/docs/changelog` | 2023-10 | `Jul 22, 2026` |
| Google | `ai.google.dev/gemini-api/docs/changelog` | — | `June 1, 2026` |
| xAI | `docs.x.ai/developers/release-notes` | 2024-11 | **`July 23`（沒有年份）** |

「我沒找到」與「不存在」是兩個不同的宣稱——這個 repo 已經為了同一件事
在 `robots_unknown` 上立過界線（紅線 7），本文件的作者在**同一天內**
於兩個不同的維度上各犯一次。這一層存在的部分理由，就是把那個判斷從人身上
移到結構上。

---

## 1. 三類來源，各自只能回答一種問題

分類沿用 2026-07-27 使用者提出的架構，本文件的貢獻是**把每一類能回答與
不能回答的問題釘死**——混用是這個 repo 反覆在抓的那隻病的入口。

### 甲類：官方 release notes / changelog／model card ＝**歷史**

**能回答**：某個日期發生了什麼版本異動。
**不能回答**：現在還能不能用（changelog 只記事件，不記當下狀態）。

四家的頁面見上表；Meta 走 GitHub API
（`meta-llama/llama-models` 的 `models/*/MODEL_CARD.md`），
`pulse-probe.py` 已經有 `adapt_github_releases`，是同一條路。

**這一類是時間線的唯一資料來源。** 別的類別都不建立列，只修改列。

### 乙類：目錄 API（`GET /v1/models`）＝**當下狀態**

**能回答**：現在有哪些 model id 可用、alias 指向誰。
**不能回答**：歷史。目錄 API 沒有已下線的模型——**一個模型下線之後，
它在這個 API 裡的痕跡跟從未存在過一模一樣。**

所以它的用途只有一個：**把甲類建出來的列標上「今天還在不在」**，
而且必須存成獨立欄位（`still_listed_at`），不可以回頭改 `released_on`。

**未決**：`_config/` 目前沒有任何 secret，CI 也沒有掛金鑰。乙類要動工得先
拍板「這個專案要不要持有廠商 API key」——那不只是工程問題。
**在拍板之前，乙類不接，時間線只用甲類，並且在頁面上寫明沒有做當下驗證。**

### 丙類：模型推論 API ＝**不採用**

使用者的建議裡有一步是「用單一 LLM 做正規化／判斷 Preview 還是 GA」。
**這一步不做，理由是紅線 1：熱迴圈 0 LLM。**

而且不做並不會損失什麼，因為那件事**本來就是字面判斷**。實測四家的
changelog 用的是同一組動詞，逐字可判：

```
released as GA / generally available   → ga
public preview / preview / beta        → preview
shut down / shutdown / retired         → shutdown
deprecated / deprecation               → deprecated
（都不是）                              → unknown
```

**「需要 LLM」與「我還沒去讀那些字」是兩件事。** 把後者說成前者，
就是用一個比事實寬鬆的說法去代表事實——這份 repo 的老病。

**但書寫在這裡而不是註解裡**：`lifecycle_of()` 回 `unknown` 的比例是
要被量測、要被印出來的（見第 4 節）。若那個比例高到讓這一層失去意義，
正確的動作是**回頭補動詞表**或承認這條路不通，**不是**把 LLM 接進熱迴圈。
若真的有一天要接，走 `pulse-*-prep` / `pulse-*-apply` 那個既有的分離模式
（人／LLM 產出檔案，apply 端純規則），熱迴圈仍然是 0 LLM。

---

## 2. 一列的欄位，以及每一格只能從哪裡來

```yaml
product_line:      claude          # _config/entities.yaml 的 id，不是自由字串
model_id:          claude-opus-5   # 廠商的正式 id，來自 changelog 原文
display_name:      Claude Opus 5   # 來自 changelog 原文；沒有就留 null
happened_on:       2026-07-24      # changelog 的條目日期
date_precision:    day             # 封閉集：day | month | none
date_year_source:  explicit        # 封閉集：explicit | section | none
lifecycle:         ga              # 封閉集：ga | preview | shutdown | deprecated | unknown
source_url:        https://...     # Tier-1，逐列一條
source_tier:       1               # 只收 1
first_fetch_at:    2026-07-28T...  # 我們第一次讀到這一頁的時間
```

三條硬規矩，每一條都對應一個已經犯過的錯：

**（一）`source_url` 缺，這一列就不存在。** 不留「待補」的空列——
空列在畫面上跟已知的列長得一樣。

**（二）`date_year_source` 是為 xAI 存在的，而且它必須是欄位不是註解。**
`docs.x.ai` 的條目印「July 23」，**沒有年份**。年份只能從章節標題或條目順序
推得，那是**推導**不是原文。推導值不可以住在事實的名字裡——這正是
`_slug_to_title` 那條的教訓，換一個維度重演。

**（三）`date_precision` 跟值一起存。** 「June 2026」只到月，
存成 `2026-06-01` 就是編造精度。

---

## 3. 這一層跟 Event 層的關係：**只連結，不合併**

模型時間線的一列**不是** Event，不進 `Events/`，不參與聚類、不進 readiness
gate、不算 `value`／`heat`／`lead_days`。理由有兩個，第二個比較重要：

1. 它沒有 `coverage`。它不是我們觀測到的，是廠商自己記的帳。
2. **`lead_days` 是這個系統自稱唯一的產物**，而它的定義是
   「我們比別人早幾天看到」。把一份我們**回頭去讀的官方帳本**餵進去，
   那個數字就變成「官方的帳本比官方的公告早幾天」——一句沒有意義的話，
   而且它會**看起來很好看**。

連結的方式是單向的：Event 頁可以指到時間線上的一列（「這則講的是
`claude-opus-5`，它在時間線上的位置在這裡」），時間線不指回 Event。

**畫面上的字樣**：時間線頁面要寫「廠商 release notes 的整理，
不是本系統觀測到的事件」。**不寫「回填」**——回填是 `coverage` 的詞，
講的是我們的抓取器在不在線上，貼到這裡是反方向的冒充。
（這正是使用者說「時間線不需要補那句回填」的正確實作：
不是把話拿掉，是換成對的那一句。）

---

## 4. 必須被量測、而且印出來的三個比率

沒有這三個數字，這一層會安靜地退化成一份看起來很完整的表。

| 比率 | 定義 | 為什麼非印不可 |
|---|---|---|
| `unknown_lifecycle_rate` | `lifecycle == unknown` 的列 ÷ 全部 | 高＝動詞表沒跟上，而表看起來一樣完整 |
| `derived_year_rate` | `date_year_source != explicit` ÷ 全部 | xAI 那類；高＝時間線的年份有一半是我們推的 |
| `unmatched_model_rate` | 條目提到版本號但對不上 `entities.yaml` ÷ 條目數 | 高＝新產品線出現了而字典沒補（`dictgaps` 的同類） |

三個都印在時間線頁的頁首，跟 `heat` 印「未量測」同一個做法。

---

## 5. 動工順序，以及每一步的前置驗證

**這一層的每一步都綁一個驗證，而驗證不在開發容器跑**——開發容器有
egress allowlist，量到的是別的問題（`published-is-a-proxy` 的 C-4′）。

| 步 | 做什麼 | 前置驗證 | 在哪跑 |
|---|---|---|---|
| 1 | 純函式層 `lib/modelline.py` | 離線 fixture（本頁第 1 節的實測字串） | selftest |
| 2 | 四家 changelog 的可抓性與原始 HTML | `verify-article-metadata.py --preset release-notes` | **CI** |
| 3 | HTML → 條目的切分 | 步 2 的 `c4-report.json` 真 bytes | 有真 bytes 之後才寫 |
| 4 | 落地與渲染 | 步 3 的解析率 + 第 4 節三個比率 | CI |

**步 3 刻意不先寫。** 對著想像的標記寫解析器，寫出來的東西會通過我自己編的
測試、然後在真頁面上失敗——那是把「我測過了」變成一個比事實寬鬆的說法。

---

## 5′. 實測：步 1 與步 3（Anthropic 那一家）已經做完，數字在這裡

2026-07-27。`verify-article-metadata.py --preset release-notes --save-html`
在開發容器裡對四家跑，**只有 `platform.claude.com` 通得過**
（1,436,122 bytes，`ok`），另外三家被 egress allowlist 擋住、判 `no_verdict`
——所以底下的數字只涵蓋 Anthropic，另外三家仍然是**未驗**。

`lib/modelline.py` 對那份真 HTML 的結果：

```
rows                     248        （2024-05-10 → 2026-07-24，26 個月）
日期解析失敗              0
derived_year_rate      0.0000       （每一列的年份都是原文寫的）
unmatched_model_rate   0.0444       （90 條在講版本的裡面，4 條對不上字典）
unknown_lifecycle_rate 0.4677
ambiguous_lifecycle_rate 0.1694
```

**這一節真正的內容不是那六個數字，是拿到它們之前踩到的七個洞。**
每一個都是「列數、日期格式、解析率全都正常，只有列跟事實的關係是錯的」：

| # | 洞 | 後果 | 現在守它的 |
|---|---|---|---|
| 1 | 錨點不認序數 `july-9th-2024` | 2024-05 至 2025-04 每一條蓋上同一天 | M112、`anchor_gap()` |
| 2 | 沒解 HTML entity | `We&#x27;ve launched` 對不上動詞表 | M113 |
| 3 | lifecycle 逐**日**判 | 一條 beta 把整天染成 preview | M114 的鄰居、逐 `<li>` 測試 |
| 4 | 目錄項當條目 | **124 列**（全頁三分之一）落在同一天 | M115 |
| 5 | `claude.com` / `claude.ai` 當 model id | 網域進時間線 | M116 |
| 6 | 缺年份時拿今年補 | 兩年的條目堆到同一年 | M117 |
| 7 | unmatched 的分母用全部條目 | 0.79，量到的是「有多少條不在講模型」 | M118 |

**第 3 與第 7 是我自己在第一版寫進去的代理指標**——在一份專門講「不要用代理
指標代表事實」的規格底下，第一版的實作犯了兩次。第 7 修好之後 0.79 → 0.044。

`unknown_lifecycle_rate` 0.47 不是缺陷，是**這一頁大半條目本來就不在講模型
生命週期**（SDK 更新、定價、文件）。時間線只收有模型且 lifecycle 明確的列；
其餘留在原始資料裡，不進表。`ambiguous` 0.17 是要人看的那一格，
不是要被靜音的那一格。

**下一步**：在 CI 跑 `--preset release-notes`，把另外三家的真 bytes 帶回來。
在那之前，OpenAI / Google / xAI 三家的切分器不寫（第 5 節步 3）。

---

## 6. 明確不做

- **不建 YAML 資料檔**（在步 2 綠燈之前）。現在建＝先寫一份靠記憶填的表，
  然後永遠沒有人回來換掉它。
- **不收第三方時間軸站**。2026-07-27 搜尋當天前排就有互相矛盾的兩篇
  （「Claude Opus 5 尚未發布」與「Sonnet 5 已於 6/30 發布」），
  而我們的 Tier-1 sitemap 上 `/news/claude-opus-5` 的 lastmod 是 07-25。
  Tier-3 只能當「有這回事」的線索，不能填進看起來像事實的表。
- **不接乙類目錄 API**（在 secret 政策拍板之前）。
- **不接丙類推論 API**（紅線 1；且第 1 節已證明不需要）。
- **不把時間線的列寫進 `Events/`**（第 3 節）。
