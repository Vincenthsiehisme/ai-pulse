# AI-Pulse：應做而未做（已排序）

盤點時間 2026-07-26（第二輪）。`main` 在 `8a6c1e8`，遠端 **28 條分支、其中 4 條未併**，
`main` 上的 selftest **224/224**。四條未併分支各自的 selftest：
`fix/observed-counts-item-days` 235、`fix/health-snapshot-dry-run` 243、
`fix/coverage-uses-own-clock` 233、`test/monitor-exit-codes` 241。

> 同日稍晚追記：這份清單所在的 `docs/backlog-refresh` 又長出了變異盤點層
> （P3），selftest 到 **238**，未併分支變成 **5 條**。這幾個數字也一樣，
> 在合併之前都只描述分支、不描述 `main`。

> 再追記（同日）：P2 做完，`fix/heat-claims-a-measurement` 上 selftest **247**、
> 變異清單 **25 條**（新增 M21–M25，全部被殺），未併分支 **6 條**。
> 一樣：這三個數字描述的是那條分支，`main` 上仍然是 224。

> **三追記（同日傍晚）——上面那句「`main` 上仍然是 224」已經不成立了。**
> 六條併掉五條（PR #2–#7），`main` 在 `5c9e30d`，selftest **286/286**。
> 剩下 `test/monitor-exit-codes` 一條，它是唯一一條**併不進去**的：從 `8a6c1e8`
> 長出來，之後 `main` 進了六個 PR，`scripts/selftest.py` 兩邊各自往同一個錨點
> 新增，GitHub 判衝突。已在 `fix/monitor-exit-codes-vs-main` 上把 `main` 併回去
> 解掉——衝突的實體是「兩邊都在同一行後面加東西」，不是同一段被改成兩個樣子，
> 所以兩邊都留、斷言一個都沒改。合併後 selftest **303/303**、
> **變異 25 條全殺、0 存活**（那四條掛了兩輪的存活記錄一起結案）。
> 遠端 **31 條分支**。
>
> 這幾個數字一樣是量出來的不是估的：`git branch -r --no-merged origin/main`、
> `python3 scripts/selftest.py`、`python3 scripts/mutate.py`。

> 上一版這一段寫的是「`main` 在 `1ce43e9`，遠端零未合併分支，本地 selftest 222/222」。
> 三個數字**現在全是假的**。清單自己過期不會讓任何東西變紅——這正是這份清單第一條
> 排序準則在講的病，只是這次得的是清單本人。所以盤點結果一律附「怎麼量出來的」。

這份清單只寫「**已知有問題、但還沒動手**」的事。修掉的不列；**修好了但還沒併進
`main` 的，算沒修**（見 P1）。

## 排序準則

每一條的位置由兩個問題決定，不由它屬於哪個模組決定：

1. **它壞掉的時候，有沒有東西會變紅？** 不會變紅的排前面。會紅的東西自己會來找人，
   不會紅的東西要靠人記得。
2. **它現在是不是正在輸出一個錯的數字？** 「沉默的缺工」比不上「有聲的假數字」——
   空欄位沒人會信，假數字沒人會查。

所以順序大致是：**有時限 → 修了但沒生效 → 正在騙人且不會紅 → 守門的東西自己沒被守 →
寫好了沒人叫 → 資料進不來 → 做了一半 → 要你動手**。

| # | 事 | 壞了會紅嗎 | 現在在騙人嗎 |
|---|---|---|---|
| P0 | 07-27 cron 收班 | 不會 | — |
| P1 | ~~六條修好的分支還躺在遠端~~ **併掉五條，剩解衝突那條** | 不會 | 剩最後一條 |
| P2 | ~~heat 印出一個沒量過的數字~~ **已併（PR #7）** | 會（selftest 286 + M21–M25） | 否（改成 null 了） |
| P2.5 | ~~`narratives.yaml` 有依那個假數字寫成的句子~~ **已改，在 `fix/narrative-drops-the-fake-heat` 上** | 會（selftest 312 + M26–M28） | 否（兩句都重寫了） |
| P3 | ~~變異盤點已做成工具，但也還沒併~~ **已併** | 會（`main` 上 25 條全殺） | 否 |
| P4 | 未接線的 gate key（清單本身**已改成機械列舉**，在 `fix/gate-keys-unmarked` 上；接線的工還在） | 不會（已標記，且漏標會紅） | 部分（止血補強，本體未修） |
| P5 | 三條「可跑但零產出」的來源 | 不會 | — |
| P6 | 20 家 pending 覆蓋盲點 | 刻意不會 | 否（誠實掛著） |
| P7 | people layer 第三步 | 不會 | — |
| P8 | `_corpus/` 累不累積 | — | — |
| P9 | 12 則 `stale_backfill` 沒有出口 | 不會 | 否 |
| P10 | 24 條已合併分支刪不掉 | — | — |

