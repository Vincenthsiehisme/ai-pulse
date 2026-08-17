# 每日精選的人審那一關：三格，以及它現在擋不住什麼

> 消費者：`scripts/pulse-digest-gate.py`、`scripts/selftest.py` 的判準、
> `scripts/enrich-runbook.md` 的 digest 那一節。
> 上游是 `references/digest-apply.md`（寫檔那一層）與
> `references/digest-framework.md` §五（為什麼要有人審）。
> 規格先於實作（紅線 9）：這一頁先寫，碼才動。

## 先講這一支現在擋不住什麼

`digest-framework` 給這一關的職責是「人審三格沒填完就不 render」。
**而現在沒有 render 可以擋**——`pulse-render.py` 產 home / lines / timeline /
signals / events 五種頁，`daily` 這個字在它裡面出現 0 次。

所以這一版的 `pulse-digest-gate.py` 是一個**狀態計算器**：它算出每一份 digest
該落在哪一桶、寫進 frontmatter、產一頁給人看的收錄索引。它不阻止任何事情發生，
因為今天沒有事情會發生。

這件事寫在這裡而不是等人發現，理由跟 `references/readiness-gate.md` 對
`unsupported_heat` 的處理一樣：**掛在那裡並註明為什麼，是誠實；假裝它在守，
才是掩蓋**（紅線 8）。差別是 `unsupported_heat` 的輸入真的還不存在（要等社群線），
而這裡的 render 是做得出來的——所以這不是「休眠」，是**分兩支審**的代價，
而且有明確的到期日：

> `/daily/` 那一支落地時，要回到這一節把這幾段刪掉，並把
> `enrich-runbook.md` 裡 digest 那兩步的「失敗不擋 push」豁免一起拿掉。
> 那個豁免的理由寫的是「`Digests/` 還沒有下游消費者」——render 一接上，
> 那句話就不成立了，而它會留在原地繼續說一件不成立的事。

## 一、三格：點名，不是打勾

寫檔那一層產出的 frontmatter 是三個 `null`。如果「填完」的定義只是「不是 null」，
審的人打三個 `ok` 就過了，而機器分不出他有沒有讀。這個 repo 給這種東西的名字是
**假開關**（`_config/gate.yaml` 的 `require_primary_evidence` 那一段寫得最清楚）。

所以三格的型別不一樣：

```yaml
review_question: ok           # 封閉詞彙：ok / no。問題成不成立
review_background: [s2, s5]   # 你確認過的 B 級段落 id
review_counter: [s4, s7]      # 你確認過的 C 級段落 id
review_note: …                # 任一格是 no 時必填
reviewed_by: vincent
reviewed_sig: 8f3c…           # 內容簽章，見下
```

| 格 | 判準 |
|---|---|
| `review_question` | 必須是 `ok` 或 `no`。其他值（含 `null`、`true`、`"ok "`）一律當成還沒審 |
| `review_background` | **集合必須剛好等於文章裡所有 B 級段落 id**。少一個就印出少了誰 |
| `review_counter` | 同上，對 C 級 |
| `review_note` | 任一格是 `no` 時必填；全 `ok` 時可有可無 |

**後兩格要你點名。** 你不打開檔案就列不出段落 id，所以蓋章的成本被機械地拉高了。

沒有 B 級段落的文章要寫 `review_background: []`——**空 list 跟 `null` 分得開**：
前者是「看過了，沒有東西要審」，後者是「還沒審」。這是
`references/evidence-availability.md` 那套三態紀律的同一個形狀：
把「沒有」跟「不知道」寫成同一個值，就是這個 repo 一直在修的病。

### 這一格擋不住什麼（第四件，寫出來不假裝）

`digest-framework` §五列了三件機器擋不住的事：問題值不值得問、B 級的背景知識
對不對、類別滑動。這裡加第四件：

**一個人可以打開檔案、抄下段落 id、然後照樣不讀內容。** 沒有任何規則抓得到那個。
點名只是把成本從「零」拉到「要開檔案」，不是把它拉到「要讀懂」。

### 舊格式：`section_layers` 缺席不等於零

那一格是 2026-08-17 才有的。在它之前寫的三份 digest（08-14、08-15、08-16）
frontmatter 裡沒有它，而 `fm.get("section_layers") or {}` 會讓「沒有那一格」
跟「這一份沒有 B/C 級段落」長得一模一樣——後兩格填 `[]` 就過，
整個點名設計被繞開，而收錄頁會說它審完了。

