# 每日精選的寫回層：機檢退件，然後才寫檔

> 消費者：`scripts/pulse-digest-apply.py`、`scripts/selftest.py` 的判準、
> `scripts/enrich-runbook.md` 的 digest 那一節、`_config/gate.yaml` 的 `digest:` 區塊。
> 上游規格是 `references/digest-framework.md`，這一頁只寫「怎麼檢、怎麼寫檔」。
> 規格先於實作（紅線 9）：這一頁先寫，碼才動。

## 這一層在守什麼

`digest-framework` §五把產線切成四段，這一支是第三段：

```
pulse-digest-prep.py    確定性：挑材料、算距離 → _probe/digest-worklist.json
Cowork 寫               敘述：產出分層 JSON
pulse-digest-apply.py   ← 這一支。機檢退件 → voice_clean → 寫 Digests/<date>.md
pulse-digest-gate.py    確定性：人審三格沒填完就不 render
```

它是**判斷層**（紅線 1）：退不退件由規則決定，不由寫的人自評。

## 一、為什麼寫的人不交「文章」，只交 sections

第一版的設計是「交一份 `body`（全文）＋一份 `claims[]`（每句話標層）」，
讓機檢查 claims。**那個設計是假的守衛。**

讀者讀的是 `body`。`claims[]` 說「這三句是 A 級、有證據」，但 `body` 裡完全可以
多出第四句沒有登記的話，而且它會是最好看的那一句——`digest-framework` 記的
手寫那篇正是這樣：好看的原因全在沒有證據的那幾句。機檢會全綠，因為它檢的是
另一份文件。

這正是這個 repo 的老病：**一個為了跟它要守的東西無關的理由而成立的斷言。**

所以這一版**沒有 `body` 這個欄位**。文章由 apply 從 sections 組出來：

```
文章 = 標題 + 問題 + sections（依序）+ so_what
```

一段就是一個 section，一個 section 只有一層。分不出層的段落要拆開——
而「這一段裡哪幾句有證據、哪幾句是你說的」分不出來，本來就是要修的東西。

代價是寫的人不能在同一段裡從證據滑進推論。那是刻意的。

## 二、輸入 schema

```json
{
  "date": "2026-08-13",
  "title": "文章標題",
  "question": "一天只准一個問題，要能被當天材料部分回答",
  "sections": [
    {"id": "s1", "layer": "A", "text": "…", "evidence": ["evt-2026-08-13-abc123"]},
    {"id": "s2", "layer": "B", "text": "…", "basis": "這是背景，今天的消息沒提：…"},
    {"id": "s3", "layer": "C", "text": "…", "counter": "別的解釋：…"},
    {"id": "s4", "layer": "D", "text": "…", "evidence": ["evt-…"],
     "source_url": "https://x.ai/bot"}
  ],
  "so_what": "一句話結論",
  "support": ["s1", "s3"],
  "dropped": [{"id": "evt-…", "why": "跟今天這個問題沒有關係"}]
}
```

四層的意思在 `digest-framework` §一與 `evidence-availability`〈多一個 D 層〉：

| 層 | 是什麼 | 這一支要求什麼 |
|---|---|---|
| A | 證據內 | `evidence[]` 非空，且每個 id 都在當日 worklist |
| B | 背景知識，可查證但不在 vault | `basis` 非空 |
| C | 作者推論 | `counter` 非空且不短於門檻 |
| D | 一手來源有、我們沒取用 | `evidence[]` 非空 ＋ `source_url` 必須是那些事件證據列裡真的有的網址 |

D 跟 B 的差別是**讀者補不補得了**：B 沒有連結，D 有。

## 三、退件規則

全部是機械判準，每一條有 id，退件時原樣印出來。退件＝不寫檔、離開碼非 0。

### 結構層

| id | 什麼時候退 | 為什麼 |
|---|---|---|
| `bad_layer` | `layer` 不在 A/B/C/D | 打錯字的層等於沒標層 |
| `duplicate_id` | 兩個 section 共用一個 id | `support` 會指到不確定的東西 |
| `dangling_support` | `support` 指到不存在的 id | 支撐鏈斷了而看起來有 |
| `empty_article` | 沒有 sections、或 `question` / `so_what` 空 | |

### 證據層

| id | 什麼時候退 | 為什麼 |
|---|---|---|
| `unknown_event` | 引用或 dropped 的事件 id 不在當日 worklist | 引用一則不存在的事件，讀者查不到、我們也查不到 |
| `layer_needs_evidence` | A 或 D 級的 `evidence[]` 是空的 | A 級的意思就是「證據內」 |
| `b_without_basis` | B 級沒有 `basis` | 沒有 basis 的背景知識，讀者分不出它是不是編的 |
| `c_without_counter` | C 級沒有 `counter` | 反例測試（`digest-framework` §一） |
| `counter_too_thin` | `counter` 短於 `digest.counter_min_chars` | 「也可能不是」不是反例 |
| `so_what_unsupported` | `support` 裡沒有任何 A 級 | **硬規則：結論不能只靠 B＋C 撐** |
| `unaccounted_material` | worklist 的 items ≠（被引用 ∪ dropped） | 每一則素材都要有交代，跟 dashboard 三桶對帳同一個道理 |
| `dropped_without_reason` | dropped 條目沒寫 `why` | 沒理由的丟棄跟資料不見了沒有區別 |
| `d_without_source_url` | D 級缺 `source_url`，或那個網址不在它引用的事件證據列裡 | 一條讀者點不到、或點到別的地方的連結，比沒有連結更糟 |
| `withheld_without_d` | 引用到 `withheld` 來源的事件，全篇沒有一條 D 指向它的原文 | 見下 |

