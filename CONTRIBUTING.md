# 改這個 repo 的規矩

一句話：**發現問題，自己開 PR，不要只回報、也不要直接推 main。**

這條同時適用於人跟自動化代理（Cowork 排程任務、Claude session）。代理發現問題
時的正確反應不是「在摘要裡寫一段『建議修』」，而是開一條分支、把修好的碼推上來、
留一個可以被審的 PR。回報不修，等於把問題留在原地還多佔一行摘要。

---

## 兩條路，別走錯

這個 repo 裡跑的東西分兩種，走的路不一樣。分不清楚會出事：走錯第一條，夜裡的鏈
會卡住；走錯第二條，沒人審過的規則會直接決定什麼上線。

### 一、資料 commit —— 直推 `main`，**不要**改成走 PR

`.github/workflows/data-refresh.yml` 每兩小時跑一班，抓取→評分→聚類→門禁→
渲染，然後 `chore: nightly refresh` 直接推 `main`。它動到的是：

```
_corpus/**  _probe/**  Events/**  Sources/**  _dashboards/**  dist/**
Tracks/**   Actors/**    ← 2026-07-27 新增，pulse-entity-notes.py 的維度節點頁
_config/sources.yaml     ← 只有兩個機器欄位，見下一段
_config/narratives.yaml  ← 每夜 enrich 的主線敘事（now / next），見下一段
```

`_config/narratives.yaml` 跟 `sources.yaml` 一樣是「人跟機器都會寫」的檔：主線的
`thesis` / `lenses`（編輯層）歸人、走 PR；每夜 enrich 只重寫 `now` / `next` 兩段，
由 `pulse-narrative-apply.py` 就地寫回、隨資料 commit 直推 `main`（實例：`a52e6c4`
「nightly: enrich + narrative 2026-07-24」，bot 直推，未經 PR）。改成走 PR 一樣會
卡死每夜鏈。所以規矩同樣按欄位分：`now` / `next` 歸鏈直推，`thesis` / `lenses` 歸人開 PR。

這些是鏈自己的產物。把它們改成開 PR 會有兩個後果：一天 12 班就是 12 個沒人會看
的 PR；而且下一班的 rebase 基準永遠停在沒合併的狀態，鏈直接卡死。所以這條路刻意
留著直推，**不是漏掉，是設計**。

同理，人也不要手改這些檔案再送 PR ——下一班就被覆蓋掉了。要改資料，改的是產生
資料的規則（那就落到第二條）。

#### `_config/sources.yaml` 是唯一一個人跟機器都會寫的檔

它同時是人維護的來源清單，也是鏈的狀態存放處。每班第一步的
`pulse-robots-recheck.py --stale-days 1 --apply --revive` 會就地改寫這兩個欄位，
異動記進 `_probe/source-history.jsonl`，然後隨資料 commit 直推 `main`：

```
lifecycle    robots_ok
```

實例：`4ce6043`（2026-07-25 05:21，bot 直推）把 `src-kol-raschka` 的
`robots_ok: null → true`、`lifecycle: dormant → probing`——robots 重驗實測放行，
機器自己改的，沒有經過 PR。

**所以這個檔的規矩按欄位分，不按檔案分。** 上面兩個欄位歸鏈；其餘一切（新增或
移除來源、`tier`、`role`、`quota_per_run`、`can_satisfy_primary`、`adapter`、
`coverage_watch` 的門檻）歸人，走第二條路開 PR。

兩個實務提醒：

**手改 `lifecycle` 沒有意義。** 下一次 robots 重驗會依實測結果覆蓋掉。要停用一條
來源，用人為停用那條路——`--revive` 刻意不碰人為停用的來源，把 `lifecycle` 直接
打成 `dormant` 則會被下一班救回來。

