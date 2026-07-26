# AI-Pulse：應做而未做（已排序）

盤點時間 2026-07-26。`main` 在 `1ce43e9`，遠端零未合併分支，本地 selftest **222/222**、
monitor 三個 alert flag 全開 **rc=0**。

這份清單只寫「**已知有問題、但還沒動手**」的事。修掉的不列。

## 排序準則

每一條的位置由兩個問題決定，不由它屬於哪個模組決定：

1. **它壞掉的時候，有沒有東西會變紅？** 不會變紅的排前面。會紅的東西自己會來找人，
   不會紅的東西要靠人記得。
2. **它現在是不是正在輸出一個錯的數字？** 「沉默的缺工」比不上「有聲的假數字」——
   空欄位沒人會信，假數字沒人會查。

所以順序大致是：**有時限 → 正在騙人且不會紅 → 守門的東西自己沒被守 →
寫好了沒人叫 → 資料進不來 → 做了一半 → 要你動手**。

| # | 事 | 壞了會紅嗎 | 現在在騙人嗎 |
|---|---|---|---|
| P0 | 07-27 cron 收班 | 不會 | — |
| P1 | `已觀測 0 筆`＝量不到 | 不會 | **是** |
| P2 | 隔離候選是死路 | 不會 | **是**（永遠空） |
| P3 | dry run 會寫髒 state | 不會 | **是** |
| P4 | `--alert-coverage` 用外面的時鐘 | 不會 | 是（漏叫） |
| P5 | `unsupported_heat` 從沒觸發過 | 不會 | 是（門檻在值域外） |
| P6 | `pulse-monitor.main()` 沒有測試 | 不會 | — |
| P7 | 12 個未接線的 gate key | 不會（已標記） | 已止血 |
| P8 | `src-mistral-news` 零產出 | 不會 | — |
| P9 | 21 家 pending 覆蓋盲點 | 刻意不會 | 否（誠實掛著） |
| P10 | people layer 第三步 | 不會 | — |
| P11 | `_corpus/` 累不累積 | — | — |
| P12 | 11 則 `stale_backfill` 沒有出口 | 不會 | 否 |
| P13 | 22 條已合併分支刪不掉 | — | — |

---

## P0 — 07-27 必須發生的收班（唯一有時限的一條）

`data-refresh.yml` 現在的 cron 是 `0 */2 * * *`，一天 12 班；`robots --stale-days`
也一起從 7 調成 1。排程任務 `trig_01F52Q24UntdNVTd3DWbxFgs` 會在
**2026-07-27 12:00Z** 觸發，把兩個值改回 `0 16 * * *` 與 7。任務目前 enabled、
next_run 正確。

**如果 07-27 過了而 workflow 裡還是 `*/2`，代表那個任務沒跑到，要手動改。**
workflow 第 16-18 行已經把這句話寫在註解裡。一天 12 次去打人家的 robots.txt
是不禮貌的，而且我們自己沒有那個量的需求。

排 P0 只有一個理由：**它是這份清單上唯一一條「今天不做，明天就沒得做」的事。**
其他每一條都可以晚一週，這條晚一週就是連續一週失禮。

---

## P1 — `Sources/*.md` 把「量不到」印成「0 筆」（紅線 8 違規）

`pulse-source-notes.py:102-103` 寫 `items_observed` / `events_bound`，`:130` 把
零值渲染成「已觀測 0 筆」。**首班 CI（`158d60f`，425 items / 32 sources）跑完之後**
重測：

```
Sources/*.md 裡印「已觀測 0 筆」的 7 條：
  src-arxiv-cs-cl        進過 state ✓   （已停用）
  src-consilium-press    從沒抓過 ✗
  src-ec-digital-strategy 從沒抓過 ✗
  src-kol-importai       從沒抓過 ✗
  src-kol-thezvi         從沒抓過 ✗     ← 可跑
  src-media-theregister  從沒抓過 ✗     ← 可跑
  src-mistral-news       進過 state ✓   ← 真的產出 0
```

