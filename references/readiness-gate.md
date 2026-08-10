# readiness gate：Event 能不能公開發布

> 這份文件是**規格**，`scripts/pulse-gate.py`（判定）與 `_config/gate.yaml`
> （門檻）是它的實作。三者不一致時以本檔為準，**先改本檔再改碼**（紅線 9）。
>
> 它從 skill 的第一版就被引用（「事件層 — 硬門禁 — references/readiness-gate.md」），
> 但直到 2026-07-26 為止**檔案根本不存在**。這件事本身值得記一筆：一個被引用了
> 兩個月、內容為零的規格，跟一條永遠不觸發的 blocker 是同一種東西——看起來有人在管。

## 這一層在守什麼

`pulse-gate.py` 是**唯一**決定 `status: review → published` 的地方。紅線 1 說
判斷不由 LLM 決定，具體就落在這支腳本上：它讀 frontmatter 與 body，回傳一串
`blockers[]`，空的才發。LLM 寫的敘述會被它擋，不會被它相信。

判定是**純函式** `evaluate(fm, body, gate) -> (blockers, warnings)`：同樣的
frontmatter 與同樣的 `gate.yaml` 一定得到同樣的結果，不讀時鐘、不讀網路、不讀
磁碟。唯一的例外是 `stale_backfill`（見下），它需要知道「這則在佇列裡放多久了」，
所以走另一條路徑、由 `main()` 附加。

## blocker 一覽

| blocker | 觸發條件 | 由什麼設定控制 | 今天走得到嗎 |
|---|---|---|---|
| `placeholder_content` | body 任一處還有佔位詞 | `lib/notes.PLACEHOLDER_RE`（硬寫） | 走得到 |
| `thin_fact` | 「事實」段或 `summary` 短於門檻 | `readiness.thin_fact_min_chars` | 走得到 |
| `thin_research_analysis` | `category ∈ {research, paper}` 且「影響」<40 或「脈絡」<30 | 硬寫 | 走得到 |
| `generic_entity` | `company` 落在泛稱清單 | `GENERIC_ENTITY`（硬寫） | 走得到 |
| `missing_category` | `category` 空、或還是 `industry` | 硬寫 | 走得到 |
| `missing_keywords` | `keywords` 空 | — | 走得到 |
| `missing_track` | `track` 空 | — | 走得到 |
| `missing_evidence` | `evidence[]` 空 | — | 走得到 |
| `missing_primary_evidence` | `primary_evidence` 為 0 | — | 走得到（紅線 2 的執法點） |
| `low_confidence` | `confidence` 低於門檻 | `readiness.min_confidence` | 走得到 |
| `unmeasured_heat` | `heat` 有數字、但 `score_factors.propagationSignals` 為 0 | — | 走得到（見下） |
| `unsupported_heat` | `heat ≥ 門檻` 且（獨立來源 < 2 或 平台廣度 < 2） | `readiness.heat_*` 三個 | **走不到**，等社群線（見下） |
| `stale_backfill` | 回填的舊文在佇列裡過期 | `pulse-gate.main()` | 走得到，且是終端狀態 |

`warnings[]` 不擋發布，只標記。目前只有一條：`independent_sources < 2` →
「single-source fact; cross-source corroboration pending」。

## heat 那兩條：2026-07-26 的決定

### 量到的事實

`references/incidents/2026-07-26-heat-dead-terms.md` 量的（48 個 Event，之後複測 51 個結論不變）：
heat 公式六項裡有四項——`uniqueAuthors`(30 分)、`velocity`(20 分)、
`platformBreadth`(7 分)、`regionBreadth`(6 分)——**在全部 Event 上都是 0**。
實測 heat 最大值 32，理論上限 48，`heat_threshold` 是 70。

複測時多量到一件那份文件沒寫的事：這四項不是「資料還沒進來」，是
**`pulse-cluster.py` 呼叫 `score_event()` 時第四個參數直接寫死 `metrics=[]`**。
沒有任何程式碼曾經往那個參數裡放過東西。不是輸入端沒東西，是連接線沒有接。

### 為什麼不降門檻

