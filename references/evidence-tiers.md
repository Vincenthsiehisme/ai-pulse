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
| `suspected_repost` | 轉載鏈的判定結果。**每一輪重算重寫**——它是判斷的產物不是人填的事實，留著上一輪的結論會在字典或門檻改動之後變成一句沒人維護的舊話 |

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

## `evidence.translation_chain`：一篇改寫不是第二個聲音

`gate.yaml` 的那一塊：

```yaml
translation_chain:
  enabled: true
  entity_overlap_min: 0.80
  window_hours: 48
  excluded_from: [independent_sources, heat]
```

要防的事很具體：一篇英文原文加上一篇中文改寫，被算成**兩個獨立來源**，
於是「heat ≥ 70 需 ≥ 2 獨立來源」那道門被一次轉載打開。七條媒體線之所以
全部只收英文，就是在閃這個坑。

實作在 `scripts/lib/cluster.py` 的 `suspected_reposts()`，由
`pulse-cluster.rescore()` 呼叫。

### 判準：三個條件同時成立，外加一個否決

對同一則 Event 裡的每一對證據 (a, b)：

| # | 條件 | 缺資料時 |
|---|---|---|
| 1 | **語言不同**（`sources.yaml` 的 `language`） | 任一邊缺 → 不判 |
| 2 | **發布時間差 ≤ `window_hours`** | 任一邊缺 → 不判 |
| 3 | **標題實體集合的 Jaccard ≥ `entity_overlap_min`** | 任一邊空集合 → 不判 |
| 否決 | 兩邊都有 `fingerprint` **且不相等** → 直接不是轉載 | — |

「缺資料時不判」在這裡是**往嚴格的方向倒**：不判＝維持原本的獨立性計算＝
可能高估。這跟本檔前面說的「寧可低估獨立性」相反，是刻意的——**捏造一個
「它們是同一篇」的結論，比漏抓一次更難發現**。漏抓的那則會停在 review 等
人看；誤判的那則會安靜地少一個聲音，而且沒有任何欄位會顯示它被扣過。

實體集合走 `lib/entities.entity_ids()`，也就是命名實體字典。這一步是整條
規則能跨語言的原因：字典的 `aliases` 兩種語言都收，所以
「OpenAI 发布 GPT-5.2」與 "OpenAI launches GPT-5.2" 都命中 `{openai, gpt}`，
Jaccard = 1.0。**用 token 交集做不到這件事**——中英文標題的 token 交集
趨近於零。

fingerprint 當**否決**而不是當必要條件：`event_fingerprint()` 認得出具名模型
版本時它很準（GPT-5.2 ≠ GPT-5.1，兩者不可能互為翻譯），認不出時回 `None`
而那不代表兩篇無關。當必要條件會讓所有沒有版本號的新聞完全不受這條規則保護。

### 判成轉載之後怎麼算

一組互相判定為轉載的證據（連通分量）裡，留**一條原文**、其餘標成
`suspected_repost: true`。原文的挑法依序是：發布時間早的、tier 小的、
證據順序在前的——三段都是確定性的，沒有任意 tie-break。

被標記的證據：

- **不計入 `independent_sources`**（`excluded_from` 的第一項）。
- **不計入 heat**（第二項）。今天 heat 的傳播輸入是 `metrics=[]`，
  唯一會流進 heat 的證據面數字就是獨立來源數，所以上一條已經涵蓋這一條。
  **這不是「兩件事都做了」，是「今天這兩件事是同一件」**——社群線（M3）
  接上、heat 開始吃真的傳播訊號那天，要回來把第二項單獨接一次。
- **照樣計入 authority 與 `primary_evidence`。** 這是照 `excluded_from` 的
  字面：那兩項不在排除清單裡。一篇翻譯的權威性確實低，但那件事由它自己的
  tier 表達，不由這條規則表達。
- **照樣留在 `evidence[]` 裡，看得見。** 刪掉的話，人會以為我們沒抓到那篇。

### `enabled: false` 是真的關掉

`enabled` 讀得到，關掉就完全不判、不標記。這是一個**真開關**，不是
`readiness.require_primary_evidence` 那種假開關——差別在於它關掉的是一個
額外的保守判定，不是紅線的執法點。關掉它只會讓獨立性回到 2026-07-27 之前的
算法，不會讓任何一則本來擋著的 Event 通過。

### 這條規則今天不會被任何真語料走到

沒有任何中文來源，所以每一班的 `suspected_repost` 都會是 0。
**一條沒有輸入的規則只能靠測試證明自己是對的**——selftest 兩個方向都釘：
該判的判、不該判的不判（同語言、超出時間窗、實體重疊不足、fingerprint 不同、
`enabled: false`）。變異清單 M43–M47 守它的五種安靜死法（`enabled` 不讀、語言那一關拿掉、
時間窗不比、重疊門檻不比、`excluded_from` 不讀）。

### 它管不到的那一格

**認不出模型版本的跨語言兩篇，根本不會落進同一則 Event。**
`belongs_to_event()` 在沒有 fingerprint 時退回標題相似度，而中英文標題的
token 交集趨近於零——於是同一件事會變成**兩則各自獨立的 Event**。

那是另一種病（重複 Event），這條規則管不到，本檔也不假裝它管得到。
真要治，得讓聚類本身也走實體集合而不只是 token 相似度，那會動到
`belongs_to_event()` 的門檻，是另一份規格的事。記在 `BACKLOG.md`。

## 這一層不保證什麼

- **不保證 `primary_evidence >= 1` 代表事情是真的。** 它只代表當事人自己說過。
  當事人也會說錯、也會改口。內容真假由人工複審負責（`readiness-gate.md`）。
- **不保證 tier 標得對。** tier 是人寫在 `sources.yaml` 上的，沒有任何機制驗證
  一條標成 Tier 1 的來源真的是一手發布。標錯的方向如果是往上（把媒體標成
  Tier 1），紅線 2 就被繞過去了，而不會有任何東西變紅。
- **不保證兩條 Tier-2 的獨立性是真的。** `media_group` 也是人寫的。兩家其實
  同集團但沒標的媒體，會被算成兩個獨立聲音。
- **不保證被留下的那一條真的是原文。** 挑原文只看發布時間，而轉載方的時間戳
  是它自己寫的——一篇時間戳造假（或時區標錯）的改寫會被留下，原文反而被標成
  轉載。影響面有限：一組轉載無論留哪一條，對 `independent_sources` 的貢獻都是
  1，authority 與 `primary_evidence` 也是全部證據一起算的。**差別只在人看到
  哪一條被標記**——所以這是一個顯示問題，不是一個計分問題。真要治得比對正文
  或 canonical 連結，那超出「只收標題與連結」的合規邊界（紅線 7）。