七條裡**五條從來沒有被抓過**。「0 筆」對它們來說是量不到，不是量到 0 —— 這正是
紅線 8 那句「量不到就寫量不到」要防的東西，而且它出現在給人看的頁面上。
（首班之前是 9 條印 0、其中 8 條沒抓過；媒體線跑起來之後名單換人，**比例沒變**——
這個 bug 跟哪些來源沒關係，跟「用空值代表兩種完全不同的事」有關係。）

同一支腳本還有第二個量錯：

```
items_observed 加總（jsonl 行數）= 869
相異 (source_id, url)            = 461
差                                = 408
```

`items_observed` 數的是**項目 × 天**，不是項目數。一條每天都出現在 feed 裡的
新聞，會讓那條來源的「已觀測」每天 +1。`references/vault-pages.md` 的四態表寫的是
「`_corpus/**/*.jsonl` 累計行數」——文件跟碼是一致的，**錯的是這個定義本身**：
它跟旁邊那格「有效產出」數的是不同的東西（那格數的是事件數，刻意去重），
兩格擺在一起比較時會得到錯的印象。

**該做的事**（照紅線 9，先改 `references/vault-pages.md` 再改碼）：
`items_observed` 改數相異 `(source_id, url)`；沒有 `first_fetch_at` 的來源印
「尚未抓取過」而不是 0；`events_bound` 排除 `status: dropped`。

---

## P2 — 唯一的人工升級路徑是一條死路（隔離候選永遠是空的）

`pulse-source-health.py:261` 把 `quarantine_candidates` 放進 `--json` 的 **stdout
字典**裡。寫到磁碟的 `snapshot` 是 `{"at", "runs_considered", "sources"}` ——
**沒有這個 key**。於是 `pulse-monitor.py:370` 的
`hjson.get("quarantine_candidates") or []` 永遠拿到 `[]`，`:498-500` 據此渲染的
health.md「隔離候選」那一行永遠是空的。

這條線的設計是：機器只能寫到 `degraded`（而 degraded 仍然每班被抓，連三班成功會
自己回來），`dormant` **只有人能寫**。也就是說「隔離候選」清單是**機器交棒給人的
唯一介面**。這個介面現在是斷的：達到隔離門檻的來源不會出現在任何人看得到的地方。

順帶三件同一支腳本的事，一起修比較省：

- `_probe/source-health.json` **現在根本不存在於 repo**。而 `source-lifecycle.md`
  推薦的回滾動作就是「刪掉這個檔案」——刪掉之後健康分從零開始，而且沒有任何東西
  會把它重新標記成「這是重置後的第一班」。**這是一個吸收態**：進去了看起來跟
  「一切正常、只是還沒累積」一模一樣。
- 機器會寫 `lifecycle: active`，跟「機器只能寫 degraded」這條不變式互相矛盾。
- **dry run 會改到持久狀態**：`atomic_write_text(hpath, ...)` 在
  `if not args.apply: return 0` **之前**執行，所以 `--json` 那種只想看看的跑法，
  會把 `degraded_by: "health"` / `degraded_from` 寫進 `source-health.json`，
  而 `sources.yaml` 沒有動 —— 兩個檔案從此互相矛盾，沒人知道是哪一次跑的。

（最後這條單獨排在 P3 是因為它的損害形態不同：P2 是「該叫的沒叫」，P3 是
「看一眼就改壞」。）

---

## P3 — `--json` 這種「只看不動」的跑法會留下改動

見 P2 最後一段。獨立列出來是因為它會咬到**未來的自己**：任何人為了 debug 跑一次
`pulse-source-health.py --json`，就在 `source-health.json` 裡留下一筆機器降級紀錄，
而 `sources.yaml` 是乾淨的。下一班讀到這個 state 時，會以為降級是真的發生過。

修法是一行：把 `atomic_write_text` 移到 `--apply` 的守衛之後。要留一個
`--write-state` 之類的旗標的話，那是另一個決定，先把預設行為修正。

---

## P4 — `--alert-coverage` 拿外面的時鐘量自己的鏈

守衛條件是 `history_days >= max_silent_days`：`history_days` 是**整個語料庫**的
歷史長度，`max_silent_days` 是**單一觀察對象**允許沉默的天數。語料庫才 3 天的
現在，所有 coverage 警報都被這個守衛壓住不叫；等語料庫長到 30 天，一條**昨天才
加進來**的觀察項也會立刻被拿 30 天的尺去量。