`_config/gate.yaml` 早就寫了理由，這裡再確認一次：把 70 降到 45，
`unsupported_heat` 會開始有反應，但那個反應是假的——它會在
「單一來源 + 剛發布」的 Event 上觸發，而那跟傳播廣度沒有任何關係。
紅線 4 禁止把手工分數包裝成已測量熱度；**把門檻降到非熱度的數字搆得到的高度，
是同一件事換個方向做**。門檻不動。

### 為什麼也不重算權重

「把那 63 分重新分配給還活著的兩項，讓 heat 用滿 0–100」聽起來像在修，其實更糟：
一個由「獨立來源數 + 新鮮度」算出來、卻鋪滿 0–100 值域的數字，**比現在那個
8–32 更像一個真的量測**。要處理的問題是欄位名稱說熱度、量到的是別的；
把值域補滿只會讓這個誤會更難被發現。

### 所以：量不到就寫量不到（紅線 8）

`heat` 從 2026-07-26 起是**可為空的欄位**。四項傳播輸入全部為 0 時，
`score_event()` 回傳 `heat: None`，而不是一個由獨立來源數換算出來的數字。
同時新增一個記錄用因子：

```
score_factors.propagationSignals = 四項傳播輸入裡有幾項非零（authors / tweets / platforms / regions）
```

這個數字讓「我們什麼都沒量到」變成**寫在磁碟上的事實**，而不是要別人從四個 0
自己推論出來的東西。前台與儀表板遇到 `heat: None` 印「未量測」，不印 0——
印 0 是另一個謊，而且是更難察覺的那種（0 看起來像「量過了，很冷」）。

這件事有下游證據：`_config/narratives.yaml` 裡曾經有兩句 LLM 寫的敘述在引用那個
數字當論據（「四則皆單源、heat 偏低（8–14），還沒跨來源共振」）。敘述層開始
拿一個沒量過的數字推論，是紅線 2 與紅線 8 同時被繞過——**因為那個數字長得像
量過的**。這是「先把數字印出來，之後再說」的實際代價。

那兩句已於 2026-07-26 改掉，而且改的過程本身留下一課：它們待在 `lenses`，
是夜間鏈**永遠不會重寫**的欄位——上游把輸入改成「未量測」，擋得住新的謊，
擋不住已經寫出來的。現在敘述層有自己的擋線與規格：
`references/narrative-layer.md`。

### `unmeasured_heat`：把上面那句話變成一條會紅的線

規格寫了不等於守得住（`references/mutation-inventory.md` 整份在講這件事）。
所以新增一條 blocker：**`heat` 有數字、但 `propagationSignals` 為 0 → 擋**。

它守的是三個實際存在的入口：有人手改 frontmatter、遷移腳本寫壞、
以及最重要的——**未來有人把 heat 的無條件計算加回去**。那一天這條線會紅，
而不是網站再一次安靜地印出假熱度。它不是裝飾：`pulse-gate.py` 對它的判定
在 selftest 有正反兩面的釘子。

### `unsupported_heat`：誠實地記成「休眠」

這條不刪。它是紅線 4 的執法點，語意正確，只是它的輸入今天不存在——
`heat` 現在只在真的有傳播訊號時才有數字，所以 `heat ≥ 70` 這一關要等社群線
（M3）接上才走得到。**掛在那裡並註明為什麼，是誠實；假裝它在守，才是掩蓋**
（紅線 8）。它的行為在 selftest 有正反兩面的釘子（撐不住要擋、撐得住不擋），
所以社群線接上的那天它是活的，不是一段兩個月沒跑過的碼。

真正讓它復活的是社群／KOL 線（M3）。在那之前它休眠，這是刻意的、不是待辦——
所以 BACKLOG 裡沒有它的條目，這一段就是它的負責人。

## 為什麼 heat 與 value 不對讀者顯示（2026-08-11）

**heat 現在恆為「未量測」。** 四項傳播輸入（`velocity` / `platformBreadth` /
`regionBreadth` / `propagationSignals`）沒有任何量測管道，`scoring.py` 因此一律回
`None`，前台一路印「未量測」。那一格從上線到現在**沒有一天印過數字**。

一個永遠印同一句話的欄位，對讀者不是資訊是雜訊：它佔著事件卡片與詳情頁最顯眼
的位置，而它每天講的都是「這一格沒有內容」。所以 2026-08-11 起，heat 與 value
**從讀者看得到的地方全部下架**：事件卡片的 score 行、詳情頁的 hero 四格、首頁的
計數欄、四條傳播因子的比例條，以及 `dist/data/events.json` 的 `heat` 欄位。