---

## P0 — 07-27 必須發生的收班（唯一有時限的一條）

`data-refresh.yml` 現在的 cron 是 `0 */2 * * *`，一天 12 班；`robots --stale-days`
也一起從 7 調成 1。排程任務 `trig_01F52Q24UntdNVTd3DWbxFgs` 會在
**2026-07-27 12:00Z** 觸發，把兩個值改回 `0 16 * * *` 與 7。

一天 12 次去打人家的 robots.txt 是不禮貌的，而且我們自己沒有那個量的需求。

排 P0 只有一個理由：**它是這份清單上唯一一條「今天不做，明天就沒得做」的事。**
其他每一條都可以晚一週，這條晚一週就是連續一週失禮。

### 兩層都還在（2026-07-26 複查）

| 何時 | 任務 | 狀態 |
|---|---|---|
| 2026-07-27 12:00Z | `trig_01F52Q24UntdNVTd3DWbxFgs` | enabled，next_run 正確 |
| 每週一 16:00Z | `trig_015SHn9yjL6LtA9TsbeyGCdo` | enabled，首跑 2026-07-27 16:04Z |

第二層不是備援心態，是這個 repo 的核心毛病：**一個只靠單次觸發的收班安排，如果沒
觸發，沒有任何東西會變紅**。所以第二層刻意**不去查第一層跑了沒**（那又是一個代理
指標），只讀 `data-refresh.yml` 裡的實際值：cron 一天超過一班、或任一處
`--stale-days < 7`，就改回來。收班不是改設計，所以它直接推 `main`、不開 PR。

也就是說這個頻率上限現在是**每週自癒**的，不是靠人記得。剩下要人管的只有一件：
如果連禮貌檢查也沒跑到，那就真的沒人管了 —— 但那需要兩個獨立的排程同時失效。

---

## P1 — ~~六條修好的分支還躺在遠端，`main` 上一條都沒生效~~（併掉五條，剩最後一條）

```
$ git branch -r --no-merged origin/main        # 2026-07-26 傍晚
  fix/monitor-exit-codes-vs-main
  test/monitor-exit-codes                      # ← 同一件事，前者是解完衝突的版本
```

| 分支 | 原編號 | 修了什麼 | selftest | 狀態 |
|---|---|---|---|---|
| `fix/observed-counts-item-days` | 舊 P1 | `Sources/*.md` 不再把「量不到」印成「0 筆」；`items_observed` 改數相異 `(source_id, url)`；`events_bound` 排除 `dropped` | 235 | **已併 #3** |
| `fix/health-snapshot-dry-run` | 舊 P2+P3 | 隔離候選真的寫進磁碟快照（機器交棒給人的唯一介面接回來了）；`--json` 這種只看的跑法不再改持久狀態 | 243 | **已併 #2** |
| `fix/coverage-uses-own-clock` | 舊 P4 | 沉默判準改用每條實體自己的 `first_fetch_at`，不再拿整個語料庫的長度當尺 | 233 | **已併 #4** |
| `docs/backlog-refresh` | 本檔 + P3 | 這份清單本身；變異盤點層（`scripts/mutate.py` + `mutations.yaml` + 獨立工作流），並補掉它第一輪抓到的五個洞 | 238 | **已併** |
| `fix/heat-claims-a-measurement` | P2 | `heat` 沒量到就寫 null 不編數字；新 blocker `unmeasured_heat`；`references/readiness-gate.md`（SKILL.md 引用了 v1 就存在、但這個檔一直沒有）；51 則遷移 + 回滾 | 247 | **已併 #7** |
| `test/monitor-exit-codes` | 舊 P6 (a/c/d) | 死人開關的 exit code 走真子行程釘住；`FM_FROM_CONFIG` 白名單邊界改由行為守；`ingested_at` 黏性改成真的跑第二輪 | 241 | **衝突，用下一列** |
| `fix/monitor-exit-codes-vs-main` | 同上 | 上一列 + 把 `main` 併回去解掉衝突 + 那四條過期的存活記錄 | **303** | 待併 |

