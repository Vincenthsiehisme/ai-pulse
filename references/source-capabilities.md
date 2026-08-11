# 來源層：capability —— 這條來源**有可能**告訴我們什麼

> 消費者：`scripts/lib/sources.py` 的 `CAPABILITIES`（封閉詞彙表）、
> `scripts/selftest.py` 的三條判準、`scripts/pulse-monitor.py` 的宣稱／觀察對照行。
> 規格先於實作（紅線 9）：這一頁先寫，`_config/sources.yaml` 才補欄位。

## 這個欄位在回答什麼

不是「這條來源好不好」，那是 `tier` 與 `lifecycle` 的事。
是**「假設它明天發了一篇，那篇有可能是哪一類的證據」**。

要有這個欄位，是因為 2026-08-11 量到一件事：86 則已上線事件裡 81 則（94%）
到今天只有一個獨立來源。要回答「為什麼」，得先分得出這兩種：

```
沒有人跟進        → 事情真的沒有後續，系統沒有錯
沒有人看得到跟進  → 後續存在，但這 32 條來源裡沒有一條的職責是報那種東西
```

第二種是**盲區**，而盲區不會讓任何東西變紅——它長得跟第一種一模一樣。
capability 是把盲區變成可以指著看的東西的第一步。

## 它明確**不是**什麼

### 不是獨立性

一家公司自己的部落格寫「某某企業導入了我們」，那是 `enterprise_adoption`——
capability 說的是**題材**，不是**可信度**。可信度由 `track` 與 `tier` 表達，
而且 `track: official` 的來源永遠不會因為 capability 寫得漂亮而變成第三方佐證。

兩件事分開寫是刻意的。混在一起的話，補一條媒體來源就會同時看起來像是補了
題材又補了獨立性，而那正是 2026-08-11 的 attach 實測證明**不成立**的推論。

### 不是測量

**capability 是人寫下的宣稱，不是系統量到的事實。**

今天 32 條的標註是照 `_corpus/` 裡實際抓到的標題標的（25 條有語料），
但即使如此，它仍然只是「我讀了它過去發過什麼，推測它未來可能發什麼」。
沒有任何一格是機器驗證過的。

這件事必須寫在這裡，因為這個 repo 有前科：`scoring.value` 寫了沒人讀、
`desc-zh.json` 有消費者沒有生產者、`next_signal` 欄位存在但 0/86 被填過。
一個沒有標明「這是宣稱」的欄位，三個月後會被當成測量來引用。

### 不是分類整齊

一條來源可以同時有多個 capability，而且**應該**有多個。
只標一個通常代表標的人在偷懶，或者這條來源的職責本來就窄（`src-gh-vllm-releases`
只發版本號，就只有 `product_release`，那是誠實的窄）。

## 詞彙表是封閉的，而且只有一份

15 個值，定義在 `scripts/lib/sources.py` 的 `CAPABILITIES`。

```
official_announcement   官方承認某件事發生了
product_release         有東西可以用了
research_release        方法／模型／論文本身

benchmark               有人跑了數字
third_party_validation  不是發布方的人說了話
research_replication    有人試著重現

enterprise_adoption     有組織真的在用
procurement             有人真的付錢買了

supply_chain            晶片／機櫃／電力實際流動
infrastructure          機房、算力、網路蓋起來了
financial_impact        錢的方向變了

policy_execution        法規從紙上變成執行
legal_proceeding        訴訟、法院受理與裁定

social_signal           圈子在談
developer_feedback      用的人回報了什麼
```

**為什麼放 `lib/` 而不是 `_config/`**：`_config/` 放的是操作者可以調的旋鈕
（門檻、開關、觀察窗）。詞彙表不是旋鈕，是結構——改它等於改資料模型，
應該走 PR 而不是改一行 YAML。這跟 `SECTIONS` 的前例是同一條理由。

**為什麼封閉**：開放詞彙表會在半年後長出 `benchmarks` / `benchmark_result` /
`third-party_validation` 這種同義異形，而覆蓋率矩陣會安靜地把它們算成不同格。
selftest 有一條釘住：值不在表裡就紅。

## 三條判準（都在 selftest，不在文件）

執行計劃的〈修正三〉：**驗收條件寫在文件裡會過期，寫在碼裡才不會。**
「所有 running sources 都有 capability」這句話在通過的那天成立，
在下一次有人加來源的那天失效，而且不會有任何東西變紅。

所以：

1. `lifecycle` 在 `RUN_LIFECYCLES`（active / degraded / probing）的來源，
   `capabilities` 必須存在且非空 → 否則紅
2. 任何 `capabilities` 的值必須在 `CAPABILITIES` 裡 → 否則紅
3. 除了 `lib/sources.py`，`scripts/` 底下不准再出現 `"official_announcement"`
   這個字面值 → 否則紅（比照既有的 `aggregator_sources` 禁令）

