# vault 的 note 結構：哪些節點存在、哪些邊是真的

> 這份是**規格**，`scripts/pulse-entity-notes.py`（`Tracks/` `Actors/`）、
> `scripts/pulse-source-notes.py`（`Sources/`）、`scripts/pulse-cluster.py`
> （`Events/`）是它的實作。不一致時以本檔為準，**先改本檔再改碼**（紅線 9）。

## 這份檔案為什麼到今天才存在

帳號層的 skill（`ai-pulse-tracker`）的 `references/obsidian-schema.md` 從第一天
就畫好了 vault 的結構：

```
Events/                 # 唯一事實節點
Sources/                # 來源 note
Tracks/                 # 六大主線 note
Actors/                 # 公司 / 人物 note
_dashboards/            # Dataview 查詢頁
```

**repo 這端沒有對應的規格檔，而 `Tracks/` 與 `Actors/` 兩個資料夾一直不存在。**
`_dashboards/` 也不是 Dataview——社群外掛一個都沒裝（`.obsidian/` 只有 core
plugin，沒有 `community-plugins.json`），那幾頁是 `pulse-dashboard.py` 與
`pulse-monitor.py` 每班烤出來的靜態表。

這是同一個形態的第五次：**規格說有，實作沒有，而沒有任何東西會紅**
（前四次是 `references/evidence-tiers.md`、`gate.yaml` 的
`clustering.unknown_entity.report_to`、手寫的未接線清單、手寫的現況表）。
skill 是設計圖、repo 是照圖蓋的實體，兩份文件分屬兩個地方本身沒問題；
問題是**沒有任何機制會發現實體少蓋了一層**。

## 節點與邊

| 節點 | 產生者 | 這一層回答的問題 |
|---|---|---|
| `Events/<id>.md` | `pulse-cluster.py` | 發生了什麼（唯一事實節點） |
| `Sources/<source_id>.md` | `pulse-source-notes.py` | 這條來源是什麼、四態各是多少 |
| `Tracks/<顯示名>.md` | `pulse-entity-notes.py` | 這條主線上有哪些事件 |
| `Actors/<canonical>.md` | `pulse-entity-notes.py` | 這家公司有哪些事件、字典收了它沒有 |

邊：

```
Event  --[[Sources/…]]-->  Source     （在 Event body 的〈證據〉區塊，2026-07 就有）
Track  --[[Events/…]]-->   Event      （2026-07-27 新增）
Actor  --[[Events/…]]-->   Event      （2026-07-27 新增）
```

### 為什麼新的邊是從維度頁指向 Event，不是反過來

`Event → Track` 與 `Event → Actor` 看起來更自然：把 frontmatter 的
`track: 基礎設施與成本` 改成 `[[Tracks/基礎設施與成本]]` 就好。**不這樣做，
兩個具體理由：**

1. **`company` / `track` 是機器欄位。** `pulse-render.py`、`pulse-dashboard.py`、
   `pulse-narrative-prep.py`、`pulse-gate.py` 都在讀它們的**字串值**。改成
   wikilink 字串，每一個消費者都要跟著改，而漏改的那個不會炸——它只會比對不到，
   然後那條線在對外頁面上少一半事件。這正是本 repo 一直在抓的那種安靜失敗。
2. **已 enrich 的 Event body 是刻意不重寫的**（`rescored_enriched_markdown`
   保留潤好的 prose）。要在 body 裡加一個〈關聯〉區塊，就得動到那條保護，
   或者接受它只出現在還沒潤稿的那一半 Event 上。

而 **Obsidian 的 graph 是無向的**：`Tracks/X → Events/Y` 這條邊在 graph view
上跟反過來畫一模一樣，Event 頁的 backlink 面板也會列出 `Tracks/X`。
**零風險拿到同一張圖**，所以這裡選成本低的那一邊。