### 為什麼只有這一條併不進去

它是 `8a6c1e8` 長出來的，之後 `main` 進了 #2–#7。`scripts/selftest.py` 兩邊
各自在「來源頁白名單」那條之後新增了一段：這邊加 `render()` 的行為邊界（紅線 6），
`main` 那邊加 `items_observed` 量不到 ≠ 量到 0（紅線 8）。**兩段互不相干，
只是恰好貼在同一行後面**，git 沒有辦法自己知道這件事，所以判衝突。

解法就是兩邊都留。**一個斷言都沒有改**——這條分支的 13 個 exit code 釘子本來就是
寫給 `fix/coverage-uses-own-clock` 之後的 `pulse-monitor.py` 的（註解裡明寫
「新舊兩種護欄（history_days / observed_days）下都該判 silent」），併上來原封不動全過。

### 併進來之後量到的第一件事

那四條在 `mutations.yaml` 上掛了兩輪 `survives: true` 的變異，**全部倒了**。
而且是 `mutate.py` 自己判紅告訴我的，不是我記得去看：

```
25 條：21 被殺、0 存活（清單有記）、4 要人管
  [stale-record] M01 monitor 的 main() 直接回 0 …  ← 已經有測試守住了，清單該更新
```

它們的 `why` 從 merge 那一刻起就是假的（寫著「還沒併進 main」）。`survives: true`
卻被殺掉會判紅，這是 `mutations.yaml` 開頭那段「兩個方向都會被比對」第一次真的
付現。**一份不會抱怨自己過期的盤點清單，跟沒有清單的差別只是心裡比較踏實。**

「修好了但沒併進 `main` 的，算沒修」這句話這次也被量了一次：這四條在
`test/monitor-exit-codes` 上被殺是中午的事，在 `main` 上被殺是同一天傍晚。
中間那幾個小時，`main` 的 CI 對 `return rc → return 0` 一無所知——分支上的測試
寫得再好，都不會有任何一班跑到它。

**還要人動手的原因**：這個環境的 proxy 擋掉 GitHub API（403），我開不了 PR；
`git push origin main` 也被 classifier 擋下（跟 repo 的分支保護無關，是這個
session 自己的護欄）。分支已經推上去而且**現在沒有衝突了**，網頁上按一下即可。

---

## P2 — ~~`unsupported_heat` 從上線到現在一次都沒有擋過東西~~（**已修，在 `fix/heat-claims-a-measurement` 上**）

> 2026-07-26 改寫。原本這條寫著「要你先決定方向我才動」；方向決定了，也做完了，
> 等併。決策與規格：`references/readiness-gate.md`。

**題目比原本寫的嚴重。** 舊敘述說「門檻在值域外，所以這條 blocker 走不到」——
走不到只是症狀。真正的問題是 `heat` **永遠算得出一個數字，而那個數字量的不是熱度**。

四項傳播輸入（`uniqueAuthors` 30、`velocity` 20、`platformBreadth` 7、
`regionBreadth` 6，共 63 分）在 51 個 Event 上全是 0。舊敘述說那是「輸入不存在、
來源形態量不出來」——**那句話是錯的**。`pulse-cluster.py:144` 呼叫
`scoring.score_event(...)` 時第四個參數直接寫死 `metrics=[]`。
**不是輸入端沒東西，是連接線沒有接。** 沒有任何東西曾經被接到那個參數上。

而下游真的把那個數字當量過的用了：`_config/narratives.yaml` 裡有 LLM 依它寫成的
句子（「四則皆單源、heat 偏低（8–14），還沒跨來源共振」）。一個沒接線的欄位變成
敘述層的論據——紅線 2 與紅線 8 同時被繞過，**因為那個數字看起來像量出來的**。

### 兩條原本寫在這裡的修法都被否決了

上面那段舊文字建議「把門檻降到實際值域裡」。`_config/gate.yaml` 自己的註解則
反對它（「正確的修法是去真的收集社群指標，**不是**把 70 調到 45」）。
**repo 內部本來就有這個分歧**，這次站在 gate.yaml 那邊：降門檻會讓
`unsupported_heat` 開始有反應，但那個反應是假的——它會對「單一來源 + 剛發布」
發火，跟傳播沒有關係（紅線 4）。

