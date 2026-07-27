# 證據層：什麼算證據、哪一種撐得住紅線 2

> 這份文件是**規格**，`scripts/pulse-cluster.py` 的 `rescore()` /
> `evidence_frontmatter()`、`scripts/lib/quality.py` 的
> `authority_score_from_tier()`、`scripts/pulse-gate.py` 的
> `missing_primary_evidence` 是它的實作。不一致時以本檔為準，
> **先改本檔再改碼**（紅線 9）。

## 這份檔案為什麼到今天才存在

`references/gate-config-status.md` 第 98 行早就寫著：

> 要放寬紅線 2 的門檻，該走的路是改 `references/evidence-tiers.md` 再改碼（紅線 9）

`references/readiness-gate.md` 第 145 行也把「內容真假」轉手給
「證據層（`evidence-tiers`）」。**兩處都指著一個不存在的檔案。**

這是這個 repo 的老毛病換一種樣子：用「文件裡有一個連結」代理「那件事有規格」。
指路的人當天是誠實的——他知道那件事該有規格；只是沒有任何一條測試會因為
被指到的檔案不存在而變紅。順著連結去找的人會以為是自己搜錯了。

## 三個 tier 的語意

分節在 `scripts/lib/sources.py` 的 `SECTIONS`，是單一真相源；tier 寫在
`_config/sources.yaml` 每一條來源上。兩者的對應**不是**自動的——分節決定抓取
順序與角色，tier 決定權威分與 primary 資格。

| 分節 | 典型 tier | 能不能滿足 primary | 它回答的問題 |
|---|---|---|---|
| `official_sources` | 1 | **能**（唯一能的） | 當事人自己說了什麼 |
| `media_sources` | 2 | 不能 | 有沒有第二個獨立的聲音在講 |
| `kol_sources` | 2–3 | 不能 | 有沒有人在乎、多快開始談 |
| `aggregator_sources` | 3 | 不能 | 只當候選與熱度提示，不作事實依據 |

權威分由 tier 給確定性起始值（`authority_score_from_tier`）：
**Tier 1 → 90、Tier 2 → 65、Tier 3 → 40**，認不出來的 tier 給 50。
本 schema 沒有 `authorityScore` 欄位，所以這一步是查表不是推論。

### primary 的判準只有一條

`rescore()` 裡：

```python
if tier == 1 and role != "aggregator" and scat != "aggregator":
    primary += 1
```

**`tier == 1` 而且沒有被標成聚合。** 兩個 `!= "aggregator"` 是刻意重複的：
`role` 與 `source_category` 兩個欄位都可能標，漏看任一個就會讓一條聚合來源
用 Tier-1 的身分去滿足 primary。

### 紅線 2 的執法點只有一處

`pulse-gate.py`：

```python
if not (fm.get("primary_evidence") or 0):
    blockers.append("missing_primary_evidence")
```

就這一行。`_config/gate.yaml` 的 `evidence.need_tier1_primary: 1` 與
`need_independent_tier2: 2` **都沒有被讀進去**（見
`references/gate-config-status.md` 的 A/B/C 分類）。前者的數字碰巧跟這行的行為
一致，後者描述的「兩個獨立 Tier-2 也可以放行」**這條路根本不存在**——primary
缺席就是擋，補幾個獨立 Tier-2 都沒用。

寫在這裡是因為那兩個數字看起來像旋鈕：把 `need_independent_tier2` 從 2 改成 1
不會改變任何一則 Event 的命運，而下一個人會去懷疑資料。

## 獨立性：兩個條件任一成立就合併

實作在 `scripts/lib/cluster.py` 的 `independent_voices()`，是連通分量不是
`len(set(...))`：

- 同一個人（`person_id`）→ 合併。一個人不會因為換平台變成兩個獨立聲音。
- 同一個媒體集團（`media_group`）→ 合併。同一個編輯台不是兩個獨立聲音。
- 兩個欄位都空 → 退回 `source_id`，每條來源自成一組（舊行為）。

遞移是刻意的，且只往保守方向倒。**寧可低估獨立性，不可高估**——高估就是把
「heat ≥ 70 需 ≥ 2 獨立來源」這道門用我們自己的設定檔開掉。

## 證據記錄要留下什麼

一條證據記錄是 `Events/*.md` frontmatter 的 `evidence[]` 的一項。欄位白名單，
順序固定（`evidence_frontmatter()`）：

