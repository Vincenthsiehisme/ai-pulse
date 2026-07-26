# heat 有 63% 的權重從來沒有被量到過

實測日期：2026-07-26，樣本：vault 內全部 48 個 Event。

這份只記錄量到的東西，不改公式、不改門檻。改排名規則前要先有這份（紅線 9
docs-first），改不改是另一個決定。

> **追記（同日稍晚，`fix/heat-claims-a-measurement`）**：上面那個「另一個決定」
> 已經做了，而且做的過程推翻了這份筆記的兩個推論。表格與分佈數字仍然成立
> （那是實測），但下面兩處結論是錯的，已在原地標出：
>
> 1. 「heat 的可達上限約 48 …… 結構性不可達」——現在不成立了，而且它答錯了問題。
> 2. 「這三項不是壞掉，是**輸入端沒有東西**」——不對。是 `pulse-cluster.py:144`
>    呼叫 `scoring.score_event()` 時第四個參數寫死 `metrics=[]`：
>    **不是輸入端沒東西，是連接線沒有接。**
>
> 現行行為與完整決策過程見 `references/readiness-gate.md`。

## 量到什麼

`scripts/lib/scoring.py` 的 heat：

```
heat = _logscale(authors,     80)  * 30
     + _logscale(tweets,     300)  * 20
     + min(independent_count,  5)  *  8
     + min(platforms,          4)  *  7
     + min(regions,            3)  *  6
     + freshness                   *  0.08
```

48 個 Event 的因子分佈：

| 因子 | 權重 | 非零筆數 | 最大值 |
|---|---|---|---|
| uniqueAuthors | 30 | 0 / 48 | 0 |
| velocity（tweets） | 20 | 0 / 48 | 0 |
| independentSources | 8 | 48 / 48 | 3 |
| platformBreadth | 7 | 0 / 48 | 0 |
| regionBreadth | 6 | 0 / 48 | 0 |
| freshness | 0.08 | 有值 | — |

`independentSources` 也幾乎不動：47 / 48 是 1，只有 `evt-2026-07-25-0fa594`
（Claude Opus 5）是 3。

## 推論：heat 目前不是量出來的

恆為 0 的四項合計 63 分權重。實際會動的只剩 `independentSources * 8` 與
`freshness * 0.08`，兩者上限各約 40 與 8。所以：

- 實測 heat 最大值 **32**，正好等於 `3 * 8 + freshness 8`。
- 47 個 `independentSources = 1` 的 Event，heat 落在 8–14，差異全部來自 freshness。

**heat 現在等於「獨立來源數的線性換算 + 新鮮度」，不是傳播熱度。** 這是紅線 8
（對自己誠實）要處理的東西：欄位名稱說的是熱度，量到的是別的。

## 連帶：`unsupported_heat` 這條防線是空的

`_config/gate.yaml`：

```yaml
heat_threshold: 70              # 超過此熱度才檢查熱度支撐
heat_min_independent_sources: 2
heat_min_platform_breadth: 2
```

~~heat 的可達上限約 48（`5 * 8 + 8`），永遠碰不到 70，所以熱度支撐檢查從來沒有
執行過一次。~~ 同一段的 `translation_chain`（`excluded_from: [independent_sources,
heat]`）也一樣——它防的是虛增 heat 繞過 `unsupported_heat`，但那條路本來就沒開。

~~門檻不是設錯，是它預設的輸入不存在。~~

**訂正（同日稍晚）**：「碰不到 70」這件事本身是對的，但把它寫成結論是搞錯了
主詞。可達上限是 48 還是 32 都不重要——重要的是那個數字**根本不是量出來的**。
盯著上限看，會很自然地想到「那就把門檻降到 45」，而那是把手工分數包裝成已測量
熱度（紅線 4 明文禁止）。

現在（2026-07-26 起）四項傳播輸入全 0 時 `scoring.score_event()` 回
`heat: None`，不是 48、不是 32、也不是 0——0 會被讀成「量過了，很冷」，比不印
更難察覺。`unsupported_heat` 因此依然走不到，但那是**休眠等社群線（M3）**，
不是空防線：`selftest.py` 兩個方向都釘住了（`metrics=[]` 時 `None`；四項餵滿時
heat 跨得過 70）。另外新增 `unmeasured_heat` 擋「有 heat 數字但
`score_factors.propagationSignals` 為 0」。規格：`references/readiness-gate.md`。

## 為什麼三個因子恆為 0

- `platformBreadth` / `uniqueAuthors` / `velocity` 需要社群平台的傳播證據。目前
  24 條來源全是 blog / newsroom / release feed / HN，形態只有一種，量不出廣度。
- `regionBreadth` 需要跨地域的獨立報導。官方線的 EU 三條（`src-ec-digital-strategy`、
  `src-consilium-press`、`src-ep-itre`）都是 `dormant`，CN 線只有 `src-qwen-blog`，
  實際只剩 US。

~~所以這三項不是壞掉，是**輸入端沒有東西**。補來源比改公式優先。~~

**訂正（同日稍晚）**：這段推論是錯的，而且錯得有代價——它會讓人以為「補來源」
就能讓那三項動起來。實際上 `pulse-cluster.py:144` 呼叫 `scoring.score_event()`
時第四個參數寫死 `metrics=[]`，**連接線根本沒有接**。今天把 24 條來源加到
240 條，那三項還是 0。

上面對「為什麼沒有社群資料」的描述本身沒錯（來源形態確實只有一種），但它是
第二個原因，不是第一個。第一個原因是那行寫死的 `metrics=[]`——先接線，
補來源才有意義。

## 刻意沒做的事

沒有改 heat 的權重、沒有動 `gate.yaml` 的 70、沒有把恆零因子從公式裡拿掉。
把 30 分的權重重新分配給還活著的因子，會讓每一個既有 Event 的 heat 換一個
數字，也就是讓磁碟上已經存在的資料換一個結局——那要另外一個 PR，附遷移與
回滾（CONTRIBUTING「一定要走 PR 而且要特別小心的三類」）。