重算權重把 63 分分給還活著的兩項也否決：值域補滿之後，一個 0–100 的「熱度」
看起來**比現在的 8–32 更像**真的量出來的。把謊講得更順不是修好。

補來源那條路要等 M3（X／社群線 M1 不接、已拍板）。所以中間這段時間唯一誠實的
動作是第三條——兩份既有文件都沒走的那條：**不要輸出那個數字**。

### 做了什麼

`heat` 可為 null；`score_factors.propagationSignals` 記下四項裡有幾項非零；
新 blocker `unmeasured_heat` 擋下「有數字但 propagationSignals 為 0」；
前台與敘述層印／送「未量測」而不是 0（**0 會被讀成「量過了，很冷」**）。
三個門檻刻意不動，`unsupported_heat` 保留並誠實記成「休眠，等 M3」，
selftest 釘住「四項餵滿時 heat 跨得過 70」——那條紅了才表示門檻該重談。

遷移 51 則，`value` +10 ~ +14（平均 +12.00），回滾 = `git revert`。
selftest 238 → 247，`mutations.yaml` 加 M21–M25，全部被殺。

### 這一輪掉出來的兩個新發現（都還沒處理）

1. **`_config/narratives.yaml` 裡有依假數字寫成的句子，還在站上。** 遷移只改了
   Events 的 frontmatter，改不到已經寫成散文的結論。那幾句要重寫——但重寫是敘述層
   的事（LLM 寫、過 speak-human-tw），不是這個 PR 的範圍。**排 P2.5，見下。**
2. **`value` 是一個沒有任何消費者的計算欄位。** `pulse-render.py` 只依日期排序，
   全站沒有任何地方依 `value` 排序，`dist/index.html` 裡出現 0 次 "value"。
   所以這次遷移的 rank delta（36/51 換位、最大位移 12 名）**不是使用者看得到的
   排名變動**，只是顯示值變動——這件事必須誠實講清楚，不然聽起來像改了排名。
   一個沒人用的分數欄位本身就值得問：它是要接上，還是該刪掉。**排 P8.5。**

---

## P2.5 — ~~`_config/narratives.yaml` 裡有拿假數字當論據寫成的句子~~（**已修，在 `fix/narrative-drops-the-fake-heat` 上**）

P2 修好了數字的源頭，但**已經寫成散文的結論改不到**。站上原本有這兩句：

> `infra-cost` → lenses[投資人]：「四則皆單源、heat 偏低（8–14），還沒跨來源共振」
> `product-market` → lenses[投資人]：「目前只有官方發布、無採用數字，heat 8–10 偏低」

`heat 8–14` 是那個沒接線的欄位算出來的，「還沒跨來源共振」是從它推出來的結論。
數字改成 `null` 了，這兩句話卻還在。

排在這裡而不是 P2 裡面，是因為修法不同：這是敘述層的活，要重寫、要過
speak-human-tw，不是改碼。它是紅線 2「證據撐不住的那一層寫『（證據不足，待補）』」
的直接應用——**沒量到的東西不該有結論**。

### 動手之後才看見的那一半

原本以為這條就是改兩句話。改之前先去看那兩句待在哪一格，才發現它們都在
`lenses`——而 `lenses` 是夜間鏈**永遠不會重寫**的欄位（`thesis` 也是；會被重寫的
只有 `now` / `next`）。也就是說 P2 在 `pulse-narrative-prep.py` 那端把輸入從 0
改成「未量測」，**不管跑幾百班都碰不到這兩句**。

**這是同一個病的又一個實例：用「入口已經修好」代理「站上沒有假話」。**
兩者在正常路徑上一致，分岔的地方正好是那些不再被任何流程碰到的角落——
而不再被碰到，正是它們最需要被檢查的理由。堵住上游只擋得住新的謊。

所以只改文字會用同樣的方式再爛一次。這一輪做了四件：

| | 做了什麼 |
|---|---|
| 規格 | `references/narrative-layer.md`（紅線 9，先寫這個）：誰寫哪一格、量化熱度宣稱的判準、命中之後做什麼、以及**這一層不保證什麼** |
| 判準＋執法 | `scripts/lib/narrative_guard.py` 找出「熱度／heat 後 12 字內有數字、且窗口內沒有否定詞」；`pulse-narrative-apply.py` 命中就**拒收該欄位**（不自動改寫——改寫等於確定性腳本自己編一句話），該班回非零（靜靜跳過等於一顆永遠綠的燈） |
| 不腐爛 | selftest +9 條，其中一條直接掃 `_config/narratives.yaml` **全檔含 `thesis` 與 `lenses`**——apply 只看得到當班寫入的東西，躺著的句子要靠這條 |
| 守擋線本身 | `mutations.yaml` 加 M26–M28：判準永遠豁免、命中照樣寫進去、拒收了卻回 0。**堵一個出口不等於堵住**，三條是三條互不相干的說謊路徑 |