`dormant` / `quarantined` 不強制。理由：那些來源現在什麼都不會產出，
逼人替一條停用的來源寫下未來的宣稱，寫出來的東西沒有人會回頭驗。
它們有標就留著，將來復活時是現成的。

## `RUN_LIFECYCLES` 順手搬家了

寫第 1 條判準時發現 `{"active", "degraded", "probing"}` 這個集合被硬寫在
**四個**檔案裡：`pulse-probe.py`、`pulse-monitor.py`、`pulse-source-notes.py`，
以及 `pulse-source-health.py`（在那裡叫 `RUNNABLE`）。

這正是 `lib/sources.py` 當初為了 `SECTIONS` 而存在的那個病。
判準要用到這個集合，而多寫第五份的話，判準本身就會變成病的一部分。
所以搬進 `lib/sources.py`，四處改成 import，並加一條禁令。

## 宣稱 vs 觀察：這個欄位當天就有消費者

`pulse-monitor` 每班印一行對照：

```
來源能力：running 27 條，全數已標；14 種能力裡 1 種沒有任何來源宣稱（procurement）；
3 條宣稱了但語料裡從來沒有過（src-kol-thezvi、src-media-theregister、src-mistral-news）
```

三個數字各自回答一個不同的問題：

| 數字 | 它在問 | 壞掉的樣子 |
|---|---|---|
| running 幾條已標 | 判準有沒有被繞過 | 有人加來源沒標（selftest 會先紅） |
| 幾種能力沒人宣稱 | **盲區在哪** | 這就是 P0-d 覆蓋率矩陣的雛形 |
| 幾條宣稱了但零產出 | 宣稱是不是空頭支票 | 一條從來沒交過貨的來源，它的宣稱不可證偽 |

第三格今天是 **3**，而這三條的健康分都是 **100**。詳見下一節。

## 這一格今天不觸警，理由要寫下來

第三格（宣稱了但零產出）**不接 `--alert-*` 旗標**，只印。

先把一件事講清楚，因為我第一版寫錯了：**健康分沒有壞。**
`references/source-lifecycle.md`〈什麼算失敗〉那張表白紙黑字寫著
「`200` 但 0 筆 → 成功 `+8`」，理由是「安靜的 feed 是健康的 feed，
把『沒新聞』罰成失敗等於逼系統偏好吵的來源」。那個判斷是對的，不該改。

真正的缺口在別的地方：**那張表只看單班，而沒有任何消費者在看累計。**

```
src-mistral-news   score=100  runs=25  consecutive_successes=24  last_status=200
                   語料累計相異項目數：0     ← 25 班、24 次成功，一筆都沒有過
```

一班 200／0 筆是安靜；**25 班全部 0 筆、一次都沒有過**，就不再是安靜了，
而是這兩種之一：feed 真的兩週沒東西，或者 adapter 解析壞了。
**這兩者現在分不出來**，而分不出來本身就是要修的東西。

另外兩條的形狀不同但結論一樣：`src-media-theregister` 是 `robots_disallow`、
`src-kol-thezvi` 是 `robots_unknown`，25 班全記成中性——那也是刻意的
（robots 是合規政策不是健康度），代價同樣是分數永遠 100、永遠不進隔離候選。

所以這一行**不是在補一個壞掉的警報，是在補一個從來沒有人量的維度**：
單班的健康歸健康分管，累計的到貨歸這一行管。

那為什麼不觸警？因為三條裡有兩條的成因是 robots 合規，那是**設計上就該一直是
這樣**的狀態（同 `TERMINAL_BLOCKERS` 的理由）——一個第一天紅、之後每天都紅的
警報，兩週之內就會被人加旗標關掉，然後連 `src-mistral-news` 那條真的該追的
也一起靜音。**先讓它每天被印出來，是為了不讓它被忘掉。**

要把它變成警報，得先能分開「合規上抓不到」與「抓得到但一直空手」。
那是下一輪的題目，規格會寫在 `references/source-lifecycle.md`〈健康分〉。

## 同一份詞彙表的第二個用途：`unanswerable` 的 reason

`pulse-signal-review.py --verdict unanswerable` 必須配 `--reason`，
而 reason 的合法值就是 **`CAPABILITIES` 再加一個 `other`**
（`lib/sources.REASONS`，衍生不抄寫）。

### PRD 把這兩份寫成不同的清單，那是個錯

PRD §7 給了 11 個 reason，§14 給了 14 個 capability。兩份重疊很多但不相等：

```
只在 reason 那份     product_availability、other
只在 capability 那份 official_announcement、product_release、research_release、
                     infrastructure、developer_feedback
```

而 PRD §19 的 Gap × Capability 矩陣要求兩者**可以直接比較**。
用兩份不同的清單去 join，結果是有些 Demand 的列永遠對不到任何 Source，
有些 Source 的列永遠沒有 Demand——而那不是量出來的洞，是詞彙表的洞。