兩邊都錯，而且錯的方向相反：現在該叫的不叫，將來不該叫的會叫。

候選修法：改用每條來源自己的 `first_fetch_at`（`_probe/state.json` 有），
量「這條**自己**被觀察了多久」。這件事已經寫進
`references/health-alarms.md` 的「這一層不保證什麼」，所以下一個人不必再推導一次，
但**文件寫了不等於修了**。

---

## P5 — `unsupported_heat` 從上線到現在一次都沒有擋過東西

實測 48 個 Event：`uniqueAuthors`(權重 30)、`velocity`(20)、`platformBreadth`(7)、
`regionBreadth`(6) —— 四個因子**全部 0/48**，63% 的權重恆為零。實際會動的只有
`independentSources × 8` 加上 `freshness × 0.08`，而 47/48 的 `independentSources`
是 1。heat 的理論上限約 48，`gate.yaml` 的 `heat_threshold` 是 70。

門檻沒設錯，是**輸入不存在**：24 條來源全是 blog / newsroom 形態，量不出平台廣度；
EU 三條 dormant、CN 只剩 Qwen，量不出地域廣度。已記錄在 `399687a`，刻意只記錄
不改公式（紅線 9）。

**該做的事**：要嘛承認 heat 現在就是「獨立來源數 × 新鮮度」，改名、刪掉那 30 分
權重、把門檻降到實際值域裡；要嘛去補能量出平台廣度的來源形態。
**兩件都不做就這樣掛著，是目前的狀態，也是最糟的狀態。**

排在 P1-P4 之後而不是更前面，是因為它的失效方向是「該擋的沒擋」，而現在被它放行的
事件還要再過 readiness gate 的其他規則；P1-P4 是直接把錯的東西端到人面前。

---

## P6 — 死人開關自己的 exit code 沒有測試

今天實測：把 `pulse-monitor.py` 的 `main()` 結尾 `return rc` 改成 `return 0`，
重跑 selftest —— **222/222 passed**。這個變異完整存活。

selftest 從來沒有呼叫過 `_mm.main()`，只在 `:1270` 用
`_inspect.getsource(_mm.main)` 檢查原始碼字串。也就是說：整條鏈的最後一道防線是
「monitor 回非零 → CI 紅燈」，而**那個非零本身沒有任何測試在守**。
`--alert-*` 三個旗標的計算邏輯都有測試，把計算結果轉成 exit code 的那一步沒有。

一起處理的還有：

- **先前一輪手動變異盤點：94 個注入點裡 47 個存活**（約一半）。那是 174 條測試時
  的數字，今天併入四條分支後測試長到 222 條，**這個數字要重跑才算數**。
- `FM_FROM_CONFIG` 的白名單繞過還是活的（紅線 6 那條邊界沒有測試在守）。
- `ingested_at` 黏性的那條釘子是**空轉的**——它斷言的條件在 fixture 裡恆真。

---

## P7 — `gate.yaml` 還有 12 個 key 沒有任何程式碼讀它

`docs/gate-unconsumed`（已併）把它們全部標成 `⚠ 未接線`，並用 selftest 釘住標記，
所以**現在不會再騙人了**——這也是它排在這裡而不是 P1 區的理由。標記不等於修好：

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
  改寫，現在算成**兩個獨立來源**。`feat/media-line` 那七條媒體線之所以全部只收
  英文就是在閃這個坑（`sources.yaml` 第 92 行）。**中文媒體要進來之前，這個必須
  先接上**——這是這一區裡唯一有前置關係的一條。
- `quality.freshness_full_hours` / `freshness_zero_days` 未接線（實際是
  `lib/quality.py:_freshness()` 的硬寫階梯）。

---

## P8 — `src-mistral-news` 連兩天 200 / robots True / 0 筆

設定是 `adapter: sitemap` 指到 `sitemap-index.xml`，配 `url_prefix: /news/`。
兩個可能：sitemap-index → 子 sitemap 的展開沒做（或 `max_sitemaps: 3` 抓到的三張
剛好都不含新聞），或 `url_prefix` 對不上實際路徑。