重寫用的是量出來的事實，不是換個講法：51 則 Event 的 `heat` 全部是 `null`、
`propagationSignals` 全部是 0；`基礎設施與成本` 12 則已發布事件 **12/12** 獨立來源
數為 1，`產品與商業驗證` **11/11** 同樣。所以講得出口的是「沒有第二個獨立聲音」，
不是「熱度低」——後者需要一個我們沒有的量測。

分支上量到的：selftest **312/312**、變異 **28 條全殺、0 存活**。

---

## P3 — 變異盤點是手工做的，所以它一定會過期（而且已經過期了）

上一版寫「94 個注入點裡 47 個存活」。那是 **174 條測試**時的數字。今天 `main` 上是
224 條，四條分支上是 233–243 條，**那個比例現在沒有任何意義**，但它還印在清單上，
看起來像個現況。這就是清單本人得的病。

`test/monitor-exit-codes` 那一輪也是手工的：一條一條 `sed` 進去、跑 selftest、
看幾條紅、再還原。過程中踩到兩個坑，都值得寫進工具裡：

- **針腳不唯一會假裝成「存活」**。needle `'        if r.get("unenriched_undated"):'`
  同時命中 console print 與 `[alert]` 兩個區塊，`str.replace(a, b, 1)` 改到了前者，
  於是 alert 那條路徑根本沒被動過，selftest 全綠 —— 差一點就得出「這個釘子不存在」
  的結論。守則：**注入前先 `assert s.count(needle) == 1`**。
- **改壞語法不算變異**。一個讓 `render()` 直接 raise 的改動會讓 selftest 紅，但那
  紅的是崩潰不是斷言，量到的東西是假的。守則：注入後要能跑得完才算數。

**已經做完（在 `docs/backlog-refresh` 上，同樣未併）**：規格
`references/mutation-inventory.md`、清單 `scripts/mutations.yaml`（20 條，P2 之後 25 條）、
跑法 `scripts/mutate.py`、獨立工作流 `.github/workflows/mutation.yml`。
selftest 那一端只做 0.5 秒的鮮度檢查（針腳還在不在），慢的那一半留給獨立工作流。

第一輪跑出來 **16 被殺、4 存活**，四條存活的全部指向 P1（`main` 上沒有東西守著
死人開關的出口與白名單邊界）。過程中另外發生兩件值得記的事：

- **五個原本以為守得住、其實沒人守的地方**：`health()` 的「從來沒抓到過」判成綠燈、
  `missing_primary_evidence`（紅線 2 的執法點）、`unsupported_heat`（紅線 4）、
  聚類的 96 小時窗口、keywords 的順序。其中 `pulse-gate.py` 是**唯一**決定發不發的
  地方，而在這一輪之前 selftest 從來沒有 import 過它——把那兩行 `blockers.append`
  刪掉，224 條測試一條都不會紅。**五個都當場補了行為釘子，不是掛在這裡。**
- **工具自己犯了它要抓的病**：selftest 新加的「每個針腳剛好出現一次」在注入期間
  必紅（針腳正被換掉），於是**每一條變異都「被殺」**，kill 訊號變成常數，四條已知
  的存活者全被誤判。修法與理由寫在規格的「坑三」。

先做工具再補數字，順序不能反：先補數字就是再生產一個一樣會過期的東西。所以這一條
現在不留任何數字在清單上——要數字就跑 `python3 scripts/mutate.py`。

（舊 P6 的另外三個子項——exit code 測試、白名單邊界、`ingested_at` 黏性——已經在
`test/monitor-exit-codes` 上做完，等併，見 P1。規格寫在
`references/health-alarms.md`「算對了不等於會叫」那一節。）

---

## P4 — `gate.yaml` 有一批 key 沒有任何程式碼讀它

`docs/gate-unconsumed`（已併）把它們標成 `⚠ 未接線`，並用 selftest 釘住標記，
所以**現在不會再騙人了**——這也是它排在這裡而不是更前面的理由。標記不等於修好：

