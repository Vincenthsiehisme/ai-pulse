# 聚類層：attach 規則 —— 一則新聞什麼時候算「同一件事」

> 消費者：`scripts/lib/cluster.belongs_to_event()`、`scripts/pulse-cluster.py`、
> `_config/gate.yaml` 的 `cluster.title_similarity_min`。
> 規格先於實作（紅線 9）。

## 規則本體

```
時間差 > 21 天                         → 不 attach（硬上限）
fingerprint 兩邊都有 且 不相同         → 不 attach（身分否決，2026-08-12 加）
fingerprint 相同 且 facet bucket 相同  → attach（窗口 21 天，incident 7 天）
其餘                                    → 96 小時內 且 標題相似度 ≥ 門檻
```

相似度是標題 token 的 Jaccard（`title_similarity`），停用詞已剔除。

## 2026-08-12：身分否決 —— 結構化事實不准被模糊相似覆寫

第二條是後來補的。在此之前的規則是「fingerprint **相同**就走路徑 A」，
而不同的時候**沒有任何處置**——直接落到路徑 B 的標題相似度去重新裁決。

於是同一份身分訊號，前面說「這是兩個版本」，後面又允許相似度說「其實一樣」。

### 這不是新規則，是一條已經寫下來的規則漏了一個消費端

`lib/cluster.suspected_reposts()` 早就有這條：

```python
fa, fb = a.get("fingerprint"), b.get("fingerprint")
if fa and fb and fa != fb:
    continue          # 不同版本，不可能互為翻譯
```

轉載偵測認這個不變式，attach 判定不認。跟 `SECTIONS`、`RUN_LIFECYCLES`
那兩次搬家是同一個病的形態：一條規則有兩個消費端，只釘住了一個。

### 它讓什麼東西進了 vault

`evt-2026-07-25-0fa594`「Claude Opus 5」，全 vault confidence 最高的那則（100）：

```
primary_evidence: 5
  rel=100  Claude Opus 5      ← 真的
  rel=100  Claude Opus 4 7    ← 另一次發布
  rel=100  Claude Opus 4 5    ← 另一次發布
  rel=100  Claude Opus 4 8    ← 另一次發布
  rel=100  Claude Opus 4 6    ← 另一次發布
```

真正的 primary evidence 是 **1**。`evt-2026-07-22-09b47d`「Claude Sonnet 5」
同樣的形狀（3 筆裡 2 筆是 4.5 / 4.6）。全 vault 129 筆證據裡有 **6 筆**是這個形狀。

它們的相似度是 **1.00**——不是「有點像所以黏上去」，是 token 集合完全相同
（理由見 `references/title-provenance.md`〈版號會整個消失〉）。

### 實測：863 signal × 106 事件，誤殺 0

```
                       加 veto 前   加 veto 後
多候選                    10            1
零候選                   745          751      （+6 = 那六筆錯的）
被 veto 掉的配對           —           24
其中誤殺（本來對的）        —            0
```

24 筆全部是跨家族或跨版本（`opus:5 ≠ sonnet:5`、`opus:4 ≠ opus:5`、
`sonnet:4 ≠ haiku:4` …）。**一筆都沒殺錯。**

### 端到端對照：不修的話，下一班會再多掛六筆

同一天（`--day 2026-08-10`、232 則訊號）跑兩次，一次用改前的碼、一次用改後的：

```
                事件數   證據總筆數
跑之前            106       129
對照（舊碼）      106       138     +9 筆證據、+0 則事件
實驗（新碼）      108       138     +9 筆證據、+2 則事件
```

**證據總筆數一樣，差別在它們去了哪裡。** 舊碼把其中 6 筆全部堆到
`evt-2026-07-22-09b47d`「Claude Sonnet 5」身上：

```
evt-2026-07-22-09b47d「Claude Sonnet 5」  primary_evidence  3 → 10
    rel=33  Claude Opus 5
    rel=33  Claude Opus 4 7
    rel=33  Claude Opus 4 5
    rel=33  Claude Opus 4 8
    rel=33  Claude Haiku 4 5
    rel=33  Claude Opus 4 6
```

新碼把它們分流成兩則新事件，同一格是 `primary_evidence: 4`。

也就是說這不只是「歷史上有 6 筆髒的」——**不修的話，這個形狀每一班都在長。**

