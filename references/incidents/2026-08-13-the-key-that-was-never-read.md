# 2026-08-13：設定檔一直是對的，是讀的人拿錯鑰匙

> 一支函式、兩個獨立的錯、零紅燈。發現它的不是任何測試，是有人問
> 「為什麼那六則補寫的 Claude 事件 `company` 是 `industry`」。

## 症狀

`pulse-monitor` 在叫：

```
[alert] 有事件卡在 review 已在庫裡放 18 天（門檻 2）
待處理卡最久的 5 則：Claude Sonnet 4.6 / 4.5、Claude Opus 4.6 / 4.8 / 4.7
       blockers: placeholder_content, thin_fact, generic_entity, ...
```

`generic_entity` 這一格的意思是「`company` 是 `industry`」——而那六則是
Anthropic 的模型發布，公司再明確不過。

## 兩個錯，在同一支函式裡

`pulse-cluster.load_entities()`：

```python
for key in ("companies", "product_lines", "products", "technologies", "policy"):
    ...
    out[e["id"]] = (e.get("canonical") or e["id"], e.get("term_type"), e.get("parent"))
```

**一、分節清單是手寫的第二份，而且有兩個名字不存在。**

```
程式讀的     companies  product_lines  products    technologies  policy
檔案實際有   companies  product_lines  infrastructure  frameworks  technologies  policies
```

`products` 與 `policy` 永遠讀到空的；`infrastructure`（7）、`frameworks`（12）、
`policies`（4）**整批沒被載入**。六個分節共 93 個實體，實際只載了 70 個。

而單一真相源一直都在：`lib/entities.ENTITY_SECTIONS`——`build_matcher()`
用的就是它。**同一份清單兩個消費端，只釘住一個。**
這是 `SECTIONS`（六個檔）、`RUN_LIFECYCLES`（四個檔）之後**第三次**同一個病。

**二、公司欄位讀成 `parent`。**

`entities.yaml` 的 23 個 product_line **全部**帶著 `company: <公司 id>`，
而且每一個都指到存在的公司。**沒有任何一個有 `parent`。**

於是 `infer_company()` 的第二段——

```python
# 2) 命中 product_line/product → 往上解析到 parent 公司
```

——**從來沒有執行成功過**。它是死碼。所有只命中產品線的訊號都落到
`"industry"` 兜底，然後被 gate 掛上 `generic_entity`。

## `parent` 不是打錯，它是另一個關係

這一格特別容易看走眼：`parent` **確實**存在於這份字典裡，只是在別的層。

```
company  層 → parent    企業層級（google-deepmind 的 parent 是 google）
其餘各層 → company   所屬公司（claude 的 company 是 anthropic）
```

兩種關係、兩個欄位名。讀的人拿了上面那把鑰匙去開下面那道門。

所以修正之後的 selftest 是**兩條**，把它們釘開：非 company 的條目不准用
`parent`，company 層的 `parent` 要指到存在的公司。只釘一條會讓另一種筆誤溜過去。

## 量到的影響

```
載入的實體      70 → 93
company=industry 的事件   12 則
   其中 entity_hits 有產品線可解的     7 則（6 則 claude → Anthropic、1 則 grok → xAI）
   其中一個實體都沒命中的               5 則（那不是這個 bug）
```

七則裡有六則正是 `pulse-monitor` 現在在叫的那批。

## 為什麼沒有任何東西變紅

兩個錯的後果都是**少**，不是**錯**：

- 少載入的實體 → 那些詞從此不會被 `infer_company` 認得，但比對表（`build_matcher`）
  用的是正確的清單，所以 `entity_hits` **照樣命中**——命中了卻解不出公司
- 解不出公司 → 落到 `industry`，而 `industry` 是一個**設計內的合法值**
  （註解寫著「泛稱 → 會觸發 generic_entity blocker，待 enrich 修正」）

也就是說，這個 bug 的產物跟「這則新聞真的認不出主體」長得一模一樣。
`generic_entity` 每天都在亮，而它亮的理由有兩種，畫面上分不出來。

## 這次是怎麼被發現的

不是測試。是有人問「為什麼這六則的 `company` 是 `industry`」，
然後往回追了三層：`generic_entity` → `infer_company` → `load_entities`。

**第一個假設是「字典缺 `claude` 的 parent，補一行就好」。**
去查的時候才發現 23 個 product_line 的 `parent` 全是空的——
如果只補 `claude` 那一行，會補在一個沒有人讀的欄位上，
症狀不會消失，而下一個人會更困惑。

**先量全體再動手，是這一輪唯一做對的事。**