### 動手之前先發現：那張清單自己是手寫的（2026-07-26 傍晚，`fix/gate-keys-unmarked`）

上面標題原本寫「12 個」，而那個 12 是**手工數的**；`selftest.py` 也是拿一份手寫的
12 個名字去比對。手工清單只擋得住一個方向：「標了未接線、後來卻接上了」。反方向
——**有人新增一個沒接線的 key 而忘了標**——上一版誠實寫了「測不到」，然後就沒有
再管它。**誠實地記下一個洞不會把洞補起來。**

把 55 個 leaf key 全部機械列舉出來比對，當場掉出兩個從來沒進過那張清單的：

- **`quality.weights` 整塊**（authority 25 / richness 25 / freshness 20 /
  originality 15 / completeness 15）。五個數字、總和剛好 100、名字對得上五個維度
  ——**這是整個檔案裡最像旋鈕的東西**。五個上限全部硬寫在 `lib/quality.py` 的五支
  函式裡（`min(25, …)` / `min(15, …)` / `_freshness()` 的階梯），沒有任何一行碼讀
  `weights`；`quality.py` 的 docstring 還寫著「各自上限見 gate.yaml.quality.weights」，
  指向一組沒有人讀的數字。**這一條的待辦跟下面那些一樣：接上去或刪掉。**
- **`readiness.require_primary_evidence`**。這一個相反：它**不該**被接上。接線只要
  一行，而那一行會讓 `gate.yaml` 多一個能關掉紅線 2 唯一執法點的開關，然後 selftest
  全綠——因為每一條測試都是拿預設值跑的。假開關的傷害是有人改了它、發現沒效果、
  開始不信任這個檔案；真開關的傷害是有人改了它、**很有效果**。所以新增第三類
  **「C. 刻意不接」**，跟「A. 未接線（待接）」分開列：混在一起，下一個人會很熱心地
  幫我們接上。

現在的規矩：**列舉是機械的，標記是人寫的，測試比對兩者。** 每一個 leaf 都要被
`⚠ …未接線` 或 `消費者：<路徑>` 涵蓋（自己那一行或任何一層祖先），兩種都沒有就紅。
判準在 `scripts/lib/gate_keys.py`，它不保證什麼寫在
`references/gate-config-status.md` 最後一節。分支上量到的：selftest **322/322**、
變異 **32 條全殺、0 存活**——其中 M30 第一輪存活，逼出一條「只比對 path 所以恆真」
的空測試（`0b4efaa` 之後的那個 commit）。

**還沒做的仍然是接線本身**，下面每一條都還在：

- **`dedup:` 整塊未接線**（`minhash_jaccard: 0.80`、`ngram: 4`、
  `event_window_hours: 72`）。真正在跑的是 `lib/cluster.py` 裡硬寫的 token-Jaccard
  加上 96h / 7d / 21d 三段窗口。把 `event_window_hours` 從 72 改成 48 重跑，聚類
  結果不會有任何變化 —— 下一個人會去懷疑資料，而不是懷疑這個欄位。
- **`clustering.version_derivation` 未接線**。`claude@opus-4.8` 這種衍生實體不會產生。
- **`clustering.unknown_entity` 未接線**，而且它的
  `report_to: _dashboards/dictionary-gaps.md` 指向的檔案**不存在**。字典缺口目前
  沒有任何地方在收集，只能靠人翻語料發現。
- **`evidence.need_independent_tier2: 2`** 描述的「兩個獨立 Tier-2 也可以放行」
  這條替代路徑 **不存在**；實際只有 `missing_primary_evidence` 一條規則在擋。
- **`evidence.translation_chain` 未接線**，後果很具體：一篇英文原文加上一篇中文
  改寫，現在算成**兩個獨立來源**。七條媒體線之所以全部只收英文就是在閃這個坑
  （`sources.yaml` 第 92 行）。**中文媒體要進來之前，這個必須先接上**——這是這一區
  裡唯一有前置關係的一條。
- `quality.freshness_full_hours` / `freshness_zero_days` 未接線（實際是
  `lib/quality.py:_freshness()` 的硬寫階梯）。
- **`quality.weights` 整塊未接線**（見上）。要真的能調，得把 `lib/quality.py` 的
  五支函式改成讀這裡；在那之前它是一組會誤導人的正常數字。

---

## P5 — 三條來源「可跑但零產出」，兩種完全不同的病

首班 CI（`158d60f`，425 items / 32 sources）之後，判決已經出來了：

