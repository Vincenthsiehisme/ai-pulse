# AI-Pulse：應做而未做（已排序）

盤點時間 2026-07-26（第二輪）。`main` 在 `8a6c1e8`，遠端 **28 條分支、其中 4 條未併**，
`main` 上的 selftest **224/224**。四條未併分支各自的 selftest：
`fix/observed-counts-item-days` 235、`fix/health-snapshot-dry-run` 243、
`fix/coverage-uses-own-clock` 233、`test/monitor-exit-codes` 241。

> 同日稍晚追記：這份清單所在的 `docs/backlog-refresh` 又長出了變異盤點層
> （P3），selftest 到 **238**，未併分支變成 **5 條**。這幾個數字也一樣，
> 在合併之前都只描述分支、不描述 `main`。

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
| P1 | 五條修好的分支還躺在遠端 | 不會 | **是**（修了不等於生效） |
| P2 | `unsupported_heat` 從沒觸發過 | 不會 | 是（門檻在值域外） |
| P3 | 變異盤點已做成工具，但也還沒併 | 會（在分支上） | 否（改成可重跑的判準了） |
| P4 | 12 個未接線的 gate key | 不會（已標記） | 已止血 |
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

## P1 — 五條修好的分支還躺在遠端，`main` 上一條都沒生效

```
$ git branch -r --no-merged origin/main
  fix/coverage-uses-own-clock
  fix/health-snapshot-dry-run
  fix/observed-counts-item-days
  test/monitor-exit-codes
```

| 分支 | 原編號 | 修了什麼 | selftest |
|---|---|---|---|
| `fix/observed-counts-item-days` | 舊 P1 | `Sources/*.md` 不再把「量不到」印成「0 筆」；`items_observed` 改數相異 `(source_id, url)`；`events_bound` 排除 `dropped` | 235 |
| `fix/health-snapshot-dry-run` | 舊 P2+P3 | 隔離候選真的寫進磁碟快照（機器交棒給人的唯一介面接回來了）；`--json` 這種只看的跑法不再改持久狀態 | 243 |
| `fix/coverage-uses-own-clock` | 舊 P4 | 沉默判準改用每條實體自己的 `first_fetch_at`，不再拿整個語料庫的長度當尺 | 233 |
| `test/monitor-exit-codes` | 舊 P6 (a/c/d) | 死人開關的 exit code 走真子行程釘住；`FM_FROM_CONFIG` 白名單邊界改由行為守；`ingested_at` 黏性改成真的跑第二輪 | 241 |
| `docs/backlog-refresh` | 本檔 + P3 | 這份清單本身；變異盤點層（`scripts/mutate.py` + `mutations.yaml` + 獨立工作流），並補掉它第一輪抓到的五個洞 | 238 |

**這一條的重點不是「還有五件事沒做」，是「五件事做完了，而系統的行為一點都沒變」。**
`main` 上跑的還是舊碼：Sources 頁還在印「已觀測 0 筆」、`--json` 還會寫髒 state、
coverage 還在拿外面的時鐘量自己的鏈、`return rc` 改成 `return 0` 在 `main` 上仍然
**224/224 全過**。

而且這個狀態自己不會變紅：CI 只跑 `main`，四條分支綠得再漂亮也沒有任何一格會亮。
上一版清單把 P1–P4 從表上劃掉的那一刻，如果沒有這一條，就等於宣稱它們生效了——
那是紅線 8 的違規，只是主詞換成這份文件。

**要人動手的原因**：這個環境的 proxy 擋掉 GitHub API（403），我開不了 PR；
分支都已經推上去了，合併要在網頁上按。見 P10。

---

## P2 — `unsupported_heat` 從上線到現在一次都沒有擋過東西（**這題在你手上**）

實測 48 個 Event：`uniqueAuthors`(權重 30)、`velocity`(20)、`platformBreadth`(7)、
`regionBreadth`(6) —— 四個因子**全部 0/48**，63% 的權重恆為零。實際會動的只有
`independentSources × 8` 加上 `freshness × 0.08`，而 47/48 的 `independentSources`
是 1。heat 的理論上限約 48，`gate.yaml` 的 `heat_threshold` 是 70。

門檻沒設錯，是**輸入不存在**：來源全是 blog / newsroom 形態，量不出平台廣度；
EU 三條 dormant、CN 只剩 Qwen，量不出地域廣度。已記錄在 `399687a`，刻意只記錄
不改公式（紅線 9）。

**該做的事**：要嘛承認 heat 現在就是「獨立來源數 × 新鮮度」，改名、刪掉那 30 分
權重、把門檻降到實際值域裡；要嘛去補能量出平台廣度的來源形態。
**兩件都不做就這樣掛著，是目前的狀態，也是最糟的狀態。**

排在這裡而不是更前面，是因為它的失效方向是「該擋的沒擋」，而現在被它放行的事件
還要再過 readiness gate 的其他規則。**這條要你先決定方向我才動**，因為改公式或改
門檻都要先改 `references/readiness-gate.md`（紅線 9），還要附遷移與回滾——
方向錯了整套白做。

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
`references/mutation-inventory.md`、清單 `scripts/mutations.yaml`（20 條）、
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

## P4 — `gate.yaml` 還有 12 個 key 沒有任何程式碼讀它

`docs/gate-unconsumed`（已併）把它們全部標成 `⚠ 未接線`，並用 selftest 釘住標記，
所以**現在不會再騙人了**——這也是它排在這裡而不是更前面的理由。標記不等於修好：

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