### 為什麼 veto 必須跟 slug 還原同一個 commit

`Claude Opus 4 5 / 4 6 / 4 7 / 4 8` 的 fingerprint 在還原修好之前**全部是
`anthropic:claude:opus:4`**（`_FP_PATTERNS` 的版號組吃到第一個整數就停）。
veto 對它們**之間**不觸發，而它們會改走路徑 A（同 fingerprint、同 facet
bucket、21 天窗內），實測六對全部 attach、relevance 全部 100：

```
只加 veto、不修 slug：
  4 8 ⟷ 4 7   attach=True  relevance=100
  4 8 ⟷ 4 6   attach=True  relevance=100
  4 8 ⟷ 4 5   attach=True  relevance=100
  4 7 ⟷ 4 6   attach=True  relevance=100
  4 7 ⟷ 4 5   attach=True  relevance=100
  4 6 ⟷ 4 5   attach=True  relevance=100
```

也就是說：**「Opus 4.x 不得進 Opus 5」會通過，而錯誤只是換了個形狀。**
一個只驗前者的成功標準會回報成功。所以本輪的成功標準有兩條，缺一不可：

```
Claude Opus 4.x                  不得進 Claude Opus 5
Claude Opus 4.5 / 4.6 / 4.7 / 4.8  不得互相合併
```

補上還原修正之後，上面六對與四筆對 Opus 5 的判定全部是 `False`。

### 這一輪**不**動 tokenizer

保留數字並不能解決這件事：

```
{claude, opus, 5}  vs  {claude, opus, 4, 7}   → 2/5 = 0.40
{claude, opus, 5}  vs  {claude, opus, 4.7}    → 2/4 = 0.50
門檻 0.30 → 兩種都還是 attach
```

**tokenizer 是必要條件、不是充分條件。** 而且修好 slug 之後
`Claude Opus 4.5` 的 token 集合仍然是 `{claude, opus}`（`.` 被
`_TOKEN_STRIP` 切開、剩下的單字元被 `len(t) > 1` 丟掉），相似度仍然 1.00——
**但那已經不當家了**，因為 veto 在它之前就否決掉。分工是：

```
slug 還原  →  讓 fingerprint 正確
veto      →  讓 fingerprint 蓋過 similarity
tokenizer →  只影響「兩邊至少一邊沒有 fingerprint」時的 fallback 品質與 relevance 數字
```

tokenizer 因此延後處理，等候選排名上線後再依 relevance 品質決定要不要動。

### 邊界：只有兩邊都有 fingerprint 才否決

單邊有、單邊沒有 → **不否決**，照走路徑 B。因為 `_FP_PATTERNS` 是一份寫死的
11 個模型家族白名單（Grok 不在裡面、Muse Glimmer 不在裡面），`None` 的意思是
「這支正則不認得」，不是「這不是那個模型」。拿「我不認得」去否決，
會把整批第三方報導砍掉——那正是 P0-e 已經量到的 12/14 黏不上的族群。

往嚴的方向倒在這裡是**只在兩邊都說得出身分、而且說的不一樣**時才動手。

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

## 2026-08-12 下午：最好的那個，分不出來就不掛

身分否決解決的是「這兩個明明是不同版本」。它解決不了另一個問題：
**一則 signal 同時符合好幾個 Event 的時候，挑哪一個。**

在此之前 `attach_target()` 是 `next(c for c in events if belongs_to_event(...))`。
`events` 來自 `sorted(Events/*.md)`，檔名是 `evt-<日期>-<hash>`——所以
「第一個符合的」實際上是**最舊的那個符合的**，而「最舊」跟「最像」無關。

這**不是**不確定性。同樣的輸入給同樣的輸出，這條鏈仍然是 deterministic 的。
它是**確定地挑錯**，而那更難發現：不確定性可以用「跑兩次比對」抓出來，
確定地挑錯跑一百次都一樣綠。

### 排名這一半，今天量不到任何效果——這句話要寫在規格裡

實測 934 訊號 × 125 事件（門檻 0.30，身分否決已上線）：

```
多候選                       1 則
first-match ≠ 最佳候選        0
語意鍵完全平手                1
```

**`0`。** 身分否決已經把排名會修的那些全修掉了。