| 來源 | 進過 `_probe/state.json` | 病灶 |
|---|---|---|
| `src-mistral-news` | ✓ | **解析端**：抓到了，解不出東西 |
| `src-media-theregister` | ✗ | **抓取端**：從來沒抓過 |
| `src-kol-thezvi` | ✗ | **抓取端**：從來沒抓過 |

`src-mistral-news` 的設定是 `adapter: sitemap` 指到 `sitemap-index.xml`，配
`url_prefix: /news/`。兩個可能：sitemap-index → 子 sitemap 的展開沒做（或
`max_sitemaps: 3` 抓到的三張剛好都不含新聞），或 `url_prefix` 對不上實際路徑。

**今天查不出來的原因要講清楚**：這個容器的 proxy 擋外部連線（403），我沒辦法在
本地抓那張 sitemap 驗證。要查只能在 CI 裡查，作法是讓 sitemap adapter 在零產出時
把「展開到幾張子 sitemap、過濾前的前幾條 URL」印進 `_probe/<日>/report.md`。
**那個 debug 輸出本身就值得做**——現在的 report 只說「200 / 0 筆」，分不出
「站上真的沒新東西」跟「我們解析不出來」。跟舊 P1「量不到 ≠ 0」是同一個病灶，
只是換到了 report 上。

---

## P6 — 覆蓋盲點還有 20 家標著 pending

`_config/sources.yaml` 的 `coverage_watch.must_watch` 共 32 條，其中 20 條 `pending`：
DeepSeek、SSI、Thinking Machines、Perplexity、Cursor、Cognition、Scale AI、Z.ai、
Moonshot、MiniMax、ByteDance、Baidu、Tencent、TSMC、Broadcom、Groq、Cerebras、
CoreWeave、AWS、Cohere。

標了 `pending` 所以**不觸警**——這是誠實的做法（紅線 8），但「誠實地承認沒覆蓋」
跟「覆蓋到了」是兩回事。其中 DeepSeek、Scale AI、MiniMax、Broadcom、Cerebras
已經**在別人的語料裡被看見**，代表它們有新聞在流動，只是我們沒有第一手來源。

排這麼後面不是因為不重要，是因為它**沒有在騙人**：清單上寫著「沒有」，實際也沒有。
這是純粹的擴充工作，隨時可以做，做多少算多少。

---

## P7 — People layer 第三步沒開始

`person_id` 的獨立性計算（連通分量）已經接上、selftest 有釘。但
**每一列語料的 `author` 還沒有真的綁到 `person_id`** —— 現在 `person_id` 只從
`sources.yaml` 的來源層設定來。所以「同一個人在兩個平台發文」只有在那個人自己有
一條專屬來源時才抓得到；他投稿到媒體、或在 podcast 上講，綁不起來。

`pulse-probe.py` 第 74 行留了註解說明這件事。

---

## P8 — `_corpus/<day>/` 要不要累積（這題也在你手上）

現在是每天一個目錄、只放當天新看到的列。覆蓋範圍檢查因此只有幾天的實有語料，
monitor 自己會印「語料期間不足 30 天，沉默天數僅供參考」。要不要改成累積視窗，
我沒有動，因為那會改變所有「近 30 天」統計的意義。

這條跟 P1 裡的 `fix/coverage-uses-own-clock` 有關：那條併進去之後，coverage 的
守衛就不再依賴語料庫總長度，這題的急迫性會降一階。**建議先合那條，這題再決定。**

---

## P8.5 — `value` 是一個沒有任何消費者的分數欄位

P2 的遷移過程中量到的：`scoring.py` 每則 Event 都算一個 `value`，寫進 frontmatter，
**然後沒有任何東西讀它**。`pulse-render.py` 只依日期排序；全站沒有一處依 `value`
排序或篩選；`dist/index.html` 裡 "value" 出現 **0 次**。

所以 P2 遷移造成的 rank delta（51 則裡 36 則換位、最大位移 12 名）**不是使用者
看得到的排名變動**。這件事必須這樣講，不然聽起來像動了排名。

一個算得很認真、沒人用的欄位有兩個誠實的出路：接上（讓它真的決定排序或門檻），
或刪掉。第三條路——繼續算著、繼續寫進 frontmatter、繼續沒人用——是紅線 8 那種
「留著看起來像有功能的東西」。

