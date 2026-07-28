# AI-Pulse：應做而未做

這份清單只寫「**已知有問題、但還沒動手**」的事。修掉的移到最後的〈附：已經修掉的〉；
**修好了但還沒併進 `main` 的，算沒修**——這條規矩不變，只是現在不必靠人記得：
現況數字由每班的鏈自己量（見下一節），而那條鏈跑在 `main` 上。

每一條有一個**不會變的名字**（`cron-收班`、`gate-未接線`…），沒有編號。
理由寫在下面〈為什麼這裡沒有編號〉——不是排版偏好，是量到的一個 bug。

## 現況

**現況數字不在這份檔案裡，在 [`_dashboards/backlog-status.md`](_dashboards/backlog-status.md)，
每班重新生成。**

這裡以前有一張手寫的表：`main` 的 commit、selftest 條數、變異數、可刪分支數、
Events 數、語料天數。它在 2026-07-27 那一版**寫下之後 3 小時就過期了**——
四條分支被合併，六格同時作廢。

那是同一種病的第 9 個實例（見〈已經修掉的〉底下的清單）：**用一張量過的表代理現況**。
更值得記的是**上一版的修法失敗了**：當時的做法是把量測時間寫進標題、在最後一節
請下一個人複量。那是一個**靠人記得**的機制，而這份清單存在的理由就是不要有
那種機制。三小時就證明它不夠。

所以照這個 repo 一貫的分法辦——**量測是機械的，判斷是人寫的**（跟
`gate.yaml` 的標記涵蓋檢查同一句話）：

- **數字**歸 `scripts/pulse-backlog-status.py`，每班跟著夜間鏈重生成，
  規格在 `references/vault-pages.md`。
- **判斷**留在這裡：哪一條重要、壞了會不會變紅、現在有沒有在騙人。
  **這份檔案不再有任何一個會過期的數字。**

兩格刻意不搬過去也不留在這裡：**selftest 條數**與**變異結果**。它們不是每班
量得到的事實，放進那一頁只會變成一個「上次不知道什麼時候量的」數字。要它們就
自己跑，指令在〈附：怎麼重新盤點這份清單〉。

## 為什麼這裡沒有編號

再上一版有 P0–P10。2026-07-26 梳理的時候（`docs/backlog-tidy`，PR #10），
在 repo 裡量到兩處指著編號的字：

```
scripts/selftest.py:794          # …不是拿整個語料庫的長度（BACKLOG P4）
references/readiness-gate.md:112 負責人：BACKLOG P2 收在這裡
```

寫下去的當天兩句都是對的。到那天 `P4` 指的是 gate 未接線、`P2` 是一條已經併掉的事，
**兩句話都在指別的東西了**，而且沒有任何一條測試會因此變紅——編號是位置，位置會
隨著清單重排而改變，但引用它的人不會跟著改。

這就是這個 repo 一直在抓的同一隻病：**用一個比事實寬鬆的代理指標去代表事實**。
「P4」代理的是「gate 未接線那件事」，兩者在清單沒動過的日子裡重合，正好在清單有
進展的那天分岔——而有進展，正是最多人會去讀它的時候。

所以改成**名字**：名字跟著事情走，事情結案了名字就進〈已經修掉的〉，
指著它的人至少搜得到自己引錯了。優先順序改由**表格裡的位置**表達，不由名字表達。
（上面那兩處已經在 PR #10 一起改掉了。`references/mutation-inventory.md` 裡
的「BACKLOG P1」不動——那些在「第一輪 / 第二輪」的段落裡，是歷史記錄，不是指標。）

## 排序準則

每一條的位置由兩個問題決定，不由它屬於哪個模組決定：

1. **它壞掉的時候，有沒有東西會變紅？** 不會變紅的排前面。會紅的東西自己會來找人，
   不會紅的東西要靠人記得。
2. **它現在是不是正在輸出一個錯的數字？** 「沉默的缺工」比不上「有聲的假數字」——
   空欄位沒人會信，假數字沒人會查。

所以順序大致是：**有時限 → 修了但沒生效 → 正在騙人且不會紅 → 守門的東西自己沒被守 →
資料進不來 → 做了一半 → 要你動手**。

**2026-07-27 重測：上一版說「正在騙人且不會紅」這一格是空的，那句話當時就不對。**

上一版寫著「`main` 上也沒有已知的假話在對外輸出」，並且註記「這兩格是最會悄悄長
回來的——下一次盤點先問這兩格」。這一次照做，逐頁量：

```
已發布 Event                                              41
  內文與自己的 frontmatter 互相矛盾                          1
  四個從未量測的傳播因子印成粗體 0                        41 / 41
```

兩件事**當時就已經被查出來、寫進了 `docs/design/2026-07-27-published-is-a-proxy.md`
第 4 節的（甲）與（乙）**，但那份文件的 frontmatter 是 `status: proposal`，
而這份清單的總表沒有它們。於是「已知的假話」躺在一份提案裡，
**而唯一按「現在在騙人嗎」排序的地方看不到它。**

這正是本清單開頭那句話的又一個實例：**用一個比事實寬鬆的代理指標去代表事實。**
這次的代理是「總表是空的」代表「沒有假話」。

所以規矩補一條：**一件事被寫進設計提案，不等於它離開了這份清單。**
提案講的是怎麼修；這裡記的是「它現在還在騙人」。兩者要各記一次。