**今天查不出來的原因要講清楚**：這個容器的 proxy 擋外部連線（403），我沒辦法在
本地抓那張 sitemap 驗證。要查只能在 CI 裡查，作法是讓 sitemap adapter 在零產出時
把「展開到幾張子 sitemap、過濾前的前幾條 URL」印進 `_probe/<日>/report.md`。
**那個 debug 輸出本身就值得做**——現在的 report 只說「200 / 0 筆」，分不出
「站上真的沒新東西」跟「我們解析不出來」。（跟 P1「量不到 ≠ 0」是同一個病灶。）

**首班 CI 已經跑過了（`158d60f`：425 items / 32 sources），媒體線的判決出來了**：
七條 `src-media-*` 裡有六條開始產出，只剩 `src-media-theregister` 從沒進過
`_probe/state.json`——那條要單獨查，不能再算在「剛併進來所以還沒跑」裡面。
`src-kol-thezvi` 同樣從沒抓過。這兩條加上 `src-mistral-news` 是目前僅有的三個
「可跑但沒東西」，其中前兩條是**抓取端**的問題、後一條是**解析端**的問題，
查法不同。

---

## P9 — 覆蓋盲點還有 21 家標著 pending

DeepSeek、SSI、Thinking Machines、Perplexity、Cursor、Cognition、Scale AI、Z.ai、
Moonshot、MiniMax、ByteDance、Baidu、Tencent、TSMC、Broadcom、Groq、Cerebras、
CoreWeave、AWS、Cohere。

標了 `pending` 所以**不觸警**——這是誠實的做法（紅線 8），但「誠實地承認沒覆蓋」
跟「覆蓋到了」是兩回事。其中 DeepSeek(22)、Scale AI(22)、MiniMax(6)、Broadcom(2)、
Cerebras(2) 已經**在別人的語料裡被看見**，代表它們有新聞在流動，只是我們沒有第一手
來源。

排這麼後面不是因為不重要，是因為它**沒有在騙人**：清單上寫著「沒有」，實際也沒有。
這是純粹的擴充工作，隨時可以做，做多少算多少。

---

## P10 — People layer 第三步沒開始

`person_id` 的獨立性計算（連通分量）已經接上、selftest 有釘。但
**每一列語料的 `author` 還沒有真的綁到 `person_id`** —— 現在 `person_id` 只從
`sources.yaml` 的來源層設定來。所以「同一個人在兩個平台發文」只有在那個人自己有
一條專屬來源時才抓得到；他投稿到媒體、或在 podcast 上講，綁不起來。

`pulse-probe.py` 第 74 行留了註解說明這件事。

---

## P11 — `_corpus/<day>/` 要不要累積（這題在你手上）

現在是每天一個目錄、只放當天新看到的列。覆蓋範圍檢查因此只有 3 天的實有語料，
monitor 自己會印「語料期間不足 30 天，沉默天數僅供參考」。要不要改成累積視窗，
我沒有動，因為那會改變所有「近 30 天」統計的意義。

這條跟 P4 有關：P4 修好之後，coverage 的守衛就不再依賴語料庫總長度，這題的急迫性
會降一階。**建議 P4 先做，這題再決定。**

---

## P12 — 11 則 `stale_backfill` 擋著的 Event 沒有出口

monitor 顯示 review=14 裡有 11 則是「設計上擋著」的舊聞回填，不是卡住。行為是對的，
但**沒有任何路徑讓它們離開這個狀態**——它們會永遠留在 review。要嘛給一個
`archived` 終態，要嘛定期清掉。現在只是靠 monitor 把它們跟真正的待處理分開印，
不讓數字互相污染。

---

## P13 — 需要你動手的兩件（我在這個環境做不到）

### 22 條已合併的遠端分支刪不掉

`main` 現在是 `1ce43e9`，遠端上除 `main` 外的 **22 條分支全部已完整併入**
（`git branch -r --no-merged origin/main` 回 0），可以安全刪除：