代價要寫清楚：**Event 的 frontmatter 上仍然沒有 wikilink**，所以在 Obsidian 裡
從一則 Event 往外跳，要走 backlink 面板而不是點 property。這是刻意的取捨，
不是還沒做完。

## `Tracks/<顯示名>.md`

一條主線一頁，六條固定（`lib/tracks.py` 是那份對照表的單一真相源）。

- frontmatter：`id`（`track-<slug>`）、`kind: track`、`slug`、`tags: [track]`。
- `thesis`：抄自 `_config/narratives.yaml` 的**編輯層**。刻意**不抄** `now` /
  `next`——那兩段每夜重寫，抄過來會讓六個檔案每天產生一次沒有新資訊的 diff，
  而且會出現兩份可能不一致的同一段話。要讀那兩段就去看 `narratives.yaml`。
- 事件清單：這條線上的 Event，按日期新到舊，標出 `status`。

`track` 值認不出來的 Event（別名表沒收的寫法）**不會被靜靜丟掉**：它們列在頁尾
的〈認不出主線的事件〉區塊。認不出來是字典或 enrich 的問題，不是「這則不存在」。

## `Actors/<canonical>.md`

一家公司一頁。名單來自兩邊的聯集：

- `_config/entities.yaml` 的 `companies`（**收錄**：字典裡有它）
- `Events/*.md` 的 `company` 值（**有效產出**：真的有事件掛在它身上）

兩邊都要，因為兩種缺席的意思完全不同：

| 情況 | 代表什麼 |
|---|---|
| 字典有、Event 沒有 | 我們認得這家公司，但這段期間沒有它的事件——可能是真的沒新聞，也可能是沒有來源看得到它（對照 `coverage_watch`） |
| Event 有、字典沒有 | **字典缺口**。實測有三個：`NTT DATA`、`vLLM`、`industry` |

`industry` 是 `infer_company()` 認不出實體時的泛稱兜底，**不是一家公司**，
所以它不產頁，但會在〈沒有歸屬到公司的事件〉區塊被列出來——那是一批
`generic_entity` 待修的 Event，不是一個 Actor。

frontmatter：`id`（`actor-<entity_id>` 或 `actor-<slug>`）、`kind: company`、
`in_dictionary: true|false`、`aliases`（抄自字典）、`tags: [actor, company]`。

## Event 的標題有兩個

> 實作：`scripts/pulse-title-prep.py`（誰要翻）、`scripts/pulse-title-apply.py`
> （寫回）、`scripts/lib/zhtext.py`（驗章，跟榜單描述共用）、
> `scripts/pulse-render.py` 的 `title_html()`（顯示）。

`Events/*.md` 的 `title` 是**來源的原始英文標題**。六層 prose 是中文、站台框架是
中文、只有標題不是——2026-07-27 實測 51 則 Event **全部** 51/51 英文標題，而標題
正是讀者在首頁、時間軸、卡片上唯一會看到的那一行。

| 欄位 | 是什麼 |
|---|---|
| `title` | 一手：來源怎麼寫就怎麼存，**永遠不改** |
| `title_zh` | 二手：潤稿端翻的中文，可能不存在 |
| `title_zh_src` | `title` 在翻譯當下的雜湊 |

### 為什麼要有 `title_zh_src`

譯文綁在**當下那句原文**上。原文變了、雜湊對不上 → 前台**退回原文**，並重新排進
待譯清單。少了這一格，標題哪天被改掉，畫面上會掛著一句看起來很合理、其實在講舊
標題的中文——**那比沒有中文糟得多**。跟榜單描述的 `desc-zh.json` 是同一條規矩、
同一支驗章（`lib/zhtext.py`）。

### 兩個都印，中文在上原文在下

原文永遠一併顯示。這不是版面潔癖：**標題是最容易被翻歪的一句，而讀者無法從一句
中文回推它翻自什麼。** 紅線 2 的延伸——譯文是二手的，讀者要能看到一手的那句。

### `title_zh` 是 sticky 欄位