所以排名這一半是**結構修正，不是量出來的修正**。留著它的理由有兩個，
都不是「它改善了什麼數字」：

1. 「挑檔名最前面的」本來就不是一個判斷
2. 候選蒐集本來就是平手守門的前置，排名的邊際成本是零

拿「0/106 則中文標題」擋掉 CJK n-gram 的那把尺，也要對自己用。

### 平手守門有一個客戶，而且是 9 路平手

```
訊號「Claude For Teachers」
   fp=0 facet=1 sim=0.33   0.2h  「Claude Sonnet 4.6」
   fp=0 facet=1 sim=0.33   1.5h  「Claude Sonnet 4.5」
   fp=0 facet=1 sim=0.33   1.6h  「Claude Sonnet 5」
   fp=0 facet=1 sim=0.33   1.4h  「Claude Haiku 4.5」
   fp=0 facet=1 sim=0.33   0.4h  「Claude Opus 4.6」
   fp=0 facet=1 sim=0.33   1.8h  「Claude Opus 4.8」
   fp=0 facet=1 sim=0.33  28.6h  「Claude Opus 4.7」
   fp=0 facet=1 sim=0.33  28.4h  「Claude Opus 4.5」
   fp=0 facet=1 sim=0.33  74.3h  「Claude Opus 5」
```

一則師資產品公告，對九則模型發布事件九路平手。共同 token 只有 `claude`。
**它不屬於其中任何一則**，而任何一種「挑一個」的規則都會挑錯。

### 時間距離刻意不進排名鍵

《修正版》§10 把「時間距離」排在排名第 4 位。**這一輪不採納**，理由在上面那張表：

```
加上時間 → 挑「Claude Sonnet 4.6」，理由是差 0.2 小時
```

用 0.2 小時的時間差，把一個師資產品公告掛到一則模型發布事件上。
**那是把 first-match 的任意性換成另一種任意性，而且看起來更精確。**

更根本的：時間已經是硬閘了（96 小時 / 21 天，見〈規則本體〉）。
再拿它當偏好等於把同一個訊號用兩次——**閘後面的每一個候選，時間都已經
「夠近」了，那之後誰更近不再是證據**。

所以排名鍵只有三格：

```
(指紋一致, facet bucket 一致, 標題相似度)
```

三格全等 → 平手 → 不掛。這則 signal 去開自己的 Event，或被 defer。

### 為什麼不做成可調的 margin

《修正版》§11 建議 `cluster.attach_ambiguity_margin: 0.08`（前一版建議直接定 0.08，
後一版改成「先修 identity 再校準」——方向對）。**這一輪兩者都不做。**

修完 identity 之後的分布已經量了：**多候選只剩 1 筆，而它的 Top1−Top2 是 0.00。**
n=1、差距 0，任何大於 0 的門檻值都接得住它——這份語料選不出 0.02 跟 0.30 哪個對。

一個沒有資料支撐的旋鈕，日後會被當成校準過的旋鈕來調
（同 `coverage_gap.min_answers` 那條）。所以第一版只實作**完全平手不掛**，
設定檔不開這一格。等真的出現 0.61 / 0.59 那種形狀，再把它變成可調的。

### 這次改動一樣只影響未來

`pulse-cluster.py` 每班只對**新進的 signal** 跑 attach 判定。
`Claude Sonnet 5` 上那筆 `rel=33` 的「Claude For Teachers」是舊帳，
新規則不會回頭把它拿掉——它沒有 fingerprint，沒有任何規則能自動判它是錯的。
**那一筆要人看**（`status` 已經是 published，移除要走人工複審）。

## 2026-09-04：同一顆 URL 二次進站——21 天窗口攔到了不該攔的東西

### 觸發這一則

`src-anthropic-news`（sitemap adapter）在 `evt-2026-07-30-54f43a`
（Investigating Incidents Cybersecurity Evals）進站 35 天後，同一顆 URL
又出現在當天的語料裡——**`url` 與 `url_canonical` 逐字元相同**，只有 sitemap
回報的 `published`（lastmod）從 `2026-07-30T23:14:55Z` 跳到
`2026-09-04T03:24:16Z`。`first_observed_at` 沒有動（合約是「寫入一次永不重寫」，
見 `references/event-timestamps.md`），`is_new` 也正確判成 `false`——
`pulse-probe.py` 那一層沒有壞。

