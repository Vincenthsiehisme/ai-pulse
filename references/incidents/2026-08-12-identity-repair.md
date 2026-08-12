# 2026-08-12：六次模型發布被歸成兩件事

> 修正規則的那一輪是 `fix/identity-beats-similarity`（`references/attach-rule.md`
> 〈身分否決〉）。這一份是**歷史修復**的帳目：動了什麼、為什麼那樣動、
> 哪些東西我們決定不動。

## 症狀

`evt-2026-07-25-0fa594`「Claude Opus 5」，全 vault confidence 最高的那則（100）：

```
primary_evidence: 5
  rel=100  Claude Opus 5      ← 真的
  rel=100  Claude Opus 4.7    ← 另一次發布
  rel=100  Claude Opus 4.5    ← 另一次發布
  rel=100  Claude Opus 4.8    ← 另一次發布
  rel=100  Claude Opus 4.6    ← 另一次發布
```

`evt-2026-07-22-09b47d`「Claude Sonnet 5」同樣的形狀，而且更嚴重——
在修好之前的最後一班，它的證據清單長成這樣：

```
10 筆證據，8 筆身分衝突
  Claude Sonnet 4.5 / 4.6      （rel=100）
  Claude Opus 5 / 4.7 / 4.5 / 4.8 / 4.6、Claude Haiku 4.5   （rel=33）
```

一頁叫「Claude Sonnet 5」的事件，證據列的是 Opus 和 Haiku。

## 四層因果，前兩層在 fetch 端

```
1. _slug_to_title  /news/claude-opus-4-5 → 「Claude Opus 4 5」（小數點沒了）
2. event_fingerprint  版號組吃到第一個整數 → opus:4，四次發布塌成同一個鍵
3. title_tokens    len(t) > 1 丟掉單字元 → 「Opus 4 5」與「Opus 5」相似度 1.00
4. belongs_to_event  fingerprint 不同時不否決，直接落到相似度重新裁決
```

第 1 層是根。sitemap 沒有標題欄位，標題是從 URL 推導的，而 URL 的 `-`
同時是斷詞符與小數點。`_slug_to_title()` 的 docstring 當時寫著
「還原不準的代價由 cluster 的實體比對吸收」——**而 cluster 的實體比對
正是被這個不準打壞的那一層**。代價沒有被吸收，它一路走到 confidence。

## 這個形狀每一班都在長

規則修好的 PR 送出時，我在對照組量過一次「不修的話今晚會多掛什麼」。
那份預測與隔天的實測完全一致：

```
預測（對照組，2026-08-11）   Sonnet 5 會多掛 6 筆 rel=33
實測（nightly 4b093ec）      Sonnet 5 真的多了那 6 筆，一筆不差
```

身分衝突的證據總數 6 → 12。**這不是「歷史上有幾筆髒的」，是一個還在生長的形狀。**

## 分數的傷比標題聽起來小，要照實說

```
                    修復前 → 修復後
Sonnet 5  primary       10 →  2      confidence 83 → 83（沒動）
Opus 5    primary        5 →  1      confidence 100 → 94
兩則      independent     不變        （12 筆錯的全來自同一條來源）
```

`lib/scoring.py`：`confidence = authority·0.62 + min(獨立,4)·7 + min(primary,2)·10`。
**`primary` 在 2 就飽和**，所以 10 掉到 2 一格都沒動。而 `independent_sources`
從頭到尾沒被灌水過——12 筆錯的證據全部來自 `src-anthropic-news` 這一條來源，
連通分量算出來本來就是一個聲音。

也就是說：**這件事沒有汙染 KPI，它汙染的是「這一頁在說什麼」。**
所有數字都是綠的，而頁面的內容是錯的。這正是這個 repo 一直在抓的形態，
只是這次發生在最顯眼的一頁上。

## 做了什麼