`event_markdown()` 會**整份重寫** frontmatter，沒被明確帶過去的欄位會被抹掉。
`title_zh` / `title_zh_src` 是第三、第四個踩到這個坑的欄位（前兩個是 `ingested_at`
與 backfill 旗標，見 `fix/backlog-flag-erased-by-second-run`）。所以
`Event` 物件帶這兩格、reload 時讀回來、`event_markdown()` 明確寫出去。

### 這一層不保證什麼

- **不保證翻得對。** 驗章是機械的：有沒有中文、長度、AI 腔黑名單、綁不綁得上原文。
  「翻得準不準」沒有任何機械判準，只有原文並排在旁邊讓讀者自己看。
- **不保證每一則都有中文。** 待譯清單有單晚上限（預設 20），而且潤稿鏈可能整段
  跳過。沒有中文就是印原文，不是空白。

## `coverage`：這則事件發生時，我們看得到嗎

> 完整規格與呈現規則見 `references/event-timestamps.md`〈第三個現場：呈現層〉。

封閉集 `observed` / `backfilled` / `unknown`，由 `_probe/state.json` 的
`first_fetch_at` 與 Event 自己的 `happened_at` 推導：

```
observable_from = min(first_fetch_at[s] for s in 該事件證據的來源)
```

存在的理由：`Events/` 的日期只有**外面世界**那個時鐘，所以一則 07-07 的事件，
畫面上看不出我們是 07-07 就在追、還是 07-26 首抓時才撈回來的。2026-07-27 實測
36 則已發布事件裡有 30 則屬於後者。

**這一格是推導欄位，不是 sticky 欄位。** 上面 `title_zh` 那批要在 reload 時讀回、
寫檔時原樣寫出，因為它們的值只有那一次算得出來；`coverage` 相反——每班從
`state.json` 重算，`event_markdown()` 整份重寫不會傷到它。**不要**把它加進
sticky 清單：寫死之後，來源的 `first_fetch_at` 修正了它也不會跟著改。

## `_dashboards/` 是靜態表，不是 Dataview

skill 的規格寫的是 Dataview 查詢頁。實作不是，而且**刻意不是**：

- 社群外掛一個都沒裝。裝 Dataview 等於在 vault 上加一個執行期依賴，
  而這條鏈的紅線是「可離線、可重現、零 API 成本」。
- 這條鏈自己**不開 Obsidian**。`_dashboards/*.md` 是給人看的產物，由 CI 每班
  烤好；Dataview 的查詢只有在人打開 Obsidian 時才會算，CI 產出的檔案裡會是
  一段沒有結果的程式碼區塊。**一份在 CI 裡永遠是空的儀表板，比沒有儀表板更糟。**

`.obsidian/core-plugins.json` 的 `bases: true` 已經開著，但**沒有任何 `.base`
檔**。Bases 是 core plugin、不需要裝東西、而且只在人開 Obsidian 時算——它是這一層
未來合理的探索層。**現在沒做**，因為在 CI 容器裡驗證不了 `.base` 的 schema，
寫一個沒人驗證過的設定檔就是在製造下一個「看起來對」的東西。記在 `BACKLOG.md`。

## 共同規則（跟 `references/vault-pages.md` 同一套）

只寫到「日」、內容沒變就不重寫、原子寫、allowlist 欄位、零 LLM、不編造。
每個數字不是抄自 `_config/`（人寫的設定），就是數自 `Events/` / `_corpus/`
（機器量到的事實）。

## 這一層不保證什麼

- **不保證 graph 上的邊代表因果或重要性。** 一則 Event 掛在某家公司底下，
  只代表 `infer_company()` 從實體命中推出來的歸屬，不代表那家公司是主角。
- **不保證 Actor 頁的事件數等於那家公司的新聞量。** 它等於「我們的來源看得到、
  而且過了聚類與門禁的那些」。四態分離的第三格，不是第一格。
- **不保證認不出來的 track 值會被修。** 這一層只讓它們看得見。