壞在下游：`pulse-score.py` 不看 `is_new`，只看新鮮度閘
（`first_observed_at − published`），而這筆的 `lead_days` 是 **-35**
（觀測晚於「發布」——因為「發布」其實是站方後補的 lastmod，不是真的重新發布）。
新鮮度閘只擋 `lead_days > 門檻` 的正方向（觀測太晚），沒有擋負方向，
於是這筆訊號照樣進了 `signals-scored.jsonl`，當成一則要聚類的新聞。

到了 `attach_target()`，兩個候選的 `published` 相差 840 小時，超過
〈規則本體〉的 21 天硬上限，四條路徑全部不 attach。`fingerprint` 是
`None`（`Investigating Incidents Cybersecurity Evals` 不在 `_FP_PATTERNS`
的 11 個家族白名單裡），所以連身分否決都不適用——就是單純的「太久沒看到，
當新的處理」。結果開出 `evt-2026-09-04-54f43a`，跟 07-30 那則**除了檔名，
逐欄位相同**：同標題、同 URL、同來源、同一句空摘要。

### 這不是「窗口設太短」

〈規則本體〉的 21 天窗口回答的問題是「兩篇報導講不講同一件事」——那個問題
本來就該有一個上限，91 天前的舊聞跟今天的新聞標題像也不該黏在一起。
這一則問的是另一個問題：**「這兩筆訊號是不是同一個資源」**，而這個問題
不需要問時間，因為 `url_canonical` 已經回答了——一模一樣的 URL 不是
「很像」，是同一個東西被觀測了兩次。拿一把回答「像不像」的尺去量
「是不是同一個」，量出來的數字自然不對。

### 規則本體要多一條，排在最前面

```
url_canonical 與既有 Event 任一證據相同   → attach（不看時間窗、不看相似度）
時間差 > 21 天                            → 不 attach（硬上限）
fingerprint 兩邊都有 且 不相同            → 不 attach（身分否決）
fingerprint 相同 且 facet bucket 相同     → attach（窗口 21 天，incident 7 天）
其餘                                       → 96 小時內 且 標題相似度 ≥ 門檻
```

這條不經過 `belongs_to_event()`（那支函式的簽名是標題與時間，不帶 URL，
選擇不改簽名是為了不動它現有的呼叫端與測試），而是 `pulse-cluster.py`
自己在 `attach_target()` 判不出來之後多問一句：`sig["url"]` 正規化後
（去 `www.`、去結尾斜線）跟不跟既有 Event 任何一筆證據的 URL 相同。
相同就直接 attach——不需要 `eventability ≥ 70` 的門檻，因為這條路徑
不是「這則訊號夠不夠格開一個新故事」，是「這則訊號根本不是新故事」。

`Event.add_evidence()` 本來就用 `(source_id, url)` 去重（見
`references/evidence-tiers.md`），所以 attach 到既有 Event 之後，
這筆證據會被原地吞掉、不留痕跡（`ev.dirty` 不會被設成 `True`）——
這正是我們要的結果：同一顆 URL 第二次出現，不該讓任何東西動。

### 這一輪不做的事

**不回頭合併 `evt-2026-07-30-54f43a` 跟 `evt-2026-09-04-54f43a`。**
同〈2026-08-12 下午〉那筆「Claude For Teachers」的先例——`pulse-cluster.py`
每班只對新進 signal 跑判定，既有 Event 不會重新聚類，這兩則已經在磁碟上、
其中一則已經潤過稿（`enriched: true`），合併是內容決定，要人看。

**不把 `url_canonical` 寫進 `evidence` frontmatter。** 正規化只在
`attach_target()` 這一步內部算，算完即丟，不進 schema——避免動到
`_EVIDENCE_FIELDS` 這個白名單牽動 frontmatter 欄位順序與既有測試。
之後如果同一種正規化在別處也要用，再考慮升成共用函式。

**不修新鮮度閘的負值 `lead_days`。** 那是另一個問題（`pulse-score.py`
為什麼會把「站方後補 lastmod」算成「訊號」），這裡只堵住它流到聚類層
之後會造成的傷害——多一顆同 URL 訊號被擋在源頭之外，比只在下游補洞更好，
但那是下一輪的題目，不假裝這裡順手解決了。
