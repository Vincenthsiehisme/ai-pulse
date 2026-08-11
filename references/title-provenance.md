# 標題是哪裡來的 —— 以及哪些標題不是原文

> 消費者：`scripts/pulse-probe._slug_to_title()` / `adapt_sitemap()`、
> `scripts/lib/cluster.event_fingerprint()`、`title_tokens()`。
> 規格先於實作（紅線 9）。

## 兩種標題，下游分不出來

`_corpus/` 與 `_probe/*/signals-*.jsonl` 的 `title` 欄位有兩種來源：

```
adapter: rss / json / atom   →  原文標題（發布方自己寫的）
adapter: sitemap             →  從 URL 尾段**推導**出來的
```

sitemap.xml 沒有標題欄位，只有 `<loc>`。要嘛去抓內文、要嘛從 slug 還原。
抓內文超出這幾條來源的 `license_note: titles + links only`，所以選還原。

**而 `title` 這個欄位名不會告訴任何下游消費者它是推導來的。**
目前用 sitemap 的三條：`src-anthropic-news`、`src-xai-news`、`src-mistral-news`。

## 2026-08-12：還原不準的代價沒有被吸收，它傳下去了

`_slug_to_title()` 原本的 docstring 寫著：

> 還原不準的代價由 cluster 的實體比對吸收，不由編造吸收。

這句話當時是對的判斷，**但這次量到的是：cluster 的實體比對正是被這個不準
打壞的那一層。** 代價沒有被吸收，它一路走到 `confidence`。

### URL 裡的 `-` 有兩個意思

```
/news/claude-opus-4-5
       ↑     ↑  ↑ ↑
       斷詞  斷詞 小數點
```

`re.split(r"[-_]+", seg)` 分不出來，於是：

```
/news/claude-opus-4-5   →   "Claude Opus 4 5"        （小數點沒了）
```

### 版號會整個消失

第一層：`event_fingerprint()` 的版號組是 `(\d+(?:\.\d+)?)`，
吃到第一個整數就停——`Claude Opus 4 5` 的 `5` 前面隔著空白，不在組裡：

```
"Claude Opus 4.5"  →  anthropic:claude:opus:4.5     ✓
"Claude Opus 4 5"  →  anthropic:claude:opus:4       ✗ 4.5 / 4.6 / 4.7 / 4.8 全塌成同一鍵
```

第二層：`title_tokens()` 的 `len(t) > 1` 把單字元丟掉：

```
"Claude Opus 5"    →  {claude, opus}
"Claude Opus 4 5"  →  {claude, opus}                 相似度 1.00
```

兩層疊起來的結果，是 vault 裡 129 筆證據有 6 筆掛錯，全部 `relevance: 100`。
完整因果鏈與實測見 `references/attach-rule.md`〈身分否決〉。

## 還原規則現在做了什麼

```
「1–2 位數 - 1–2 位數」且左右都是純數字   →  合併成小數點
其餘的 -                                   →  照舊當斷詞符
```

```
claude-opus-4-5   →  Claude Opus 4.5
grok-4-5-everywhere → Grok 4.5 Everywhere
2026-08-03        →  2026 08 03      ← 不動，年份是 4 位數
glp-1-123000637   →  Glp 1 123000637 ← 不動，右邊 9 位數
```

**左邊限制 1–2 位數是為了擋年份**（語料 857 個 URL 裡有 2 個年份型 slug）。
右邊也限制 1–2 位數是為了擋文章編號（`...-1-123000637.html` 這種）。

實測血徑：857 個不重複 URL 裡「數字-數字」出現 12 次，
版本型 10（anthropic 7、xai 2、openai 1）、年份型 2。

## 這條規則做不到什麼

**三段版號**（`gemini-2-5-pro` 這種如果出現）只會合併前兩段成 `2.5`，
第三段照舊分開——目前語料裡沒有這種形狀，所以沒有為它加規則。
真的出現的時候會表現成「版號少了一截」，不是「版號錯了」，
而 fingerprint 仍然會因為前兩段不同而正確否決。

**沒有小數點的版號差異**（`claude-opus-4` vs `claude-opus-5`）本來就沒問題，
這條規則不碰它們。

**原文標題本身寫錯版號**——這條規則救不了，也不該救。

## 歷史資料不會自己變好

`_corpus/` 與 `_probe/*/signals-*.jsonl` 裡已經存下來的 `title` 仍然是舊的
（`Claude Opus 4 5`）。這一層的修正**只影響之後抓到的**。

所以歷史修復（那一輪重新聚類）要自己處理這件事：對 `adapter: sitemap` 的來源，
拿存下來的 `url` 重跑一次 `_slug_to_title()`，而不是直接用存下來的 `title`。
不這樣做的話，重新聚類會看到四個 `Claude Opus 4 5/6/7/8`、
fingerprint 全部是 `opus:4`，於是它們會合併成一則——**修完的規則配上沒修的資料，
產出的是本文開頭那個 relevance 100 的形狀。**

## 為什麼不改成去抓內文標題

抓內文會拿到 `<title>` 或 `og:title`，準確得多。但這三條來源的
`license_note` 是 `titles + links only`，抓內文等於改變我們對這幾個站的取用方式，
那是一個要重新判斷 robots 與授權的決定，不是一個 bug fix。

如果將來要做，觸發條件是**這幾條來源的 license_note 先改**，
而不是「還原又不準了」。