| 欄位 | 為什麼要留 |
|---|---|
| `source_id` | 綁回 `sources.yaml`：tier / role / media_group / person_id / language 全部從這裡查，不複製到證據上（複製就會過期） |
| `url` | 去重鍵之一，也是人要點進去看的東西 |
| `title` | **判斷用**：跨語言轉載鏈要問「標題實體重不重疊」 |
| `relevance` | 這條證據跟 Event 標題的相似度，attach 當下算的 |
| `published` | **判斷用**：轉載鏈要問「差幾小時」 |

`title` 與 `published` 是 2026-07-27 補的。在那之前它們只活在建立那一班的記憶體
裡——`event_markdown()` 寫進 frontmatter 的只有 `source_id` / `url` /
`relevance`，而重新讀檔那一段是這樣寫的：

```python
"title": e.get("url")          # ← 舊版
```

**證據的「標題」變成它自己的網址。** 後果有兩層：body 的〈證據〉清單把同一個
網址印兩次（中間夾一個破折號，看起來像「這篇文章的標題就叫 https://…」），
而任何拿 `title` 做判斷的規則會拿到一串網址去比相似度，比出來的數字是假的、
而且看起來很正常。

**規則：缺就是缺。** 讀不到 `title` 就填 `None`，不填 url；渲染那一行印
「（標題未留存）」加網址，不把網址印成標題。量不到不可以寫成一個看起來像值的
東西（紅線 8）。舊的 Event 沒有這兩個欄位是預期的——它們會在下一次那則 Event
被 attach 到新證據、重新寫檔時補上，**不做批次遷移**：沒有新證據的 Event 也不
需要判斷轉載鏈。

`language` 刻意**不**存進證據記錄：它是來源層的屬性，查 `sources.yaml` 就有。
存一份到證據上，來源改語言的那天兩邊就會不一致，而不一致的那一份沒有人會去看。

## `evidence.translation_chain` 還沒接上，前置條件是這個

`gate.yaml` 的那一塊描述得很完整：

```yaml
translation_chain:
  enabled: true
  entity_overlap_min: 0.80
  window_hours: 48
  excluded_from: [independent_sources, heat]
```

**整塊未接線。** 具體後果：一篇英文原文加上一篇中文改寫，會被算成兩個獨立
來源，同時虛增 `independent_sources` 與 heat。七條媒體線之所以全部只收英文，
就是在閃這個坑。

為什麼不能一次接完，量出來的理由：

1. **判斷需要的兩個欄位以前不在證據上。** `entity_overlap_min` 要標題、
   `window_hours` 要發布時間，兩個都只活在記憶體裡。這一版把它們留下來了，
   所以這條擋路的先決條件已經解除——但**留下來不等於接上**。
2. **跨語言的兩篇會不會落進同一則 Event，取決於標題認不認得出模型版本。**
   `event_fingerprint()` 帶 CJK 對照（通义→qwen 等），`event_facet()` 的
   正則也收中文（发布 / 融资 / 事故…），所以「OpenAI 发布 GPT-5.2」與
   "OpenAI launches GPT-5.2" 會得到同一個 `fingerprint` + `facet`，在時間窗內
   聚成同一則 Event——這正是 `translation_chain` 要防的那一格。
   但**認不出模型版本的標題會退回標題相似度**，而中英文標題的 token 交集
   趨近於零，於是它們會變成**兩則各自獨立的 Event**。那是另一種病（同一件事
   兩則 Event），`translation_chain` 管不到，本檔也不假裝它管得到。
3. **今天沒有任何中文來源，所以這條規則接上之後不會被任何真語料走到。**
   一條沒有輸入的規則要怎麼證明自己是對的，只能靠測試——所以接線那一版必須
   自帶正反兩面的 selftest 與變異，不能靠「跑一班看看」。

## 這一層不保證什麼

- **不保證 `primary_evidence >= 1` 代表事情是真的。** 它只代表當事人自己說過。
  當事人也會說錯、也會改口。內容真假由人工複審負責（`readiness-gate.md`）。
- **不保證 tier 標得對。** tier 是人寫在 `sources.yaml` 上的，沒有任何機制驗證
  一條標成 Tier 1 的來源真的是一手發布。標錯的方向如果是往上（把媒體標成
  Tier 1），紅線 2 就被繞過去了，而不會有任何東西變紅。
- **不保證兩條 Tier-2 的獨立性是真的。** `media_group` 也是人寫的。兩家其實
  同集團但沒標的媒體，會被算成兩個獨立聲音。
