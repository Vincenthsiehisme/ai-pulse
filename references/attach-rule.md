# 聚類層：attach 規則 —— 一則新聞什麼時候算「同一件事」

> 消費者：`scripts/lib/cluster.belongs_to_event()`、`scripts/pulse-cluster.py`、
> `_config/gate.yaml` 的 `cluster.title_similarity_min`。
> 規格先於實作（紅線 9）。

## 規則本體

```
時間差 > 21 天                         → 不 attach（硬上限）
fingerprint 相同 且 facet bucket 相同  → attach（窗口 21 天，incident 7 天）
其餘                                    → 96 小時內 且 標題相似度 ≥ 門檻
```

相似度是標題 token 的 Jaccard（`title_similarity`），停用詞已剔除。

## 2026-08-11：這條規則被實測過，結果很難看

P0-e 蒐集 **14 篇真實存在的第三方後續報導**（對應 vault 裡 7 則已發布事件，
每一篇的發布日都逐篇查證），用當時的規則跑一次：

```
attach 2/14 = 14%
```

而真正的問題不是這個數字：

> **那 2 篇 attach 的，兩篇都是逐字轉載（標題相似度 1.00）。
> 12 篇真的重寫過的第三方報導，一篇都沒 attach。**

也就是說，這條規則**不是「抓不到獨立佐證」，是「只抓得到假的獨立佐證」**。
它挑掉了所有真的重寫，只留下複製貼上——而複製貼上正是
`suspected_reposts` 要防的東西。

### 三個量出來的事實，其中兩個推翻了原本的假設

**一、96 小時窗口不是瓶頸。** 窗口 × 門檻的偽陽性矩陣（負對照＝其餘 85 則已發布事件）：

```
      窗口    0.46          0.35          0.30          0.25          0.20
     96h    2/14 誤0      4/14 誤0      7/14 誤0      8/14 誤0     11/14 誤0
     7 天    2/14 誤0      4/14 誤0      7/14 誤0      8/14 誤1     11/14 誤1
    14 天    2/14 誤0      4/14 誤0      7/14 誤0      8/14 誤1     11/14 誤1
    21 天    2/14 誤0      4/14 誤0      7/14 誤0      8/14 誤1     11/14 誤1
```

同一列左右變化很大，**同一欄上下完全不動**。守門的是門檻，不是窗口。
所以這一輪不動窗口——放寬它一篇都救不回來。

**二、路徑 A（fingerprint）對這 14 篇完全沒作用。** 14 組 fingerprint 全部是
`None`。`_FP_PATTERNS` 是一份**寫死的 11 個模型家族白名單**，Muse Glimmer 不在裡面、
Alpamayo 2 Super 不在裡面。**每一個新出現的模型家族，預設就走路徑 B。**
所以「對 facet bucket 開例外」這個候選改法應該從清單移除——facet 判斷根本沒被執行到。

**三、放寬門檻的偽陽性代價，在這份語料上是零。** 0.46 → 0.20 對 85 則負對照
一次都沒誤黏（96h 窗口）。唯一那筆誤黏出現在 21 天窗口 + 0.25：
`Meta Open Sources Muse Glimmer: A 30B Agentic AI Model` 誤黏到
`Orchard: An open framework for scalable agentic AI`（相似度 0.25）——
共同詞是 `open` / `agentic` / `ai`，是可預期的失敗形狀：**通用詞疊出來的相似度**。

## 門檻定在 0.30，以及為什麼不定更低

```
0.46  2/14   ← 改之前
0.35  4/14
0.30  7/14   ← 現在
0.25  8/14   誤黏 1（21 天窗口下）
0.20 11/14   誤黏 1
```

**0.30 是「還沒開始付代價」的最後一格。** 0.25 以下開始出現誤黏，
而誤黏的代價不對稱：漏掉一篇佐證只是少一個聲音，黏錯一篇會讓
`independent_sources` 記一個不存在的獨立來源——那個數字會進 frontmatter、
進看板、進 KPI，事後分不出哪些是虛的。

門檻搬進 `_config/gate.yaml` 的 `cluster.title_similarity_min`。
在此之前它是 `belongs_to_event()` 的**寫死預設參數**，而這個 repo 的其他門檻
都在設定檔裡、旁邊有一行註解寫消費者是誰。

**設定檔壞掉時退回 0.46 而不是 0.30**——往嚴的方向倒，同
`lib/dictgaps.thresholds()`。退回舊行為是可預期的損失（少黏一些），
退到更鬆是不可預期的汙染。

## 順序：轉載守門必須跟門檻一起上，不能晚一步

降門檻會讓更多東西 attach，**包含更多逐字轉載**。而 2026-08-11 量到：

```
同語言（en/en，逐字轉載）→ suspected_reposts 判成轉載的：空集合＝沒攔到
跨語言（en/zh）           → 判成轉載的：{1}
```

`suspected_reposts()` 的第一個條件就是「語言不同」（`lib/cluster.py`
`if not la or not lb or la == lb: continue`）——它只認**跨語言翻譯**，
同語言的複製貼上不在它的定義裡。

所以 `evidence.verbatim_repost` 這一格必須存在，而且**不能晚於門檻調整上線**。
中間那段空窗期 `independent_sources` 會虛胖，而虛胖的數字混進帳本之後
分不出哪些是虛的。這一輪兩件事在同一個 PR、轉載守門排在前一個 commit。

## 這條規則現在仍然做不到什麼

三篇在任何門檻下都救不回來：

```
Kingy AI「Muse Glimmer 30B: Benchmarks, Hardware, Pricing」   相似度 0.18
Fortune「OpenAI says its upcoming Astra model may have…」     相似度 0.11
Technology.org「OpenAI Flags Critical Cyber Risk in Astra」   相似度 0.18
```

第三篇特別值得看：`OpenAI Flags Critical Cyber Risk in Astra Model` 對
`Responding to the next frontier of critical cyber capabilities`——
人讀兩秒就知道是同一件事，共同 token 只有 `critical` 和 `cyber`。

**標題 token Jaccard 有一個地板**：媒體改寫標題時本來就在換字。
把門檻壓到 0.15 那三篇也只救回一篇，而 0.15 已經開始誤黏。

這三篇要的不是更鬆的門檻，是**別的訊號**——實體集合、內文有沒有連回官方 URL、
同一天同一批實體。那是下一輪的題目，不是調一個數字能解決的。

## 這次改動影響的是未來，不是歷史

`pulse-cluster.py` 每一班只對**新進的 signal** 跑 attach 判定，
既有 Event 不會重新聚類。所以 KPI 2（`independent_sources ≥ 2` 的比例）
不會在上線當天跳動，要等新事件累積。**上線後看到數字沒動，那是預期，不是壞了。**

## 回滾

把 `cluster.title_similarity_min` 改回 `0.46` 即可，不需要動碼。
`evidence.verbatim_repost.enabled: false` 可以單獨關掉轉載守門——
但**不要在門檻仍是 0.30 的情況下關它**，那正是上面那段空窗期的形狀。