| 名字 | 事 | 壞了會紅嗎 | 現在在騙人嗎 |
|---|---|---|---|
| [`榜單中文落地靠人工繞道`](#榜單中文落地靠人工繞道) | 譯文落地了一次，但機制還是壞的：`apply` 讀的榜單不在版控裡，fresh clone 一定退件；2026-07-28 在乾淨 clone 上重驗成立，退件理由與離開碼都在說假話 | 不會（離開碼 0） | **是（我在上一版把它當成修好了）** |
| [`published-代理未修`](#published-代理未修) | `published` 在 4/5 個 adapter 裡不是 published，驅動 17 個決定；整份修法還是提案 | 不會 | 是（標題與日期） |
| [`gate-未接線`](#gate-未接線) | 一批 `gate.yaml` 的 key 沒有任何碼讀它 | 不會（已標記，漏標會紅） | 部分 |
| [`零產出來源`](#零產出來源) | 三條「可跑但零產出」，三種不同的病 | 不會 | — |
| [`跨語言重複-event`](#跨語言重複-event) | 沒有版本號的同一件事，中英文會變成兩則 Event | 不會 | — |
| [`候選詞被普通英文洗版`](#候選詞被普通英文洗版) | 字典補漏清單大半是 June / Here / One 這種詞 | 不會 | 否（沒宣稱過它們是實體） |
| [`pending-覆蓋`](#pending-覆蓋) | 20 家覆蓋盲點標著 pending | 刻意不會 | 否（誠實掛著） |
| [`people-第三步`](#people-第三步) | 語料的 `author` 還沒綁到 `person_id` | 不會 | — |
| [`字典掃描範圍分岔`](#字典掃描範圍分岔) | 同一本字典，兩個消費者掃的欄位不一樣，沒有一行字說明為什麼 | 不會 | 否（沒宣稱過覆蓋率） |
| [`實體命中用過即丟`](#實體命中用過即丟) | 兩處都算出實體命中、兩處都沒留下，而且補不回來 | 不會 | 否 |
| [`corpus-累積`](#corpus-累積) | `_corpus/` 要不要改成累積視窗 | — | — |
| [`value-沒人用`](#value-沒人用) | 每則都算 `value`，全站沒有一處讀它 | 不會 | 否（沒宣稱過什麼） |
| [`stale-backfill-無出口`](#stale-backfill-無出口) | 12 則被擋著的 Event 沒有終態 | 不會 | 否 |
| [`兩條夜間鏈只靠時鐘耦合`](#兩條夜間鏈只靠時鐘耦合而餘裕沒有人在量) | 抓取班遲到就會吃掉潤稿班的餘裕，而餘裕沒有人在量 | 不會 | 否 |
| [`來源已死但每班照樣有貨`](#來源已死但每班照樣有貨) | 三條來源最新一筆落後 2 個月到 3 年，而沉默判準是「這班抓到幾筆」 | **不會** | **是（儀表顯示正常）** |
| [`Meta-沒有來源`](#meta-沒有來源) | Meta 唯一的來源停更於 2023-05，這家公司在系統裡等於不存在 | 不會 | 是 |
| [`分支刪不掉`](#分支刪不掉) | 只剩「我做完你來合」這個交棒介面不會叫（刪分支與推分支都已證實可行） | — | — |

---

## `榜單中文落地靠人工繞道`

**這一條是我上一版判錯的。判錯的方式，正好是這份清單開頭那句話。**

2026-07-27 我看到 `_github/desc-zh.json` 首次進版控、25 / 25 條全數翻完，
就把〈榜單描述沒有中文〉移進〈已經修掉的〉。**用「產物出現了」代表「機制會動了」
——那是一個比事實寬鬆的代理指標。**

同一晚潤稿端自己查出了真相，寫在它開的那條分支上：

```
pulse-github-desc-apply.py 讀的榜單是 dist/data/github.json
.gitignore 有 dist/          →  那份檔案不在版控裡
潤稿端是 fresh clone         →  榜單根本不存在
src_by_name 因此全空         →  25 條譯文全被判「不在目前榜單上」退件
```

那一晚之所以落地，是**潤稿端當場手工補建了榜單**才讓譯文寫進去的。
`main` 上的碼一個字沒改——**下一班 19:00Z 會撞到一模一樣的牆。**

這也是 route 2 只做了一半的後果：prep 那半改成讀已進版控的待譯清單，
apply 這半還在讀 `dist/`。**同一條路徑上的兩端，只搬了一端。**

### 2026-07-28 重驗：診斷成立，而且比上面寫的多壞兩層

`fix/c2-apply-reads-committed-worklist` 那條分支**已經不在遠端了**，一次都沒有
合進 `main`。所以我照原樣重驗了一次——不是讀碼推論，是 clone 一份
`origin/main`（`397cd57`、`--depth 1`，就是潤稿端會拿到的那一份），照 runbook
第 11 步寫三條完全合格的譯文跑 apply：

```
[退件] earendil-works/pi        不在目前榜單上（榜換過了，下次 prep 會再排進來）
[退件] Graphify-Labs/graphify   同上
[退件] firecrawl/firecrawl      同上
過關 0／退件 3          ---- 離開碼: 0 ----
```

上面的診斷成立。另外兩層是這次才看到的：

- **退件理由是假的。** 榜一次都沒換，是根本沒讀到。「榜上沒有這條」被拿來代理
  「我讀不到榜」，於是訊息把人指向 GitHub 榜單——那裡完全沒有問題。
- **離開碼 0。** 全數退件跟「今晚沒有東西要翻」在離開碼上沒有差別，而潤稿端的
  收尾摘要正是照離開碼寫的。三句裡兩句錯，還都是綠的。

還有一條測試把它釘住了：`selftest.py` 打的是 `validate("ghost/repo", _ZH, None)`，
而 `validate()` 只拿得到一個 bool，本來就分不出那兩件事——壞的那一行在 `main()`
的 `else {"repos": []}`，測試碰不到。**斷言只碰到被改壞那段程式的外圍**，
是空測試的第三種形狀。

修法（本 PR）：`english_source()` 分出榜／worklist／都沒有三態，兩種退件講不同
的話，全數退件回離開碼 3，榜讀不到就不生一份假的 dist 榜單（那會誤導同 session
後面的 prep）。測試改打 `main()`，六顆變異守著（M153–M158）。

## `published-代理未修`

`docs/design/2026-07-27-published-is-a-proxy.md` 把它盤完了：`published` 這個
欄位在五個 adapter 裡有四個放的不是 published，往下驅動 **17 個決定**
（含不可逆的 Event id），而這 17 個之中沒有一個會變紅。

**整份修法還是提案，一行都還沒實作。** 三個階段：

| 階段 | 做什麼 | 擋在哪 |
|---|---|---|
| A | 進料層說實話：`published_kind` / `title_kind` / `published_precision` 三個封閉集 | 沒擋，可以動工 |
| B | 逐個消費者決定「沒有真值時怎麼辦」 | 要拍板，尤其 Event id（不可逆，已寫進 50+ 份檔案） |
| C | 三條 sitemap 來源改抓 `og:title` | **等 C-4 在 CI 跑一次** |

**現在正在對外輸出的損害**（C-1 實測五組對照，兩組是完全不同的字串）：
`src-anthropic-news` 與 `src-xai-news` 的 Event 標題有一類**根本不是那篇文章的
標題**——不是不精確，是不同的東西。而標題會進 id 的 hash、進聚類相似度、
進對外站的每一張卡片。

階段 A 不必等任何人，是這條裡最該先動的一段。

## `gate-未接線`

`gate.yaml` 有一批 key 沒有任何程式碼讀它。它們**已經被標成 `⚠ 未接線`**，所以
現在不會再騙人——這也是它排在這裡而不是更前面的理由。**標記不等於修好。**

### 上一輪只做了止血補強（`fix/gate-keys-unmarked`，PR #9，已在 `main`）

上一版的標題寫「12 個」，那個 12 是**手工數的**；`selftest.py` 也是拿一份手寫的
12 個名字去比對。手工清單只擋得住一個方向：「標了未接線、後來卻接上了」。反方向
——**有人新增一個沒接線的 key 而忘了標**——上一版誠實寫了「測不到」，然後就沒有
再管它。**誠實地記下一個洞不會把洞補起來。**

把 55 個 leaf key 全部機械列舉出來比對，當場掉出兩個從來沒進過那張清單的：

- **`quality.weights` 整塊**（authority 25 / richness 25 / freshness 20 /
  originality 15 / completeness 15）。五個數字、總和剛好 100、名字對得上五個維度
  ——**這是整個檔案裡最像旋鈕的東西**。五個上限全部硬寫在 `lib/quality.py` 的五支
  函式裡，沒有任何一行碼讀 `weights`；`quality.py` 的 docstring 還寫著「各自上限見
  gate.yaml.quality.weights」，指向一組沒有人讀的數字。
- **`readiness.require_primary_evidence`**。這一個相反：它**不該**被接上。接線只要
  一行，而那一行會讓 `gate.yaml` 多一個能關掉紅線 2 唯一執法點的開關，然後 selftest
  全綠——因為每一條測試都是拿預設值跑的。假開關的傷害是有人改了它、發現沒效果、
  開始不信任這個檔案；真開關的傷害是有人改了它、**很有效果**。所以分成三類：
  **A. 未接線（待接）／B. 接線了但條件走不到／C. 刻意不接**。混在一起，下一個人會
  很熱心地幫我們接上。

現在的規矩：**列舉是機械的，標記是人寫的，測試比對兩者。** 每一個 leaf 都要被
`⚠ …未接線` 或 `消費者：<路徑>` 涵蓋（自己那一行或任何一層祖先），兩種都沒有就紅。
判準在 `scripts/lib/gate_keys.py`，它**不保證**什麼寫在
`references/gate-config-status.md` 最後一節。

### 還沒做的是接線本身

- **`dedup:` 整塊未接線**（`minhash_jaccard: 0.80`、`ngram: 4`、
  `event_window_hours: 72`）。真正在跑的是 `lib/cluster.py` 裡硬寫的 token-Jaccard
  加上 96h / 7d / 21d 三段窗口。把 `event_window_hours` 從 72 改成 48 重跑，聚類
  結果不會有任何變化——下一個人會去懷疑資料，而不是懷疑這個欄位。
- **`clustering.version_derivation`**：`claude@opus-4.8` 這種衍生實體不會產生。
- ~~**`clustering.unknown_entity`**~~ **2026-07-27 接上**
  （`fix/dictionary-gaps-report-to-nowhere`）：`report_to` 指的那一頁現在真的會
  被產生，兩個晉升門檻也搬進 `gate.yaml` 給兩個消費者共用。
  剩下 `action` 與 `key_from_title_hash` 標成 **C 類（刻意不接）**，理由寫在
  設定檔那兩行旁邊。
- **`evidence.need_independent_tier2: 2`** 描述的「兩個獨立 Tier-2 也可以放行」這條
  替代路徑**不存在**；實際只有 `missing_primary_evidence` 一條規則在擋。
- ~~**`evidence.translation_chain`**~~ **2026-07-27 接上**
  （`fix/translation-chain-counts-a-rewrite`），詳見〈已經修掉的〉。四個 leaf
  全部有消費者，各自有一條變異證明它真的被讀。**中文媒體的那道前置門開了。**
- `quality.freshness_full_hours` / `freshness_zero_days`（實際是
  `lib/quality.py:_freshness()` 的硬寫階梯）。
- **`quality.weights` 整塊**（見上）。要真的能調，得把 `lib/quality.py` 的五支函式
  改成讀這裡；在那之前它是一組會誤導人的正常數字。

---

## `零產出來源`

上一版把兩條寫成同一個病：「抓取端：從來沒抓過」。這一版改讀
`_probe/source-runs.jsonl`（每班每條來源的 status），**那兩條的「沒抓過」是兩件
不同的事**：

| 來源 | 每班的 status | 病灶 | 待修嗎 |
|---|---|---|---|
| `src-mistral-news` | `200`，items 全 0 | **解析端**：抓到了，解不出東西 | 是 |
| `src-media-theregister` | `robots_disallow` | **站方 robots 明說不行**（`sources.yaml` 的 `robots_ok: false` 是實測寫回的） | **不是。這是合規在正常運作** |
| `src-kol-thezvi` | `robots_unknown` | robots.txt 回 401/403 **取不到**，保守跳過——不是站方拒絕（`robots_ok` 仍是 `true`） | 是，但只能在 CI 裡查 |

**這份紀錄的範圍要講清楚**：`source-runs.jsonl` 目前只有 7 班、全部在 07-26
10:05Z–23:03Z 之間。所以上表說的是「這 7 班每一班都這樣」，不是「從上線以來」。
狀態穩定到這個程度已經夠判斷病灶，但別把它當成長期紀錄。

分開列的理由：**三條在儀表上都顯示成「零產出」，但只有第一條是我們的 bug。**
併成一句「三條零產出來源」，下一個人會平均地去修三條，其中一條無論怎麼修都不會有
產出——`theregister` 要有產出只有兩條路：站方改 robots，或我們決定不遵守。後者不會
發生，所以它該做的動作是**移出待修、標成「已知不會有產出」**，不是留著當缺工。
這跟「量不到 ≠ 0」是同一句話換個位置：**「被 robots 擋住」跟「壞了」不是同一件事，
擠在同一格裡就分不出來。**

`src-kol-thezvi` 的 401/403 是**打 robots.txt 就被擋**，跟 2026-07-24 漏抓
Claude Opus 5 那次同形態（容器／CI 的 IP 被 WAF 擋，不是站方拒絕）。現在的處理是
保守跳過、不記分、不降級——是對的；要注意的是別讓它日久被讀成「站方拒絕」。

`src-mistral-news` 的設定是 `adapter: sitemap` 指到 `sitemap-index.xml`，配
`url_prefix: /news/`。兩個可能：sitemap-index → 子 sitemap 的展開沒做（或
`max_sitemaps: 3` 抓到的三張剛好都不含新聞），或 `url_prefix` 對不上實際路徑。

**在這個容器裡查不出來的原因要講清楚，而上一版沒講對**：不是「proxy 擋外部連線」，
是**執行容器的 egress allowlist 沒有這個 host**——回的 403 body 是
`Host not in allowlist: mistral.ai.`。同一個容器對 `platform.claude.com` 抓得到
1.4 MB。所以這一格的正確讀法是「**我們在這裡讀不到**」，既不是站方拒絕，
也不是網路壞了。要查只能在 CI 裡查（`verify-article-metadata.py` 那條路，
它的 control probe 會先證明機器連得出去，再下判決）。

**診斷輸出已經做了**（`fix/sitemap-zero-yield-is-not-silence`，規格
`references/health-alarms.md`〈零產出不是沉默〉）：`_probe/<日>/report.md` 多一區
〈零產出診斷〉，把「200 / 0 筆」拆成四個 code——`source_empty`（站方那邊）、
`hints_matched_nothing` / `prefix_filtered_all`（我們這邊）、
`sub_sitemap_unreachable`（中間那一跳），並印出中途數字與過濾前的樣本 URL。

**2026-07-27 02:38Z 首班的判決出來了**：

```
| src-mistral-news | hints_matched_nothing | 我們 |
  index 有 1 張子 sitemap，hints ['news','blog'] 一張都沒命中
```

**是我們的設定對不上，不是站上沒東西。** 那份 sitemap-index 只有一張子 sitemap，
而它的網址不含 `news` 也不含 `blog`。剩下的動作只有一個：**下一班會把那張的網址
印出來**（`fix/hints-miss-without-showing-candidates` 補的——首班判對了卻沒印候選，
下一步還是查不下去），拿到網址就把 `sitemap_hints` 或 `url_prefix` 改對。
**不要用猜的改設定**：猜對了也沒有證據，猜錯了下一個人要重查一次。

以下是首班之前寫的：

**所以這條剩下的不是動手，是等一班。** 那條分支併進 `main` 之後跑過一班，去讀
`_probe/<日>/report.md` 的〈零產出診斷〉，`src-mistral-news` 屬於哪一種當場就有
答案。**併之前先跑，等於什麼都不會發生**——這個 repo 已經量過兩次了。

還沒接的那一半也要記著：那個 code 目前只渲染給人看，**沒有寫進
`_probe/source-runs.jsonl`，也沒有任何警報吃它**。`prefix_filtered_all` 連續三十班
CI 一樣是綠的。不順手接上去是刻意的——接之前得先想清楚門檻與消費者，否則就是再
造一個 [`value-沒人用`](#value-沒人用)。

---

## `來源已死但每班照樣有貨`

`零產出來源` 的鏡像，而且更難看見：**那三條至少是 0 筆，會出現在儀表上。
這一類每班穩定出貨，只是貨全是舊的。**

2026-07-27 逐條量 `_corpus/` 裡每個 source 的**最新一筆 `published`**：

| source | 每班筆數 | 最新一筆 | 落後 | 儀表上的樣子 |
|---|---|---|---|---|
| `src-meta-research` | 40 | **2023-05-17** | **3 年 2 個月** | 正常 |
| `src-qwen-blog` | 30 | 2025-09-23 | 10 個月 | 正常 |
| `src-media-venturebeat` | 14 | 2026-05-19 | 2 個月 | 正常 |
| `src-kol-karpathy` | 30 | 2026-04-30 | 3 個月 | 正常 |

（`src-kol-karpathy` 是 2026-07-28 fresh clone 複量時才掉出來的第四條——
上一版只列三條，因為那次的門檻切在 2026-06 而它剛好在界線附近。
**這說明門檻本身也要進設定，不是每次盤點的人自己挑一個。**）

病灶在 `pulse-monitor.py:322`：`silent_sources` 的判準是 `r["items"] == 0`。
**「這班抓回幾筆」被拿來代表「這條來源還在出東西嗎」**——正是這份清單開頭那句
「用一個比事實寬鬆的代理指標去代表事實」。兩者在平常的日子裡一致，正好在來源
死掉那天分岔，而不會有任何東西變紅。

要補的判準是現成的、而且只需要已經有的資料：**每條來源的
`max(published)` 與今天差幾天**，門檻沿用該來源的 `frequency`
（daily / weekly 各自一個容忍值），逾期進 `stale_source`。

`stale_source` 跟 `silent`（有來源、0 筆）必須是兩個名字。合成一個
「這條來源怪怪的」，下一個人得再查一次才知道要修抓取端還是換端點。

**另一半：`pulse-probe.py` 沒有 control probe，而它的一次性小弟有。**
`verify-policy-sources.py:237` 的 `control_probe()` 先證明機器連得出去，
連不出去就整份中止、不下任何判決。生產的 probe 沒有這一關：整條網路斷掉時
它會寫出 27 條各自獨立的 `robots_unknown`，讀起來像 27 個來源同時出事。
單條的處理是保守的、沒寫錯，缺的是**「問題在我們這邊」這個彙總訊號**。
2026-07-27 的 C-4 誤讀就是這個缺口在人身上的版本
（見 `docs/design/2026-07-27-published-is-a-proxy.md` 的 C-4′）。

---

## `Meta-沒有來源`

上一條的第一個受害者，單獨列是因為它已經在**對外站上造成沉默**，不只是監控缺口。

`_config/sources.yaml` 裡 Meta 唯一的來源是 `src-meta-research`，端點
`https://research.facebook.com/feed/`——一條**研究部落格**，而且最新一筆停在
2023-05-17。也就是說：**Meta 這家公司在本系統裡等於不存在**，而儀表全綠。

證據鏈是閉合的：`_config/entities.yaml` 把 `muse-spark` 標成
`status: unverified`，註解寫「僅見於單一次級來源，需 Tier-1 證據確認產品線名稱
與歸屬」。而 Tier-1 就在 `ai.meta.com/blog/`：2026-07-07「Introducing Muse
Image and Muse Video」、2026-07-09「Introducing Muse Spark 1.1」、
2026-07-21 還在更新。**不是拿不到，是沒在看。**

動手前要先查的（**在 CI 查，不要在開發容器查**——那裡有 egress allowlist，
量到的是別的問題）：

1. `ai.meta.com/blog/` 有沒有 feed。WebFetch 顯示頁面**沒有宣告**
   `<link rel="alternate">`，`/blog/rss/` 回 404。所以很可能又是一條
   sitemap 來源——那就跟 Claude / Grok 綁在同一個 C-3 上。
2. robots 對 `/blog/` 路徑的判決，用 probe 的 UA。
3. 換掉還是並存：`src-meta-research` 若確定廢棄，`lifecycle` 改
   `dormant` 並在 `note` 寫明「端點停更於 2023-05」，**不要直接刪**——
   刪掉等於把「我們曾經以為這裡有東西」也一起刪了。

---

## `跨語言重複-event`

**這是 `translation_chain` 接上之後才看得清楚的那一半。**

轉載鏈防的是「同一則 Event 裡有一篇翻譯被算成第二個聲音」。但那件事要先發生，
兩篇得**落進同一則 Event**——而 `belongs_to_event()` 只有兩條路：

| 路 | 跨語言行不行 |
|---|---|
| 同 `fingerprint` + 同 `facet` + 時間窗 | **行**。`event_fingerprint()` 帶 CJK 對照（通义→qwen…），`event_facet()` 的正則也收中文（发布 / 融资 / 事故…） |
| 標題相似度 ≥ 門檻（96 小時窗） | **不行**。中英文標題的 token 交集趨近於零 |

也就是說：**認得出具名模型版本的新聞，轉載鏈罩得住；認不出的（融資、事故、
人事、政策——大部分新聞）會直接變成兩則各自獨立的 Event。**

排在這裡而不是更前面，是因為它今天**不會發生**：沒有任何中文來源。
它是「中文媒體進來的那一天會立刻出現」的東西，所以要在加來源之前決定怎麼辦，
不是加完之後才發現庫裡每件事都有兩則。

修法的方向（還沒動手，也還沒寫規格）：讓 `belongs_to_event()` 在標題相似度
之外也看**實體集合**——`lib/entities.entity_ids()` 已經是現成的，轉載鏈就是
靠它跨語言的。但那會動到聚類門檻本身，屬於紅線 9 要先改文件的那一類，
而且改壞的方向很惡劣：門檻放太鬆會把不相干的事件併成一則，**併錯了不會有
任何東西變紅**，只會有一則標題與內容對不上的 Event 靜靜躺在庫裡。

---

## `候選詞被普通英文洗版`

`_dashboards/dictionary-gaps.md` 第一次跑出來，達標清單長這樣：

```
Industry 16 / Research 16 / LLMs 16 / Union 10 / LLM 10 / June 9 / Here 9
/ Energy 9 / July 8 / Building 7 / … / Gemma 5 / San Francisco 5 / …
```

`Gemma` 是真的該收的產品線，`LLM` / `LLMs` 是真的該收的技術詞。其餘大半是
**一般英文大寫詞**：`June`、`July`、`Here`、`One`、`Learn`、`Building`、
`Understanding`。

病灶在收割層不在這一頁：`pulse-probe.CAND_LATIN` 抓的是「大寫開頭的拉丁詞」，
而 `CAND_STOP` 只有二十來個字。英文標題的字首大寫、月份、地名、動名詞全都通得過。

**這條之所以現在才出現在清單上，正是那一頁的價值**：在此之前這些詞每班各自算
各自的，沒有任何地方把它們加起來，所以「雜訊佔了大半」這件事量不到。

修法方向（還沒動手）：`CAND_STOP` 要從「手寫二十個字」變成有判準的東西——
月份與星期是封閉集合可以整批排除；常見英文詞需要一份停用詞表，而那份表一旦手寫
就會是下一個「手寫清單」（第 6 個實例）。**先想清楚判準再動手**，否則只是把雜訊
換一批。

---

## `pending-覆蓋`

`_config/sources.yaml` 的 `coverage_watch.must_watch` 共 32 條，其中 **20 條 `pending`**：
DeepSeek、SSI、Thinking Machines、Perplexity、Cursor、Cognition、Scale AI、Z.ai、
Moonshot、MiniMax、ByteDance、Baidu、Tencent、TSMC、Broadcom、Groq、Cerebras、
CoreWeave、AWS、Cohere。

標了 `pending` 所以**不觸警**——這是誠實的做法（紅線 8），但「誠實地承認沒覆蓋」
跟「覆蓋到了」是兩回事。其中 DeepSeek、Scale AI、MiniMax、Broadcom、Cerebras
已經**在別人的語料裡被看見**，代表它們有新聞在流動，只是我們沒有第一手來源。

排這麼後面不是因為不重要，是因為它**沒有在騙人**：清單上寫著「沒有」，實際也沒有。
這是純粹的擴充工作，隨時可以做，做多少算多少。

**2026-07-27 補**：這 20 條就是「哪些必盯目標沒有來源」的答案，已經盤點過、已經
誠實掛著，判準在 `pulse-monitor.py`（含 `silent_pending_clock` 那個觀察期守衛）。
任何新東西要回答同一個問題，**讀這裡，不要重算一份**——重算的那份會在門檻沒人動的
日子裡跟這裡一致，正好在有人只調了其中一邊的那天分岔，而不會有任何東西變紅。
理由的完整版寫在 `lib/dictgaps.py` 的 docstring 裡。

---

## `people-第三步`

`person_id` 的獨立性計算（連通分量）已經接上、selftest 有釘。但
**每一列語料的 `author` 還沒有真的綁到 `person_id`**——現在 `person_id` 只從
`sources.yaml` 的來源層設定來。所以「同一個人在兩個平台發文」只有在那個人自己有
一條專屬來源時才抓得到；他投稿到媒體、或在 podcast 上講，綁不起來。

`pulse-probe.py` 第 74 行留了註解說明這件事。

---

## `字典掃描範圍分岔`

`_config/entities.yaml` 有兩個消費者，掃的文字範圍不一樣：

- `pulse-cluster.py:223` → `entity_ids(title, ...)`，**只掃標題**
- `pulse-probe.py:782` → `match_entities(f"{title} {summary}", ...)`，**掃標題＋摘要**

差多少：拿現有語料量，命中 ≥2 個實體的比率，**標題＋摘要是標題 only 的三倍**。
（絕對百分比會跟著語料長，重量指令在最後一節；**結論是那個倍數，不是那兩個數字**。）
也就是說，聚類看到的實體世界跟字典補漏看到的實體世界，不是同一個。

`cluster.py` 第 221–222 行有註解說明「為什麼走字典不走 token 交集」——中英文標題的
token 交集趨近於零，而字典的 aliases 兩種語言都收。但**沒有一行字說明為什麼只掃
標題**。所以現在分不出兩件事：標題 only 是「刻意的高精確度選擇」（摘要雜訊多，
聚類寧可漏不可錯），還是「當初就這樣寫了」。

排在這裡不是因為它在騙人——它沒有對外宣稱過任何覆蓋率。是因為它**會誤導下一個人**：
任何要靠實體命中長出來的東西，第一件事就是撞上「我該用哪一個」，而 repo 裡兩個答案
都在跑、都沒有理由。這是 `gate-未接線` 那個家族的變體，只是分岔的不是門檻，是**輸入
範圍**——比門檻更難發現，因為兩邊的碼看起來都對。

修法二選一，**兩個都比現在好**：把選擇寫成 `gate.yaml` 的一個 key（然後真的接線，
別變成 `gate-未接線` 的新成員），或在 `lib/entities.py` 寫一句話說明為什麼兩個消費者
本來就該不同。**不能接受的是繼續兩個都對。**

---

## `實體命中用過即丟`

上面那兩處都算出了「這一列語料命中哪些實體」，然後：

- cluster 拿去算聚類重疊（`entity_overlap_min`），算完丟掉。
- probe 拿去找字典補漏候選，算完丟掉。

**沒有任何地方留下「哪些實體在什麼時候、在誰的語料裡一起出現過」。**
`Events/` 的 frontmatter 只有一個 `company:` 欄，存的還是 canonical 標籤（`NVIDIA`）
不是 id（`nvidia`）；整個 `Events/` 找不到任何一則存了多實體命中。

這跟 `value-沒人用` 是同一個家族的**反面**：`value` 是算了一個沒人要的東西，這個是
算了一個有人要、卻沒留下來的東西。兩個都是「這段碼看起來在做事」。

比 `value-沒人用` 急的地方在於**它有時鐘**：這件事**補不回來**。`_corpus/` 只有幾天
（見 `corpus-累積`），Event 又只存單一 company 欄，所以「過去 N 天誰跟誰一起出現過」
今天沒有任何辦法回答，而且**每過一班，將來能重建的歷史就少一班**。

排在 `字典掃描範圍分岔` 後面，是因為修法依賴那一條的答案：先決定掃什麼，才知道要留
什麼。但兩條之間不該隔太久——前一條是一個下午的設計決定，這一條是每天在流失的東西。

**這不是「要先做拓撲」。** 只寫不判——每班把已經算出來的命中 append 下來、不加任何
判斷邏輯——就足以停止流失，而且完全不碰 hot loop 的判斷（紅線 1）。

---

## `corpus-累積`

現在是每天一個目錄、只放當天新看到的列，磁碟上有 **3 天**（07-24…07-26）。
覆蓋範圍檢查因此只有幾天的實有語料，monitor 自己會印「語料期間不足 30 天，沉默
天數僅供參考」。

要不要改成累積視窗，我沒有動，因為那會改變所有「近 30 天」統計的意義。
`fix/coverage-uses-own-clock` 併進去之後（已併），coverage 的守衛已經不再依賴語料庫
總長度，所以這題的急迫性降了一階——**但語料本身還是只有 3 天，決定權在你。**

**2026-07-27 補一個反方向的理由**：急迫性對 coverage 守衛確實降了，對**證據歷史**
沒有降。語料保留幾天，就等於「誰跟誰一起出現過」最多只能回溯幾天，而這是**單向
流失**——不像門檻可以改回來，過去的語料丟了就是丟了。所以這條的「決定權在你」
後面有一個時鐘在跑。相鄰的一條是 `實體命中用過即丟`：那一條講的是就算語料還在，
命中結果也沒被留下。兩條要一起看才是完整的問題。

~~**還有一條隱藏依賴，決定之前要先知道**：對外站事件頁的〈發展歷程〉，每筆證據的
標題與日期是 `pulse-render.load_corpus_index()` 從 `_corpus/` 現查的。~~
**2026-07-27 解除**：那兩個欄位改成優先讀 Event 自己的 `evidence[]`，既有 note 由
`scripts/migrate-2026-07-27-evidence-titles.py` 一次性補回，selftest 有一條把語料
索引清空驗它照樣印得出真標題與真日期。**所以這條現在真的只剩「要不要改成累積視窗」
本身，沒有別的東西綁著它了。**

---

## `value-沒人用`

`scoring.py` 每則 Event 都算一個 `value`，寫進 frontmatter，**然後沒有任何東西讀它**。
`pulse-render.py` 只依日期排序；全站沒有一處依 `value` 排序或篩選；
`dist/index.html` 裡 "value" 出現 **0 次**。

所以 heat 那次遷移造成的 rank delta（51 則裡 36 則換位、最大位移 12 名）**不是使用者
看得到的排名變動**。這件事必須這樣講，不然聽起來像動了排名。

一個算得很認真、沒人用的欄位有兩個誠實的出路：接上（讓它真的決定排序或門檻），
或刪掉。第三條路——繼續算著、繼續寫進 frontmatter、繼續沒人用——是紅線 8 那種
「留著看起來像有功能的東西」。

沒有排更前面是因為它**不騙人**：`value` 沒有對外宣稱它決定什麼。它只是浪費。
但它跟 heat 是同一個家族——`heat` 是「算了一個沒量到的東西」，`value` 是「算了一個
沒人要的東西」，兩個都是「這段碼看起來在做事」。

---

## `stale-backfill-無出口`

`Events/` 共 51 則（`published` 36、`review` 14、`dropped` 1），其中帶
`stale_backfill` 的有 **12** 則。

這些是「設計上擋著」的舊聞回填，不是卡住。行為是對的，但**沒有任何路徑讓它們離開
這個狀態**——它們會永遠留在 review，而且數量只會單調增加。要嘛給一個 `archived`
終態，要嘛定期清掉。現在只是靠 monitor 把它們跟真正的待處理分開印，不讓數字互相
污染。

---

## `分支刪不掉`

**2026-07-27 重寫：上一版的兩條裡，第一條已經做完，第二條的診斷是錯的。**

### 一、刪掉已合併的分支 → 做完了，而且原本的說法就不對

上一版寫著「`git push origin --delete` 被這個 session 的安全分類器擋著」。
實測**它沒有被擋**——拿排程任務那份憑證跑 `git push origin --delete`，
一次就成功（`fix/journey-evidence-source`，已完整併入 `main`）。

遠端從 34 條 head 降到 3 條（`main` + 一條進行中的 PR 分支 + 一條等它併掉的）。

### 二、「GitHub API 被 proxy 擋（403）」——**擋人的不是 GitHub，也不是 proxy**

`api.github.com` 回的 403 body 是：

```
GitHub access to this repository is not enabled for this session.
Use add_repo to request access.
```

那是**執行環境的 repo 授權閘**，不是 GitHub 拒絕、也不是網路層的 proxy。
證據：同一個 session、同一份憑證，**`git push` over HTTPS 完全正常**——
推分支、刪遠端分支都成功。被關住的只有 REST API 這一條路。

**這是同一隻病在這份清單裡的第三次**（前兩次見
`docs/design/2026-07-27-published-is-a-proxy.md` 的 C-4′，以及第 4 節（庚））：
**用「我在這裡做不到」去代表「這件事做不到」**。三次的形狀一模一樣，
三次都寫成了待辦事項，而其中兩件其實一直做得到。

所以正確的現況是：

| 動作 | 這個環境 | 怎麼做 |
|---|---|---|
| 推分支 | **可以** | `git push`（憑證見排程任務，不入庫） |
| 刪遠端分支 | **可以** | `git push origin --delete <branch>` |
| 開 PR / 合併 / 讀 Actions log | 不行 | REST API 被 session 的 repo 閘關著；用 `.../compare/<branch>?expand=1` 這種預填網址，人按一下 |

「PR」在這裡仍然是「分支 + 預填網址 + 對話裡的 review 說明」，但理由要寫對：
**不是 GitHub 擋，是這個 session 沒有那個 repo 的 API 授權。**

**下面這段仍然成立，而且是這條唯一還沒解決的部分**：一條「我做完、你來合」的
交棒，如果你那頭沒動作，沒有任何東西會變紅。跟「隔離候選是機器交棒給人的唯一介面，
而它是斷的」同一個形態，只是這次的介面是你我之間。它自己不會叫。

**2026-07-27 它真的響了一次，而且沒有人聽見。** 半夜潤稿那班照紅線 5
（「碼的問題自己開 PR，不要直推 main」）查出 C2 apply 的缺陷、修好、
19:29Z 推了 `fix/c2-apply-reads-committed-worklist`，並把分支名寫進事後摘要。
**到隔天早上 06:00 仍然沒有人開 PR，也沒有任何東西提醒過任何人。**
那條分支現在落後 `main` 12 個 commit，而且已經跟 PR #33 產生衝突——
**交棒延遲的成本不是零，它會長成 rebase。**

---

## `兩條夜間鏈只靠時鐘耦合，而餘裕沒有人在量`

`data-refresh.yml`（cron `0 16 * * *`，台北 00:00）與半夜潤稿那條 Cowork 排程
（`0 19 * * *`，台北 03:00）之間**沒有任何交握**，只有三小時的時鐘間隔。
`scripts/enrich-runbook.md` 步驟 0 的前置檢查是唯一的防線，而它防的是**後果**
（clone 到昨天的 repo），不是**成因**（Actions 遲到）。

2026-07-27 實測：

```
data-refresh  排定 16:00Z   實際 17:26Z   遲到 86 分
半夜潤稿      排定 19:00Z   實際 19:08Z
實際餘裕      102 分（名目 180 分）
```

runbook 自己記著「實測誤點過 96 分鐘」。也就是說**昨晚的餘裕只比歷史最差多 6 分鐘**，
而這個數字沒有任何地方在記錄、也沒有任何門檻在看它。
2026-07-24 那晚（一則 NVIDIA/南韓事件卡在 review 沒人發現）就是這條餘裕被吃光的樣子。

要做的不是把間隔拉大——那只是換一個數字繼續猜。要做的是**把餘裕變成一個被記錄的量**：
潤稿端步驟 0 已經在看 `_corpus/$(date -u +%F)/` 在不在，順手把
「這一班的語料是幾點寫進來的、我幾點到的」寫進事後摘要與 `_dashboards/health.md`，
連續幾天逼近零就該有人知道。**現在它只有在真的翻車那一天才看得見。**

---

## 附：已經修掉的

按併進 `main` 的時間排。**這一節只放已經在 `main` 上的**——躺在分支上的不算修好，
它們留在上面各自的條目裡，直到併進來為止。

| 事 | 修了什麼 |
|---|---|
| `判斷層自相矛盾`（`fix/two-lies-on-the-public-site`） | rule-tag 不再烙進 prose，改由 `layer_html()` 即時算，與警示框同一個真相源；舊 note 裡凍結的那一份由 `strip_frozen_tag()` 剝掉，不必遷移。**判斷層只剩一個時鐘** |
| `傳播因子印成 0`（同上） | `scoring` 對空 metrics 回 `None` 不回 0（含 `crossRegion`），render 印「未量測」且**不畫比例條**（空灰軌道跟「量到 0」長得一樣）。既有 56 份 note 由 `migrate-2026-07-28-unmeasured-factors.py` 一次性改成 null——**只改產生器到不了已經產出的東西**，那是前一天剛上過的課 |
| `cron-收班`（一次性排程 + 每週自癒） | 抓取頻率 07-27 收班回 `0 16 * * *`、`--stale-days` 兩處都回 7。**複查方式刻意不看排程跑了沒**，只讀 `data-refresh.yml` 的實際值 |
| `fix/machine-writes-unbacked-robots-false`（PR #1） | 機器寫 `robots_ok: false` 也要交入場券；selftest 掛進 CI |
| `fix/retry-exhaustion-mislabels-429` | 重試耗盡不再謊報成重導；robots 回 200 但內容不是 robots.txt 不算放行 |
| `fix/ci-swallows-failures` | CI 不再吞掉 probe 的 exit 3；Vault pages 兩支拆成獨立 step，`bash -e` 管得到 |
| `fix/nonatomic-config-write` | 狀態檔一律 tmp + `os.replace()`，失敗刪 tmp |
| `fix/alarms-that-mute-themselves` | 目錄名不是證據（嚴格日期 + 內容驗證）；未來日期判紅；缺 `ingested_at` 本身就算警報 |
| `fix/health-snapshot-dry-run`（PR #2） | 隔離候選真的寫進磁碟快照（機器交棒給人的唯一介面接回來了）；`--json` 這種只看的跑法不再改持久狀態 |
| `fix/observed-counts-item-days`（PR #3） | `Sources/*.md` 不再把「量不到」印成「0 筆」；`items_observed` 改數相異 `(source_id, url)`；`events_bound` 排除 `dropped` |
| `fix/coverage-uses-own-clock`（PR #4） | 沉默判準改用每條實體自己的 `first_fetch_at`，不再拿整個語料庫的長度當尺 |
| `docs/backlog-refresh` | 這份清單本身；變異盤點層（`scripts/mutate.py` + `mutations.yaml` + 獨立工作流），並補掉它第一輪抓到的五個洞 |
| `fix/heat-claims-a-measurement`（PR #7） | `heat` 沒量到就寫 null 不編數字；新 blocker `unmeasured_heat`；`references/readiness-gate.md`；51 則遷移 + 回滾 |
| `fix/monitor-exit-codes-vs-main`（PR #8） | 死人開關的 exit code 走真子行程釘住；`FM_FROM_CONFIG` 白名單邊界改由行為守；`ingested_at` 黏性改成真的跑第二輪；併回 `main` 解衝突 |
| `fix/narrative-drops-the-fake-heat`（隨 PR #9 併入） | `narratives.yaml` 那兩句拿假 heat 當論據的話重寫；加上掃全檔（含 `thesis` / `lenses`，夜間鏈永遠不會重寫的兩段）的測試與拒收執法；M26–M28 三條說謊路徑 |
| `fix/gate-keys-unmarked`（PR #9） | 未接線清單從手寫改成掃 `gate.yaml` 全部 55 個 leaf key 機械列舉（`scripts/lib/gate_keys.py`）；掉出 `quality.weights` 與 `readiness.require_primary_evidence` 兩個從沒被列過的 key；A／B／C 三類分開；M29–M32 |
| `docs/backlog-tidy`（PR #10） | 這份清單的編號 P0–P10 改成不會變的名字；修掉 `selftest.py:794` 與 `references/readiness-gate.md:112` 兩處指著編號的死引用；補一條「原測試只比對 `path`，恆真」的空測試（`52752bd`） |
| `fix/sitemap-zero-yield-is-not-silence` | 「200 / 0 筆」拆成四個 code：站方那邊沒東西 vs 我們這邊接不上。規格 `references/health-alarms.md`〈零產出不是沉默〉 |
| `fix/evidence-forgets-what-it-saw` | 證據記錄留下 `title` 與 `published`；reload 不再拿 url 頂替 title（頂替之後，拿標題比相似度會**照樣算得出一個數字**，只是算的是網址）。新增 `references/evidence-tiers.md`——那個檔名被指了兩次而一直不存在 |
| `fix/translation-chain-counts-a-rewrite` | `evidence.translation_chain` 四個 leaf 全部接上：跨語言 + 實體集合 Jaccard ≥ 0.80 + 48h 窗 → 標 `suspected_repost`、不計入獨立性。實體比對層抽到 `lib/entities.py`（單一真相源）。M43–M47 各守一個設定值真的被讀 |
| `feat/event-titles-in-chinese` | Event 標題 51/51 全是英文原文——六層 prose 是中文、站台框架是中文，只有讀者唯一會看到的那一行不是。`title_zh` + `title_zh_src` 進版控，原文變了譯文自動失效退回原文；驗章跟榜單描述共用 `lib/zhtext.py` |
| `fix/c2-skips-in-silence` | 潤稿端 C2 段（榜單描述中文化）失敗時整段跳過，**而跳過跟「沒東西要翻」印起來一樣**——`desc-zh.json` 從沒進過版控也沒人發現。觀測改由一定會跑的 Actions 那班量，分得出「量不到 / 從來沒翻過 / 有過然後停了」 |
| `fix/dictionary-gaps-report-to-nowhere` | `clustering.unknown_entity.report_to` 指的那一頁以前不存在，現在每班產生；晉升門檻搬進 `gate.yaml`，`_probe` 當班區塊與累積頁讀同一份 |
| `fix/backlog-status-is-hand-written` | 現況表從手寫改成每班重生成（`_dashboards/backlog-status.md`）。**這是第 9 條實例的第二次修法**——第一次（把量測時間寫進標題、請下一個人複量）三小時就失效了 |

共同主題是**警報自己把自己關掉**：用一個比事實寬鬆的代理指標去代表事實。代理在
順利的日子跟事實重合，所以平常測不出來；它只在你最需要它準的那一天分岔。規格寫在
`references/health-alarms.md`。目前收集到的實例：

1. 用「目錄名」代理「那天真的有語料」
2. 用「隔離候選算出來了」代理「有人看得到它」
3. 用「語料庫有多長」代理「這條線被觀察多久」
4. 用「碼裡有沒有這句話」代理「跑起來會不會叫」（`references/health-alarms.md`「算對了不等於會叫」）
5. 用「測試有幾條」代理「壞掉會不會被抓到」（`references/mutation-inventory.md`）
6. 用「一份手工清單」代理「所有未接線的 key」（[`gate-未接線`](#gate-未接線)）
7. 用「入口已經修好」代理「站上沒有假話」（`fix/narrative-drops-the-fake-heat`：
   假 heat 的源頭修掉了，但已經寫成散文的兩句結論在 `lenses` 裡，而 `lenses` 是夜間鏈
   永遠不會重寫的欄位——堵住上游只擋得住新的謊）
8. 用「編號」代理「清單上的某一件事」（就是上面〈為什麼這裡沒有編號〉那一節）
9. 用「一張量過的現況表」代理「現況」。最刁的一點：它是往**變好**的方向失準的
   （303→322），沒有人會覺得不對勁。**這一條的第一次修法也失敗了**——把量測
   時間寫進標題、請下一個人複量，是一個靠人記得的機制，三小時就過期了。
   真正的修法是把數字整個搬出手寫檔案（`_dashboards/backlog-status.md`，每班
   重生成），**手寫檔案裡一個數字都不留**。
10. 用「這條規則寫下來了、也修好了」代理「這條規則被遵守」（`references/timezones.md`）。
    2026-07-26 發現 `_as_date()` 沒把時區歸零到 UTC，修好了、記進
    `references/health-alarms.md`、還寫了「只要哪天開始收本地時區的來源，影響面
    就會長回來」。但那次**只修了發現它的那一個消費端**——`pulse-cluster.py`
    （產生 `evt-<日期>-<hash>` id 的那支）一直在做裸的 `.date()`。
    它一直是綠的，因為當時的語料剛好讓兩種寫法答案一樣。
    這一條的形態是新的：**前九條是「沒有人量」，這一條是「量過了、修過了、
    還記下來了」，而規則依然只落實了一半。** 所以修法不是再改一個函式，是把
    取日期收成 `lib/clock.py` 一個入口，再加一條機械檢查禁止其他地方自己取。

## 附：怎麼重新盤點這份清單

**大部分的數字已經不用你自己跑了**：`_dashboards/backlog-status.md` 每班重生成，
Events、語料、來源、`coverage_watch`、`gate.yaml` 接線數、最後一班 probe 都在那裡。
下面剩下的是**那一頁刻意不放的**——它們不是每班量得到的事實：

```bash
python3 scripts/selftest.py | tail -1                 # 有幾條測試
python3 scripts/mutate.py                             # 有幾格守不住（幾分鐘）
git fetch origin --prune                              # 先 fetch，不然下面全是舊的
git log --oneline -1 origin/main
git branch -r --no-merged origin/main | grep -v HEAD  # 未併分支
git branch -r --merged origin/main | grep -v 'HEAD\|origin/main' | wc -l   # 可刪幾條
git merge-tree --write-tree origin/main <branch>      # 那條能不能乾淨併
grep -n 'heat' _config/narratives.yaml                # 站上還在說謊嗎
grep -n "cron:\|stale-days" .github/workflows/data-refresh.yml   # cron-收班 收了沒
# 零產出來源：每條來源每一班的 status，不是只看最後一班
#（那一頁只印最後一班的；要看趨勢還是得自己跑）
python3 -c "
import json;from collections import Counter
runs=[json.loads(l) for l in open('_probe/source-runs.jsonl')]
for sid in ('src-mistral-news','src-media-theregister','src-kol-thezvi'):
    print(sid, Counter(s['status'] for r in runs for s in r['sources'] if s['id']==sid))"
```

`字典掃描範圍分岔` 的那個倍數（兩個消費者各自看得到多少多實體語料）：

```bash
python3 - <<'PY'
import sys, glob, json, yaml; sys.path.insert(0, 'scripts')
from lib.entities import build_matcher, entity_ids
t = build_matcher(yaml.safe_load(open('_config/entities.yaml')))
for mode in ('title', 'title+summary'):
    n = m = 0
    for f in glob.glob('_corpus/**/*.jsonl', recursive=True):
        for line in open(f):
            if not line.strip():
                continue
            it = json.loads(line); n += 1
            s = it.get('title') or ''
            if mode != 'title':
                s += ' ' + (it.get('summary') or '')
            if len(entity_ids(s, t)) >= 2:
                m += 1
    print(f"{mode:14s} {m}/{n}")
PY
```

要在本機看那一頁現在會長什麼樣（不寫檔）：

```bash
VAULT_DIR=$PWD python3 scripts/pulse-backlog-status.py --dry-run
```

`mutate.py` 那一行才是「測試守不守得住」的答案。`selftest | tail -1` 給的是**有幾條
測試**，那是兩件不同的事。

四個踩過的坑，複量的時候會再踩到：

- **`git branch -r --merged | grep -v main` 會少數**——`fix/monitor-exit-codes-vs-main`
  的名字裡就有 `main`。要 `grep -v 'HEAD\|origin/main'`。
- **`git log origin/main` 要在 `git fetch` 之後**，同一串命令裡順序寫反就會拿到舊的。
- **在分支上跑的 selftest 不描述 `main`**。要量 `main` 就開一個
  `git worktree add /tmp/ap-main origin/main`，跑完 `git worktree remove` 掉。
- **新容器要先 `pip install ruamel.yaml`**（CI 有裝，`data-refresh.yml` 第 52 行；
  乾淨的容器沒有）。少了它，`selftest.py` 不會說「缺套件」，而是死在一個看起來
  完全無關的 `FileNotFoundError: …/_probe/source-health.json`——因為 `_run_sh()`
  只回傳 `(returncode, stdout)`，子行程那句 `[fatal] --apply 需要 ruamel.yaml`
  寫在 stderr，被丟掉了。**紅的地方不是壞的地方**，2026-07-26 這次複量在這裡卡了
  十分鐘。