**這個病出現在守這個病的這一支自己身上**，所以 gate 對缺席回一個明確的
`section_layers` 待辦，不當成零。既有那三份用一次性遷移補上
（從文末〈這篇的層次〉parse 回來）——那段附錄本來是「給人看的版本，
機器不再 parse 它」，一次性遷移是它唯一的例外，跑完就不再需要。

## 二、簽章：審核蓋在內容上，不是蓋在檔案上

`reviewed_sig` 簽的是**文章本身**（question ＋ 每個 section 的 id/layer/text
＋ so_what），做法沿用 `pulse-narrative-prep.signature()`。

沒有簽章的話，一份審過的稿被手改一段，狀態還是 `reviewed`——而「審過」這件事
會慢慢跟檔案裡的東西脫鉤，沒有人會發現。這正是 2026-08-12 潤稿鏈那次事故的
形狀（產物看起來正常，內容早就不是同一批）。

簽章只涵蓋文章，**不涵蓋 `basis` / `counter` / `evidence`**。理由：那三格改了
不會改變讀者看到的文字，而簽章的用途是「讀者看到的東西變了沒」。
`counter` 被改掉確實會讓 `review_counter` 的判斷過期——那是這個設計的已知缺口，
記在這裡，不假裝簽章有蓋到它。

## 三、四桶收錄頁

`_dashboards/digests.md`，由這一支產（不是擴充 `pulse-dashboard.py`——那一支跑在
runbook 第 7 步，而這一支必須跑在 digest-apply 之後，塞進去會變成 dashboard 跑兩次）。

| 桶 | 判準 | status |
|---|---|---|
| 等你審 | 三格沒齊 | `draft` |
| 已審可發 | 三格齊、`review_question: ok`、簽章對得上 | `reviewed` |
| 退回重寫 | 任一格是 `no` | `rejected` |
| 內容改過 | 曾經審過（有 `reviewed_sig`）但簽章對不上 | `stale` |

**每一份 `Digests/*.md` 剛好落在一桶。** 落不進去的（frontmatter 壞掉、
`kind` 不是 digest、status 是別的字）印到 stderr 並回離開碼 1——
跟 `pulse-dashboard.py` 的三桶對帳同一件事，而那道守衛是 2026-08-13 一個
少了 `---` 分隔線的檔案從三張看板一起消失換來的。

對帳的**形狀**跟 dashboard 一樣、**詞彙**不一樣（那邊是 published/review/dropped）。
所以把形狀抽到 `lib/buckets.py`，兩支共用一份，不要複製第二個。

「等你審」那一桶要列出**還缺什麼**，不是只說「還沒審」：

```
- [[Digests/2026-08-15|標題]] — 4 段 · 引用 3 則
  還缺：review_question 沒填、review_counter 漏了 s4
```

## 四、退回重寫的那一天

digest 的寫檔守衛是「當天已存在就拒寫」（`digest-apply` §四）。所以一份被標成
`no` 的稿，**隔天的班不會重寫它**。

這是刻意的，不是漏洞：退回代表你想要一篇不一樣的文章，而「不一樣在哪」是白天的人
才知道的事。夜班拿同一份 worklist 重跑一次，多半會寫出同一篇。

處理方式：白天決定要改什麼之後，人自己用 `--force` 重跑。
**這個做法不寫進 runbook 的自動化那一節**（selftest 機械檢查），
理由同 `references/enrich-idempotence.md`。

代價是被退的那一天在站上是空的。寫在這裡，免得它變成一個沒人發現的空日。

## 五、還沒做、屬於 `/daily/` 那一支的

**D 級的原文連結必須進讀者看得到的版本。** 這一版決定了「層次標記（B 的 basis、
C 的 counter）只給審的人看，不給讀者」。但 D 級不一樣——它那一段的文字會寫
「想知道他們自己怎麼說，直接看原文」，而連結目前只存在文末的〈這篇的層次〉。
文末那一段不 render 的話，讀者會讀到一句「看原文」然後沒有東西可以點，
**那比不寫還糟**。

render 那一支要把 `source_url` 內嵌回 D 那一段。這件事有機檢的判準
（`withheld_without_d` 已經保證每個 withheld 事件都有一條 D 帶連結），
所以它是接線問題不是設計問題——但接線問題正是這個 repo 掉最多次的地方，
所以寫成一條待辦而不是一句「記得」。