`withheld_without_d` 是 `evidence-availability` 那一頁欠的那條線。
2026-08-13 的 Grok Bot 那則寫「（證據不足，待補）」，而 `https://x.ai/bot`
就躺在它自己的證據列裡。這條規則把「誠實」變成欄位，不靠寫的人記得。

判斷哪些來源是 `withheld` 走 `lib/availability.evidence_availability()`，
跟門禁的 `thin_by_policy` 同一份判準——**不要在這裡另寫一套**。

### 語言層

| id | 門檻 | 為什麼 |
|---|---|---|
| `closed_inference` | 黑名單命中即退 | 「只有一種可能」「必然」「唯一的解釋」是沒跑過反例的斷言 |
| `not_a_but_b_overuse` | 全篇超過 `digest.not_a_but_b_max` 次 | 這個句型一篇一次是強調，三次是口頭禪 |
| `dash_density` | 每千字破折號超過 `digest.dash_per_1k_max` | |
| `bold_overuse` | 粗體超過 `digest.bold_per_1k_max` | 每一句都是重點等於沒有重點 |
| `question_density` | 設問超過 `digest.questions_max` | 設問是 AI 腔最穩定的指紋之一 |

中國用語與半形標點**不退件，直接洗**——那一層是 `lib/voice_clean.py`，
零容忍無歧義的機械替換，跟 `pulse-enrich-apply.py` 走同一支。
洗了什麼要印出來（事後摘要），不要靜靜改掉。

**洗在檢之前。** 第一版寫成「先檢再洗」，理由是「退件理由要對得上寫的人打的字」，
而那留了一個洞：半形問號繞得過設問密度（`?` 不是 `？`，而 voice_clean 會把緊鄰
CJK 的半形標點轉全形）。先檢的版本看到一篇沒有問號的文章，洗完寫進檔案的卻有三個。
**判準要看讀者看到的那一版。**

### 機器擋不住的，這一頁不假裝有守

`digest-framework` §五列了三件：問題值不值得問、B 級的背景知識對不對、
類別滑動。**一條規則都沒有守到它們**，所以這條鏈的產出是草稿，
人審那一關由 `pulse-digest-gate.py` 管。

## 四、寫檔

```
Digests/<YYYY-MM-DD>.md   kind: digest   跟 Events/ Tracks/ Actors/ 平行
```

**不要塞進 `Events/`**：dashboard 的三桶對帳掃的是 `Events/*.md`，
混一個不同 kind 進去會讓那道守衛的語意糊掉（`digest-framework` §五）。

frontmatter 帶審核用的三格（`pulse-digest-gate.py` 讀它們）：

```yaml
kind: digest
date: 2026-08-13
title: …
status: draft            # draft → reviewed，由人改
review_question: null    # 問題成不成立
review_background: null  # B 級認不認同
review_counter: null     # counter 誠不誠實
```

三格是 `null` 就不 render。**生成一次就不能再被覆寫**——
當天那一份已經存在就拒寫並回離開碼 1，逃生口是 `--force`，
而且 **runbook 的自動化那一節不准出現 `--force`**（同 `enrich-idempotence`
那條，selftest 機械檢查）。理由一樣：審過的稿隔天被改掉，沒有人會發現。

## 五、驗收：拿 8/12 那篇手寫稿餵進去要被退

這一支寫完的第一件事是拿 `digest-framework` 記下來的那篇手寫稿當反例。
那篇的問題那一頁已經寫得很清楚：

```
「Brookfield 買電廠收費公路」「用二十年在算」「GPU 三四年換代」
    → 全是外部背景知識，文章裡沒標，讀者分不出
「只有一種可能：他們相信需求夠耐久」
    → 沒跑過反例的斷言；管理費、offtake 擔保、債權結構、募不到，都是別的解釋
```

照這一版的 schema 重新編碼之後，它至少命中 `b_without_basis`、
`c_without_counter`、`closed_inference` 三條。**驗收標準是它被退**，
不是它能過。selftest 用重建的片段釘住這一格。

> 那篇原稿不在 repo 裡（它活在一次對話裡），所以 selftest 用的是
> `digest-framework` 記下來的那幾句重建的片段，不是原文。這裡寫明，
> 免得下一個人以為有一份可回溯的原稿。