```
docs/backlog                            docs/config-sources-machine-written
docs/gate-unconsumed                    docs/heat-dead-terms
docs/pr-first-workflow                  feat/health-dashboard
feat/media-line                         feat/official-sources-coverage
feat/people-layer                       feat/source-health
fix/alarms-that-mute-themselves         fix/author-classifier
fix/backfill-flag-erased-by-second-run  fix/ci-swallows-failures
fix/doc-narratives-direct-push          fix/keywords-nondeterministic
fix/nonatomic-config-write              fix/probe-mislabels-403-as-disallow
fix/retry-exhaustion-mislabels-429      fix/traditional-placeholder
fix/unenriched-age-uses-news-date       test/backfill-sticky-flags
```

`git push origin --delete` 被這個 session 的安全分類器擋著，我送不出去。
GitHub 網頁的 branches 頁面有一鍵刪除已合併分支。

### GitHub API 在這個環境被 proxy 擋（403）

所以我**開不了真正的 PR**，只能推分支 + 你在網頁上合，或像今天這樣在本地合了再推
`main`。這不影響「發現問題自己開分支」那條規則，但要知道「PR」在這裡實際上是
「分支 + 我在對話裡寫的 review 說明」。

---

## 附：下一班 CI 是真正的驗收

今天併進 `main` 的東西裡，有幾樣**還沒有在 GitHub Actions 上跑過一次**：

- `feat/media-line` 的七條媒體來源（本地 selftest 綠，但沒真的抓過）
- `feat/source-health` 的 lifecycle 自動升降級（會**寫回 `sources.yaml`**）
- `feat/health-dashboard` 的 `Vault pages` 步驟（會產生 32+ 張 `Sources/*.md`）
- `fix/unenriched-age-uses-news-date` 的 `ingested_at`（新 Event 才會帶）
- `fix/ci-swallows-failures`：probe 的 exit 3 現在會讓整條 job 紅。**第一次紅燈時
  先看是不是 0 可跑來源，不要直接當成 flaky。**
- `fix/alarms-that-mute-themselves`：空的 `_corpus/<日>/` 目錄不再算「這天有語料」。
  如果第一班就紅，代表過去有一天是空目錄撐著綠燈的——那是這條分支要抓的東西。

本地驗證狀態：selftest **222/222**、monitor 三個 alert flag 全開 **rc=0**、
robots rc=0、workflow YAML 可解析。

**首班結果（`158d60f` + `0dab90b`，2026-07-26）**：

- probe **425 items / 32 sources**，媒體線七條裡六條開始產出（見 P8）。
- `Sources/*.md` 產生 **32 張**，`_dashboards/health.md` 綠燈、`generated_day`
  是當天、`last_success` 是當天、`probe_lag_days: 0`。
- `_probe/source-health.json` **首次落地**（32 條），而它的 key 是
  `["at", "runs_considered", "sources"]` —— **線上資料確認了 P2**：
  `quarantine_candidates` 真的不在磁碟上。
- `sources.yaml` 唯一的機器改動是 robots recheck 補上 `robots_ok: true` 與
  `robots_checked_at`（量到才寫，不是預設 true）。**lifecycle 沒有任何自動降級，
  沒有誤殺來源。**

## 附：2026-07-26 併掉的（已從上面的清單移除）

| 分支 | 修了什麼 |
|---|---|
| `fix/retry-exhaustion-mislabels-429` | 重試耗盡不再謊報成重導；robots 回 200 但內容不是 robots.txt 不算放行 |
| `fix/ci-swallows-failures` | CI 不再吞掉 probe 的 exit 3；Vault pages 兩支拆成獨立 step，`bash -e` 管得到 |
| `fix/nonatomic-config-write` | 狀態檔一律 tmp + `os.replace()`，失敗刪 tmp，不讓半份檔案被 `git add -A` 提交上去 |
| `fix/alarms-that-mute-themselves` | 目錄名不是證據（嚴格日期 + 內容驗證）；未來日期判紅；缺 `ingested_at` 本身就算警報 |

四條的共同主題是**警報自己把自己關掉**：用一個比事實寬鬆的代理指標去代表事實
（目錄名代表「那天有語料」、`max()` 代表「最舊的未潤稿」）。代理在順利的日子跟事實
重合，所以平常測不出來；它只在你最需要它準的那一天分岔。
新增的規格寫在 `references/health-alarms.md`。