```
1. 語料層   sitemap 來源的 title 依 URL 重新推導
            （9 個不同的標題，散在幾十天的語料裡）
2. Event    2 則事件的標題本身掉了版號，連 fingerprint 一起改
              evt-2026-07-22-4c0123  Claude Haiku 4 5 → Claude Haiku 4.5
              evt-2026-07-31-15c85e  Grok Imagine Video 1 5 → 1.5 References
3. 證據     身分衝突的搬家：有同指紋 Event 的搬回去，沒有的補寫一則
4. 重算     受影響的 Event 走真正的 rescore()，不自己重寫一份計分邏輯
```

## 補寫的六則，以及它們為什麼要自己承認

```
Claude Opus 4.5 / 4.6 / 4.7 / 4.8
Claude Sonnet 4.5 / 4.6
```

這六次發布**真的發生過**，而它們在 vault 裡的唯一痕跡就是那些掛錯的證據。
單純刪掉的話，我們會把一個「記錯了」換成一個「沒記」——而後者不會有任何
欄位顯示它發生過。

所以補寫，但每一則都帶著：

```yaml
recovered_by: identity-repair-2026-08-12
status: review
```

`status` 不給 `published`：**機器補的事件不該自己升到已發布**，
跟「升到 active 只有人能做」是同一條線。

### 為什麼不共用 `coverage: backfilled`

那一格已經有意思了——「事情發生時我們的來源還沒開始觀測」，
是 `lib/coverage.py` 每班重算的推導欄位。

而這六則的實際情況是：**我們當時看到了**（語料裡有 `first_observed_at`），
只是把檔案放錯抽屜。兩件事會同時成立，但要採取的行動完全不同：
`coverage: backfilled` 說的是「去補來源」，`recovered_by` 說的是「規則錯過」。
塞進同一格就分不出來。

規格見 `references/obsidian-schema.md`〈`recovered_by`〉。

## ref_now 用真正的現在，所以 diff 裡有兩種變動

`rescore()` 要一個「現在」。拿 `happened_at` 當現在會讓 `freshness` 變成 100、
`value` 跟著虛漲——而那個漲跟這次修復一點關係都沒有。

所以用真正的現在，寫出來的年齡相關欄位就跟「今晚那班如果碰到這則會寫的值」
一致。代價是 diff 裡會同時出現：

```
因為修復而變的    confidence / primary_evidence / independent_sources
因為時間而變的    freshness / heat / value
```

遷移腳本的輸出把兩者分開印。**看 diff 的時候不要混在一起看。**

## 冪等，而且是冪等檢查抓到一個 bug

這支可以重跑：跑第二次應該印出「要寫的檔：0」。

第一版不是。第 2 步（修 Event 標題）改的是記憶體裡的 `fm`，
而只有「有錯掛證據」的事件會被寫出去——於是那兩則**只改了標題**的事件
改在記憶體裡、沒落地，跑第二次還會再報一次同樣的改動。

**抓到它的是冪等性檢查，不是任何一條斷言。** 一個一次性遷移如果只跑一次
就不會有人發現這個 bug，而它的後果是「報告說改了、檔案沒改」。

## 我們決定不動的東西

**`entities.yaml` 裡 `claude` 這個 product_line 沒有 `parent`。**
所以補寫的六則 `infer_company()` 回 `industry` 而不是 `Anthropic`，
會觸發 `generic_entity` blocker。

這是**既有的字典缺口**，不是這次修復造成的，而且它影響的不只這六則。
在這裡順手補一行看起來很划算，但那會讓這個 PR 同時在改兩件事，
而字典的 parent 鏈該怎麼補是它自己的題目。

留在這裡當紀錄。補寫的六則走 `status: review`，人看的時候會看到那個 blocker。

**`title_tokens()` 仍然丟掉單字元。** `Claude Opus 4.5` 的 token 集合仍然是
`{claude, opus}`，跟 `Claude Opus 5` 的相似度仍然是 1.00。這一輪沒有動它，
因為身分否決在它之前就結束了——它只在「兩邊至少一邊沒有 fingerprint」時當家。
理由與數字見 `references/attach-rule.md`〈這一輪不動 tokenizer〉。