更根本的：**「這個訊號我回答不了」的理由，本來就是一個能力請求。**
「看有沒有企業真的拿它進 production」答不了，缺的正是 `enterprise_adoption`
這種觀測能力。兩份清單描述的是同一件事的兩面——需求面與供給面。
所以它們必須是同一份，否則矩陣兩邊的軸對不齊。

`product_availability` 併進 `product_release`（「有東西可以用了」是同一個問題）。
`other` 只存在於 reason 這一側：一條來源不能宣稱自己「有能力報導其他」。

### `other` 是這份分類表的死人開關

分類表是在 **n=0** 的情況下猜出來的。猜錯了要有東西告訴我們。

`other` 佔比 > 30% 時，`_dashboards/coverage-gap.md` 印一行提醒：
**分類軸選錯了，該回頭重看，而不是繼續往一個對不上真實問題的表裡塞。**

所以 `--reason other` **必須配 `--note`**。沒有 note 的 `other` 是一筆
「我不知道」——它會進分母、把比例撐大，卻沒有留下任何能拿來重新分類的線索。

（原執行計劃寫這一行放在 `pulse-monitor`。改放 coverage-gap 頁：
reason 的分佈本來就住在那一頁，而 `pulse-monitor` 已經有六個區塊，
為一個今天是 0/0 的數字再開第七個，是在稀釋那頁的訊噪比。
同一條規則不寫兩份——那是這個 repo 量過很多次的病。）

## `other` 交出了東西：`legal_proceeding`（2026-08-11 P0-a 之後補）

第一批 26 則裁決裡 `other` 出現 3 次，而**其中 2 次是同一件事**：

```
第 4 則  capital-evolution  「Apple 訴訟看 Apple 回應與法院動作」
第 25 則 Apple is getting this wrong  「Apple 的正式回應、法院是否受理與後續裁定」
```

一次是巧合，兩次就是這張表少了一格。所以補上 `legal_proceeding`。
第三筆 `other` 是 GeForce NOW——那一則的下一個訊號原文就寫著「無明確的 AI 相關
後續訊號可追」，指向的是**門禁的相關性判斷**，不是觀測盲區。三筆分成兩種毛病，
而 `other` 這個死人開關的價值就在這裡：它把「分類表不夠用」變成看得見的東西。

**但那條 30% 的警報沒有響**（3/22 = 14%）。它看的是比例，看不出「同一個缺口
撞了兩次」。這是那條判準自己的盲點——寫下來是因為它下一次也不會響。

供給實測：`legal_proceeding` 是**官方 0／獨立 3**（Ars Technica 5 篇、
TechCrunch 4 篇、The Verge 1 篇，用語料實際數的）。沒有公司會發文報自己被告的
進度，所以這一類只可能從第三方來——跟 `research_replication` 同一個形狀。

## 標註是怎麼決定的（2026-08-11）

25 條有語料的，讀 `_corpus/` 裡的實際標題標；7 條沒有語料的（4 條 dormant
＋ 3 條上面那 3 條），照它的官方定位標，並且**知道那是純宣稱**。

量到的分佈（**全部 32 條**。`_dashboards/coverage-gap.md` 那張表只算 running 的 27 條，
數字會比這裡小——停用的來源不補盲區，那是刻意的）：

| capability | 幾條來源宣稱 |
|---|---:|
| product_release | 13 |
| official_announcement | 12 |
| third_party_validation | 10 |
| social_signal | 10 |
| research_release | 9 |
| policy_execution | 8 |
| enterprise_adoption | 7 |
| research_replication | 7 |
| benchmark | 5 |
| developer_feedback | 5 |
| supply_chain | 3 |
| financial_impact | 3 |
| infrastructure | 2 |
| legal_proceeding | 3 |
| **procurement** | **0** |

`procurement`（有人真的付錢買了）是 0。這不是標註漏了——
是這 32 條裡真的沒有一條會報「誰買了、買了多少、付了多少錢」。

而 `research_replication` 的 7 條裡，official 線只有 `src-arxiv-cs-cl` 一條，
而它是 **dormant**（robots `Disallow: /`，已複驗）。也就是**實際在跑的官方線 0 條**。
那是預期內的（沒有公司會發文說自己的結果重現不了），但它意味著
「獨立重現」這一類證據，在這個系統裡只可能從第三方來——
而第三方那一批，2026-08-11 的 attach 實測顯示有 12/14 黏不上原事件。

兩件事合起來看：**盲區不只是「沒有來源在看」，還有「看到了也接不上」。**

## 回滾

移除 `capabilities` 欄位不會讓任何抓取／評分／聚類行為改變——
這一層目前只被 selftest 與 monitor 的那一行讀。
要退掉的話，連同 `lib/sources.py` 的 `CAPABILITIES` 與三條判準一起退，
不要只退資料留判準（那會讓整條線紅掉且沒有東西能修）。

`RUN_LIFECYCLES` 的搬家可以獨立保留，它跟 capability 沒有相依。