**寫回用 ruamel round-trip，註解會完整保留**（刻意的，`sources.yaml` 的註解是文件
的一部分），但手寫的對齊空白會被重排成 ruamel 的標準格式。所以你手改完 push 之
後，下一班常會出現一個「整份檔案都動了」的 diff——那是重排，不是有人偷改你的設
定，別追。`4ce6043` 那個 1019 行的 diff 就是這樣來的（前一次人手編輯是 `22eefde`）。

### 二、其他一律走 PR

```
scripts/**  .github/workflows/**  _config/**  *.md  其餘所有檔案
（`_config/sources.yaml` 的 lifecycle / robots_ok 除外——那兩欄歸鏈，見上）
（`_config/narratives.yaml` 的 now / next 除外——那兩段歸鏈，見上）
```

含腳本、CI、`_config/*.yaml`（門檻、來源、實體字典）、文件。判斷邏輯與門禁門檻
都住在這裡，這一層是「規則決定發不發」的規則本身——沒被審過就不該生效。

流程：

```bash
git checkout -b fix/短描述        # 或 docs/ chore/ feat/
# 改、測
python3 scripts/test-pulse-score.py
git commit                        # commit message 寫「為什麼」，不是「改了什麼」
git push -u origin fix/短描述
# 開 PR
```

---

## PR 內容要求

**commit message 與 PR 說明寫「為什麼」。** diff 已經說了改什麼，重複一遍沒有
資訊量。要寫的是：原本會怎麼壞、壞的時候看得出來嗎、為什麼選這個修法。

**靜默失敗要講清楚。** 這個系統最貴的壞法不是報錯，是數字看起來正常但其實是空
轉。如果修的是這一類，說明裡要寫「原本壞掉的時候儀表板會顯示什麼」。

**刻意不做的事要寫出來。** 順手擴大 blast radius 是這個 repo 最容易犯的錯（例：
為了讓 `keywords` 欄位好看而擴充 `STOP_WORDS`，結果悄悄改掉聚類結果）。把「我
本來可以順便改但沒改，理由是 X」寫進說明，審的人才知道你想過。

**證據要能重跑。** 說「修好了」要附能複製的驗證：測試輸出、對真實 vault 的實跑
數字、或重現腳本。實跑數字前後都要有。

**假問題比不報問題更糟（紅線 8：對自己誠實）。** 懷疑的東西先驗證再開 PR。驗不
出來就明講「查過、不成立、不開 PR」，不要為了湊產出硬送。

---

## 一定要走 PR 而且要特別小心的三類

**排名 / 門檻 / schema（紅線 9：docs-first）。** 改 `_config/gate.yaml` 門檻、
`lib/cluster.py` 的 `STOP_WORDS`、評分權重、frontmatter 欄位——先改對應說明文件
（本 repo 的 schema 說明住在腳本 docstring 與 `_config/*.yaml` 註解裡），再改
碼，附遷移與回滾方式。

`STOP_WORDS` 特別容易誤傷：它參與 `title_similarity`，也就是參與「兩則標題算不
算同一個 Event」。加一個詞就是改聚類結果，而且沒有任何測試會紅。

**任何會讓既有資料改變判定結果的改動。** 典型例子：偵測用的正則。`lib/notes.py`
的 `PLACEHOLDER_RE` 認得簡體舊寫法，是因為 vault 裡有既有 Event 用舊寫法；拿掉
它，那些未潤稿的事件會突然通過 `placeholder_content`，佔位文字直接上線。改這種
東西之前，先問「磁碟上已經存在的資料會不會因此換一個結局」。

**確定性（紅線 1）。** 這條鏈對外的承諾是同輸入同輸出。任何 `list(某個 set)`、
任何字典迭代順序、任何 `Date.now()` 進到輸出的地方，都是在破壞這個承諾。CPython
的字串雜湊每個行程都重新隨機化，所以「跑兩次比一比」在同一個行程裡驗不出來——
測試要寫死期望值。

---

## 憑證

**token 只出現在 clone / push 指令裡，絕不寫進這個 repo 任何檔案、不寫進 commit、
不印在摘要裡。**（紅線 6）