沒有排更前面是因為它**不騙人**：`value` 沒有對外宣稱它決定什麼。它只是浪費。
但它跟 P2 是同一個家族——`heat` 是「算了一個沒量到的東西」，`value` 是「算了一個
沒人要的東西」，兩個都是「這段碼看起來在做事」。

---

## P9 — 12 則 `stale_backfill` 擋著的 Event 沒有出口

現況：`Events/` 共 51 則，`published` 36、`review` 14、`dropped` 1，
其中帶 `stale_backfill` 的有 **12** 則（上一版寫 11，數字會漲）。

這些是「設計上擋著」的舊聞回填，不是卡住。行為是對的，但**沒有任何路徑讓它們離開
這個狀態**——它們會永遠留在 review，而且數量只會單調增加。要嘛給一個 `archived`
終態，要嘛定期清掉。現在只是靠 monitor 把它們跟真正的待處理分開印，不讓數字互相
污染。

---

## P10 — 需要你動手的兩件（我在這個環境做不到）

### 一、合併四條分支（見 P1），然後刪掉已合併的分支

遠端現在 **28 條分支**，除 `main` 與 P1 那四條之外的 **24 條全部已完整併入**
（`git branch -r --no-merged origin/main` 只回那四條），可以安全刪除。

`git push origin --delete` 被這個 session 的安全分類器擋著，我送不出去。
GitHub 網頁的 branches 頁面有一鍵刪除已合併分支。

### 二、GitHub API 在這個環境被 proxy 擋（403）

所以我**開不了真正的 PR**，只能推分支 + 你在網頁上合。這不影響「發現問題自己開
分支」那條規則，但要知道「PR」在這裡實際上是「分支 + 我在對話裡寫的 review 說明」。

**這件事本身就是 P1 的成因**：一條「我做完、你來合」的交棒，如果你那頭沒動作，
沒有任何東西會變紅。跟舊 P2 那個「隔離候選是機器交棒給人的唯一介面，而它是斷的」
是同一個形態，只是這次的介面是你我之間。

---

## 附：2026-07-26 這一輪併掉的

| 分支 / PR | 修了什麼 |
|---|---|
| `fix/retry-exhaustion-mislabels-429` | 重試耗盡不再謊報成重導；robots 回 200 但內容不是 robots.txt 不算放行 |
| `fix/ci-swallows-failures` | CI 不再吞掉 probe 的 exit 3；Vault pages 兩支拆成獨立 step，`bash -e` 管得到 |
| `fix/nonatomic-config-write` | 狀態檔一律 tmp + `os.replace()`，失敗刪 tmp |
| `fix/alarms-that-mute-themselves` | 目錄名不是證據（嚴格日期 + 內容驗證）；未來日期判紅；缺 `ingested_at` 本身就算警報 |
| `fix/machine-writes-unbacked-robots-false`（PR #1） | 機器寫 `robots_ok: false` 也要交入場券；selftest 掛進 CI |

共同主題是**警報自己把自己關掉**：用一個比事實寬鬆的代理指標去代表事實。代理在
順利的日子跟事實重合，所以平常測不出來；它只在你最需要它準的那一天分岔。規格寫在
`references/health-alarms.md`。

`test/monitor-exit-codes` 又加了第四個實例：**用「碼裡有沒有這句話」代理「跑起來
會不會叫」**。那條還沒併（P1）。

第五個實例是 P3 那一層在講的：**用「測試有幾條」代理「壞掉會不會被抓到」**。
規格 `references/mutation-inventory.md`，同樣還沒併。

## 附：怎麼重新盤點這份清單

清單過期不會讓任何東西變紅，所以下次盤點請直接跑這些，不要相信上面的數字：

```bash
git log --oneline -1 main                  # 標頭的 commit
git branch -r --no-merged origin/main      # P1 還剩幾條
git ls-remote --heads origin | wc -l       # P10 的分支總數
python3 scripts/selftest.py | tail -1      # 標頭的測試數
python3 -c "import yaml;w=yaml.safe_load(open('_config/sources.yaml'))['coverage_watch']['must_watch'];print(len(w),sum(1 for x in w if x.get('pending')))"   # P6
grep -l stale_backfill Events/*.md | wc -l  # P9
python3 scripts/mutate.py                  # P3：現在有幾格守不住（幾分鐘）
```

最後那一行才是「測試守不守得住」的答案。`selftest | tail -1` 給的是**有幾條測試**，
那是兩件不同的事——這正是 P3 的整個重點。