### 這不是把不方便的數字藏起來，界線在這裡

下架的是**顯示**，不是欄位，也不是判準。以下一個都沒動：

| 還在的 | 誰在讀 |
|---|---|
| `Events/*.md` frontmatter 的 `heat` / `value` | `scoring.py` 寫、`pulse-gate` 讀 |
| `unmeasured_heat`（有數字但沒有傳播證據 → 擋） | `pulse-gate.evaluate()` |
| `unsupported_heat`（heat ≥ 門檻但廣度不足 → 擋） | 同上，休眠中 |
| 送給敘述層的 `heat: "未量測"` | `pulse-narrative-prep`，防止 LLM 拿 0 當論據 |
| `score_factors` 的四項傳播欄位 | 照樣寫進 frontmatter，只是不畫在讀者面前 |

換句話說：**heat 從「對讀者的宣稱」降級成「內部判準」。** 紅線 8 要的是
「量不到就說量不到」，而它現在的說法從「在每一張卡片上寫未量測」改成
「不在讀者面前出現，並在這份規格裡寫明為什麼」。第二種說法給的資訊更多，
因為它同時說出了「為什麼沒有」。

### 傳播訊號接上線那天要回來重讀

M3（社群／KOL 線）接上之後 heat 會開始有數字，那時候**要回到這一節重新決定**顯不
顯示——不要因為現在下架了就預設它永遠不顯示。這一段就是那個決定的負責人。

`value` 沒有這個問題：它是 `conf·0.40 + impact·0.40 + freshness·0.20` 的合成分，
對讀者沒有可解釋的意義，本來就只是內部排序用的數字。它下架不附條件。

### 判準守的是反向

selftest 原本守的是「heat 要印成未量測、而且不准畫比例條」。那幾條在這一版
**反轉**成「讀者頁面不准出現 heat / value」。只刪不反轉的話，下一個人會把它
當成回歸再加回去——這個 repo 有過「順手拿掉一個空操作，而沒有任何東西變紅」
的紀錄（變異清單第三十一輪）。

## 遷移與回滾

**遷移。** 磁碟上 51 個 Event 的 frontmatter 已經寫著 heat 數字，不動它們的話
vault 會處於一半新一半舊的狀態——而 `unmeasured_heat` 會把那 51 個全部擋下來。
`scripts/migrate-2026-07-26-heat-unmeasured.py` 一次性改寫：`heat → null`、
`score_factors.propagationSignals → 0`、`value` 依新權重重算。

它是**磁碟的純函式**：只讀既有 frontmatter 裡已經存在的 `confidence` /
`impact` / `score_factors.freshness`，不重抓、不讀時鐘、不重新聚類。同一棵樹
跑兩次結果一樣（第二次是 no-op）。

`value` 的新權重：heat 缺席時，原本 `heat·0.25` 的比重按比例分回還在的三項——

```
heat 有值： value = conf·0.30 + impact·0.30 + heat·0.25 + freshness·0.15
heat 為空： value = conf·0.40 + impact·0.40            + freshness·0.20
```

不是「把 0.25 丟掉」——那會讓所有 Event 的 value 上限變成 75，跟舊資料不可比。

**回滾。** `git revert` 那一個 commit。Events/*.md 在版本控制裡，遷移改的每一個
位元組都在 diff 裡，還原是精確的、不需要重跑任何抓取。這是這個改動敢做的前提：
它動的是磁碟上的既有資料（CONTRIBUTING「一定要走 PR 而且要特別小心的三類」的
第二類），而唯一能讓那件事安全的東西是 revert 一定回得去。

## 這一層不保證什麼

- **不保證擋下來的都該擋。** blocker 是規則，規則會誤傷。誤傷的出口是人去看
  `_dashboards/blocked.md`，不是放寬規則。
- **不保證放過的都對。** gate 檢查的是形狀（欄位在不在、長度夠不夠、分數過不過），
  不是內容真假。內容真假由證據層（`evidence-tiers`）與人工複審負責。
- **不保證設定檔改了就有效。** `gate.yaml` 裡有 13 個 key 沒有任何程式碼讀它，
  對照表在 `references/gate-config-status.md`。改門檻前先去那張表確認它接線了。
