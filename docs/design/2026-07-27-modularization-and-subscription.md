---
title: AI Pulse 模組化重構 + 訂閱／電子報架構設計
status: proposal
author: 設計協作（Cowork）
date: 2026-07-27
review_cycle: 一次性提案，待人為拍板後轉為 references/
supersedes: —
red_lines_touched: [runtime 0 LLM (#1), 隱私邊界 (#6), docs-first (#9)]
---

# AI Pulse 模組化重構 + 訂閱／電子報架構設計

> 本文件是**設計提案**，尚未動任何程式碼。依 repo 紅線 #9（docs-first），
> 這份文件就是「先改對應 docs、再改碼」的那份 docs。拍板後應拆進 `references/`
> 與各 `_config/*.yaml` 的檔頭規格，再進實作。
>
> **寫提案時的格式約定**（2026-07-27 補）：**還不存在的檔案不要寫成完整路徑。**
> 寫「在 `_config/` 下新增 tracks.yaml」，不要寫成一整條路徑。`lib/deadrefs.py`
> 認的是**路徑長相**，不是「有沒有在講一個檔案」——一個提案要造的檔案寫成路徑，
> 就會被判成斷鏈；而 selftest 一紅，`mutate.py` 整支拒跑（它要求乾淨的基線），
> 連帶**每個動到 `scripts/` 的 PR 都合不進去**。本文件原本有 11 處這樣寫，
> 整個變異安全網因此停擺了一天。這是「治標」的修法：判準沒有改，所以下一份提案
> 還是會撞到同一面牆——真正的解法（給 `docs/design/` 一條結構性判準）留給那一天。

---

## 0. 這份文件要回答的兩件事

1. **模組化**：讓未來「加一個新對象／新類型／新領域／插一個新處理步驟」都**改設定、不改碼**，
   或至少「改一個註冊點、不散彈式改多檔」。
2. **訂閱 → 電子報**：在 GitHub Pages（純靜態）上讓 user 訂閱，之後收到電子報，
   且**不破壞 runtime 0 LLM（紅線 #1）與隱私邊界（紅線 #6）**。

貫穿全文的一個判準：**GitHub Pages 不能存資料、不能寄信、不能跑後端。**
任何「訂閱」「寄信」的能力都必然引入 Pages 之外的東西——問題只在於引入多少、由誰持有名單。

---

## 1. 現況盤點（先講清楚你已經做對的部分）

你的架構其實已經有相當好的模組化底子，重構是「把既有的好習慣一致化」，不是打掉重練：

| 面向 | 現況 | 模組化程度 |
|---|---|---|
| 對象（實體） | `_config/entities.yaml` 命名實體字典，公司／產品／版本三層 | ✅ 已 config 化 |
| 來源 | `_config/sources.yaml` 三軌 + lifecycle 狀態機 | ✅ 已 config 化 |
| 來源**型別** | `pulse-probe.py` 有 `ADAPTERS = {"rss":…, "atom":…, "github_releases":…}` | ✅ **已是插件雛形** |
| 門檻 | `_config/gate.yaml`（改門檻不改碼） | ✅ 已 config 化 |
| 敘事 | `_config/narratives.yaml`（人為維護，獨立於抓取鏈） | ✅ 已 config 化 |
| stage 之間 | 各 stage 是獨立 script，透過 vault 檔案（Events/、_probe/）傳遞 | ✅ **鬆耦合（vault 當匯流排）** |
| 主線（track） | ❌ **`TRACKS` 在 `pulse-render.py:47` 與 `pulse-narrative-prep.py:28` 各寫死一份** | ⚠ 重複、會走鐘 |
| 輸出頁面 | ❌ `pulse-render.py` 的 `main()` 把 home/lines/timeline/signals/event 逐行寫死，無 registry | ⚠ 加頁要改 main |
| 領域身份 | ❌ 「AI Pulse」「六大領域趨勢」品牌字串、GitHub URL、中文文案散在 render 各處 | ⚠ 綁死 AI 這個領域 |

**一句話結論**：你缺的不是「模組化」，而是**兩三個還沒被 config 收編的軸**——
主線、輸出頁面、領域身份——把它們收編，四個軸就都通了。

---

## 2. 模組化設計：四個軸

設計原則（沿用你自己的紅線）：
- **設定即真相源**：能用 YAML 表達的就不寫進 `.py`。
- **單一註冊點**：同一種東西只在一個地方列舉（消滅 `TRACKS` 雙寫）。
- **契約優先**：每個 stage 的輸入／輸出是一份有 schema 的 artifact，換掉 stage 不影響其他 stage。
- **對自己誠實（紅線 #8）**：本節區分「現在就值得做（低成本高回報）」與「等真的需要再做（別過度工程）」。

### 軸 A — 新對象（entities）：**幾乎已完成，只補護欄**

現況加一個公司／產品＝在 `entities.yaml` 加一條，`probe` 的 `build_matcher()` 自動吃。
要補的只有三件低成本護欄：

1. **schema 驗證**：在 `scripts/lib/` 下加 config_schema.py，在 probe/render 啟動時驗
   `entities.yaml` 必填欄位（identifier / term / status）。目的是把「打錯字→靜默不命中」
   變成「啟動即報錯」。呼應你 sources.yaml 檔頭已經在擔心的「靜默丟棄是最危險的失敗模式」。
2. **分檔**：實體超過某量級後，`entities.yaml` → `entities/` 目錄按 track 或類型分檔，
   loader 合併。現在還不急（26KB 還讀得動），但 loader 先寫成「掃目錄合併」就不必回頭改。
3. **「怎麼加一個對象」寫成 `references/` 下的 adding-an-entity.md**：一頁 checklist，
   讓未來的你（或協作者）不必重讀程式碼。

> 判斷：軸 A 現在只做 (1) schema 驗證即可，(2)(3) 等實體破百再說。

### 軸 B — 新類型（types）：**三種「類型」要分開講**

「類型」在你的系統裡其實是三個不同的東西，模組化手法不同：

**B1. 新來源型別（source type）＝ 已有 registry，只要收編設定**

`probe` 已有 `ADAPTERS` dict。目前要加一個「HTML 選擇器抓取」或「JSON API」型別，
得改 `pulse-probe.py`。建議：
- `ADAPTERS` 保持在碼裡（adapter 是邏輯，本來就該是碼），但**讓 `sources.yaml` 的
  `type:` 欄位是唯一決定用哪個 adapter 的地方**（現在已接近如此，確認 registry 查找
  完全由 `type` 驅動、沒有 if-else 硬判）。
- 新增 adapter 的流程寫成 `references/` 下的 adding-a-source-adapter.md：
  「寫一個 `adapt_xxx(source, body) -> list[dict]` → 在 `ADAPTERS` 註冊 → sources.yaml 用 `type: xxx`」。

> 判斷：B1 幾乎免動，補一份 adapter 契約說明即可。

**B2. 新主線（track）＝ 現在最痛的雙寫，優先修**

`TRACKS` 寫死兩份（render 帶顏色、narrative-prep 帶 slug/name），加一條主線要改兩個檔、
還要記得顏色。建議：
- 在 `_config/` 下新增 **tracks.yaml** 作為主線的單一真相源：

  ```yaml
  # tracks.yaml（_config 下）— 主線（track）單一真相源。加/改/刪主線只動這裡。
  version: 1
  tracks:
    - slug: model-research
      name: 模型能力與研究
      color: "#9b8cff"
      order: 1
    - slug: infra-cost
      name: 基礎設施與成本
      color: "#f2bf62"
      order: 2
    # …
  ```
- `pulse-render.py` 與 `pulse-narrative-prep.py` 都改成 `load_tracks()` 讀這個檔，
  刪掉兩份寫死的 `TRACKS`。
- 連帶把 render 裡寫死的 **「六大領域趨勢」「SIX INDUSTRY TRENDS」** 改成
  由 `len(tracks)` 動態算（「六」不該是字面常數，否則加第七條主線文案就對不上）。

> 判斷：B2 是**這次模組化 CP 值最高的一刀**，且與訂閱無關、可獨立先做、風險低（純重構 + 既有測試護著）。

**B3. 新輸出頁面／輸出面（output surface）＝ 建 render 的 OUTPUTS registry**

`pulse-render.py` 的 `main()` 逐行寫死每個頁面。要加「feed.xml」「電子報 HTML」「新的分類頁」
都得改 main。建議把輸出抽象成一份可註冊的清單：

```python
# pulse-render.py（示意）
OUTPUTS = [
    Output("index.html",        build_home),
    Output("lines/index.html",  build_lines),
    Output("timeline/index.html", build_timeline),
    Output("signals/index.html", build_signals),
    Output("data/timeline.json", build_timeline_json),
    # 訂閱骨幹（軸見 §3）：
    Output("feed.xml",          build_atom_feed),
    Output("feed/<track>.xml",  build_track_feeds),   # 每條主線一支
    # email digest（§3）：
    Output("newsletter/latest.html", build_newsletter_html),
]
# 逐事件頁維持特例（它是 1→N），但也登記成一個 Output。
```

加一個輸出面＝寫一個 `build_xxx()` + 在 `OUTPUTS` 註冊一行。**feed 與電子報就掛在這個軸上**——
這是模組化與訂閱兩個需求的交會點。

> 判斷：B3 要做，因為訂閱直接依賴它；順手把現有頁面也收編進 registry。

### 軸 C — 新領域／垂直（domain / vertical）：**最大的一刀，但可延後**

目前引擎與「AI 這個領域」是綁死的：品牌名、track 名稱、中文文案、GitHub URL、口號
（「0 LLM 判斷 · 去 AI 口吻」）都寫死在 render。要讓同一套引擎去追「半導體」「生技」「某產業」，
需要把**領域身份**抽出來：

- 在 `_config/` 下新增 **profile.yaml**（領域檔頭）：

  ```yaml
  # profile.yaml（_config 下）— 這個 vault 追的是哪個領域。換領域＝換這個檔 + tracks/entities/sources。
  domain:
    id: ai
    brand: "AI Pulse"
    tagline: "看清 AI 產業的關鍵變化"
    badge: "0 LLM 判斷 · 去 AI 口吻"
    repo_url: "https://github.com/Vincenthsiehisme/ai-pulse"
    lang: zh-Hant
    site_url: "https://vincenthsiehisme.github.io/ai-pulse"   # feed / 電子報絕對連結需要
  ```
- render 所有領域字串改讀 `profile`。之後「複製一個追別的產業的 vault」＝
  換 `profile.yaml + tracks.yaml + entities.yaml + sources.yaml + narratives.yaml`，**碼一行不動**。
- 更進一步（真的要同時跑多領域再說）：把 `_config/` 變成 `domains/<id>/`，一個 repo 多領域。
  **現在不要做**——YOLO 多領域會把 health 監控、Pages 部署、feed 路由全部複雜化，違反紅線 #8。

> 判斷：軸 C 先做「抽出 `profile.yaml`」這一步（低成本、讓領域字串不再散落），
> 「一 repo 多領域」明確標為未來、非本次。

### 軸 D — pipeline 可插拔：**你已經有了，只差把契約寫下來**

好消息：你的 stage 之間**已經是插件式的**——它們不互相 import，而是透過 vault 檔案溝通
（probe 寫 `_probe/`、cluster 寫 `Events/`、render 讀 `Events/`）。vault 就是 message bus。
這是很乾淨的性質，要保護它，不要「為了模組化」反而把它們合成一個大程式。

要補的是**把每個 stage 的 artifact 契約寫下來**，這樣換掉／插入 stage 才安全：

- 在 `_config/` 下新增 **pipeline.yaml**（stage manifest，也是給 workflow 讀的單一清單）：

  ```yaml
  # pipeline.yaml（_config 下）— 夜間鏈的步驟與契約。加/換 stage 動這裡 + workflow 讀這裡。
  version: 1
  stages:
    - id: probe     ; cmd: scripts/pulse-probe.py     ; reads: [_config/sources.yaml]        ; writes: [_probe/<day>/]
    - id: score     ; cmd: scripts/pulse-score.py     ; reads: [_probe/<day>/]                ; writes: [_probe/<day>/scored.json]
    - id: cluster   ; cmd: scripts/pulse-cluster.py   ; reads: [_probe/<day>/scored.json, _config/entities.yaml] ; writes: [Events/]
    - id: gate      ; cmd: scripts/pulse-gate.py      ; reads: [Events/, _config/gate.yaml]   ; writes: [Events/, _dashboards/blocked.md]
    - id: dashboard ; cmd: scripts/pulse-dashboard.py ; reads: [Events/]                      ; writes: [_dashboards/]
    - id: render    ; cmd: scripts/pulse-render.py    ; reads: [Events/, _config/*]           ; writes: [dist/]
    # 未來插一步（例：翻譯、去重複核、email 遞送）＝在這裡加一行 + 補 reads/writes 契約
  ```
- `data-refresh.yml` 改成讀這份 manifest 跑（或至少讓 manifest 成為「真相」、workflow 對照）。
- 每個 stage 開頭補一段 docstring 明列 reads/writes（部分已有）。

> 判斷：軸 D 做「寫下 `pipeline.yaml` 契約」，**不要**寫一個花俏的 plugin driver 框架
> （那是過度工程；vault-as-bus 已經夠好）。

### 四軸小結

| 軸 | 動作 | 本次做? | 風險 | CP 值 |
|---|---|---|---|---|
| A 對象 | 加 schema 驗證 | 部分（只做驗證） | 低 | 中 |
| B2 主線 | `tracks.yaml` 消滅雙寫 | ✅ 是 | 低 | **高** |
| B1 來源型別 | 補 adapter 契約文件 | 文件即可 | 極低 | 中 |
| B3 輸出面 | render `OUTPUTS` registry | ✅ 是（訂閱依賴） | 中 | 高 |
| C 領域 | 抽 `profile.yaml` | ✅ 是（抽字串）；多領域延後 | 中 | 中 |
| D pipeline | 寫 `pipeline.yaml` 契約 | ✅ 是（輕量） | 低 | 中 |

---

## 3. 訂閱 → 電子報架構

### 3.1 核心設計：把「內容」與「遞送」分開

這是整個訂閱設計的樞紐，也直接呼應你 probe 的 `ADAPTERS` 哲學：

- **內容（content）**由你的**確定性 render 產生**——一支 `build_atom_feed()` /
  `build_newsletter_html()`，從 `Events/` 抽取、拼模板，**0 LLM、可離線、可審計**（守住紅線 #1）。
  這是**單一真相源**。
- **遞送（delivery）**是一個**可替換的 adapter**——今天用 Buttondown、明天換成自寄，
  **完全不動內容產生的那一段**。

於是「自管(3) vs 託管(2)」不再是二選一的世界觀之爭，而是**同一個 feed 底下換一個遞送 adapter**。
這正是解你「3 or 2 拿不定」的關鍵：**先接 2，內容仍是你自己的 feed（沒被綁架），
未來要 3 只換遞送端。**

```
Events/ ──(確定性 render, 0 LLM)──►  feed.xml（Atom）   ← 單一真相源、你 100% 持有
                                        │
              ┌─────────────────────────┼──────────────────────────┐
              ▼                         ▼                          ▼
     RSS 閱讀器直接訂閱        遞送 adapter：託管(2)          遞送 adapter：自管(3)
     （零後端、零成本、        Buttondown「RSS→email」        GitHub Action 讀 feed →
      100% 守紅線）            自動把新項目寄給名單            用 Resend/SES 寄給自管名單
```

### 3.2 Phase A（骨幹，最先做，100% 守紅線）：確定性 feed + 頁面訂閱入口

**這一步不引入任何寄信服務、不存任何 email，就已經是一個可用的「訂閱」。**

- render 新增 `build_atom_feed()`（掛在軸 B3 的 `OUTPUTS`）→ 產 `dist/feed.xml`
  （全站）與 `dist/feed/<track>.xml`（每條主線一支，讓人只訂閱關心的線）。
- feed 內容＝既有的抽取式摘要（事實層 + canonical 連結），**與網頁同源、同樣 0 LLM**。
- 頁面加一個「訂閱」區塊：先放 RSS 連結 + 「用 email 訂閱」的入口（Phase B 接上）。
- feed 需要**絕對 URL**，所以 §2 軸 C 的 `profile.yaml` 要先有 `site_url`。

Phase A 產出：一個真的能訂閱（RSS）、零成本、零外部依賴、零隱私風險的東西。**即使你之後
決定 email 太麻煩不做了，Phase A 也已經交付價值。**

### 3.3 Phase B（email 遞送）：靜態頁面怎麼收到 email？

GitHub Pages 是靜態的，`<form>` 一定要 POST 到 Pages 以外的某個 endpoint。這是無法繞過的物理限制。
兩條路：

#### 路線 2（託管）— 建議先走這條

用 **Buttondown**（或 Substack / Mailchimp）：
- 頁面嵌它的訂閱表單 → **它幫你存名單、做 double opt-in、退訂、GDPR、寄信**。
- 開「**RSS-to-email**」：把它指到你 Phase A 的 `feed.xml`，有新項目就自動寄。
- **你的內容仍是你自己的 feed**（確定性、在 repo 裡），Buttondown 只是遞送管。

| | 說明 |
|---|---|
| 成本 | 免費額度（Buttondown 100 訂閱免費；Substack 免費） |
| 名單持有 | ⚠ 廠商持有（但可匯出；且你不依賴它產內容，隨時可搬） |
| 隱私紅線 #6 | ✅ email 不進你的 repo，落在廠商合規邊界內 |
| 上線速度 | **最快**（嵌一段表單 + 設 RSS 來源） |
| 鎖定風險 | 低——因為內容是你的 feed，換遞送商不需重做內容 |

#### 路線 3（自管）— 值得，但等名單真的重要再升級

- **擷取（capture）**：靜態頁不能存資料，需要一個免費 serverless 收表單——建議
  **Cloudflare Worker（免費額度大）**。Worker 收 email → 觸發 double opt-in → 存進名單。
- **名單儲存 ＋ 隱私（關鍵）**：**絕對不要把 email 明碼存進這個公開 repo**——那會直接違反
  紅線 #6（vault 只放 allowlist frontmatter，PII 永不進 vault），且公開 repo 的 email
  會被爬蟲收割去寄垃圾信。合規存法擇一：
  - Cloudflare **KV / D1**（免費，名單在你帳號、不在公開 repo）— **建議**；
  - 或一個**獨立的 private repo / private gist** 專存名單；
  - 明碼 email 一律不進 `Vincenthsiehisme/ai-pulse` 這個 repo。
- **寄送（send）**：夜間 `data-refresh` 跑完 render 後，一個 Action step 讀名單 + 讀
  `newsletter/latest.html` → 用 **Resend（免費約 3k 封/月）/ Amazon SES / MailerSend** 寄出。
  API key 放 GitHub Actions secret。
- **合規義務**（無論自管都要有）：double opt-in、每封含退訂連結、`List-Unsubscribe` header、
  寄件人身分與實體地址（CAN-SPAM / GDPR）。

| | 說明 |
|---|---|
| 成本 | 免費額度內（Cloudflare + Resend/SES 免費層） |
| 名單持有 | ✅ 你 100% 持有 |
| 隱私紅線 #6 | ⚠ **要你自己守**：名單必須放 repo 外的私有儲存，且做 opt-in/退訂 |
| 上線速度 | 慢（多了 Worker + 名單儲存 + 寄信 + 合規四塊） |
| 鎖定風險 | 無 |

#### 建議路徑（解你的「3 or 2」）

**先 2、後 3、內容永遠是你自己的 feed。**
理由：email 這件事真正的護城河不是「誰按下寄信鈕」，而是「內容產生是否可控」。
只要 §3.1 把內容（你的確定性 feed）和遞送分乾淨，先用 Buttondown 遞送能讓你**幾天內就有真的
email 電子報**，且**零鎖定**——哪天訂閱數大到你想自己掌握名單，再把遞送 adapter 換成
路線 3，內容那一段一行不改。反過來先硬幹路線 3，會在還沒有半個訂閱者時就先背上
serverless + 名單合規 + 寄信信譽（SPF/DKIM/DMARC）的維運債，違反你紅線 #8「別把預留當已實現」。

### 3.4 電子報沿用 enrich 三明治：判斷 0 LLM，prose 可 Cowork（精準版紅線 #1）

> 更正：本節初稿寫「電子報一律抽取式、不呼叫任何模型」，這與 repo 現有的 narrative / enrich
> 機制不一致、把紅線 #1 講得比程式碼更絕。正確的界線是——**AI 只准碰語氣，永遠碰不到判斷。**

電子報要拆成「判斷」與「敘述」兩層，各自守不同強度的規則：

- **判斷層（硬 0 LLM）**：這期收哪些事件、每則的事實／熱度／獨立來源數、排序、發哪一版——
  全部由確定性 render 從 `Events/` 算出來。**自動夜間寄送那一步也 0 LLM。** 這層 AI 不准碰。
- **敘述層（可 Cowork，但夾三明治）**：電子報的導言／每則短評 prose，**可以**沿用你已經在跑的
  enrich 三明治，不必逼成機器腔：
  1. 確定性 `newsletter-prep`：用規則挑出「這期要寫 prose 的段落」（不由 LLM 決定收哪些事件）。
  2. Cowork 依 `speak-human-tw`、**只根據綁定證據**寫 prose（不編造、不改選件與數據）。
  3. 確定性 `voice_clean` + `newsletter-apply` 機械清理、寫回一份**洗好的 artifact**，不新增語意。
  4. 夜間自動寄送只讀這份洗好的 artifact——**寄送鏈本身仍 0 LLM**，潤稿在鏈外另跑。

一句話：電子報**不是**「請 AI 幫我寫這期摘要」（那會讓 AI 碰到選件與判斷），而是
「判斷全確定性，prose 走與 narrative 同一套受審計的潤稿三明治」。這樣品質是人話、機制仍守紅線。

---

## 4. 分階段實作計畫（docs-first、可獨立回滾）

每個 phase 都是一個可獨立 merge 的 PR，附驗證與回滾。順序照「風險低→高、依賴先後」排。

| Phase | 內容 | 動作 | 驗證 | 回滾 |
|---|---|---|---|---|
| **0. docs-first** | 本文件轉正 | 把 §2/§3 決議拆進 `references/` 與各 yaml 檔頭 | 人為 review 本文件 | 刪 docs |
| **1. tracks.yaml（軸 B2）** | 消滅 `TRACKS` 雙寫 | 在 `_config/` 下建 tracks.yaml；render/narrative-prep 改讀；「六大」動態化 | render 產出與現況 diff 為 0（純重構）；跑 `selftest.py` | 還原兩份 `TRACKS` |
| **2. profile.yaml（軸 C）** | 抽領域字串 | 在 `_config/` 下建 profile.yaml；render 領域字串改讀 | 產出 diff 僅品牌字串來源改變、內容不變 | 還原字面字串 |
| **3. OUTPUTS registry（軸 B3）** | render 輸出可註冊 | main() 改 `OUTPUTS` 清單 | 既有頁面位元組不變（reference 比對） | 還原 main() |
| **4. feed.xml（Phase A）** | 確定性 Atom feed | `build_atom_feed()` + 每 track feed；頁面加訂閱區 | feed 過 W3C Feed Validator；連結可解析 | 移除 Output 一行 |
| **5. schema 驗證（軸 A）** | config 啟動即驗 | `lib/config_schema.py`；probe/render 啟動呼叫 | 故意打錯 entities.yaml → 應啟動即報錯 | 停用驗證呼叫 |
| **6. pipeline.yaml（軸 D）** | stage 契約 | 建 manifest；workflow 對照 | 夜間鏈跑完與現況一致 | 忽略 manifest |
| **7. email 遞送（Phase B）** | 電子報 | `build_newsletter_html()` + 選 2 或 3 接遞送 | 寄測試信給自己；退訂可用；double opt-in 生效 | 關掉遞送 step；feed 仍在 |

**關鍵解耦**：Phase 1–6 全部**與 email 無關**，即使你電子報方案還沒最後拍板，這些模組化都能先做完、先交付。
Email 的路線 2/3 抉擇只影響 Phase 7。

---

## 5. 明確不做（守紅線 #8，避免過度工程）

- ❌ 一個 repo 同時跑多領域（`domains/<id>/`）——等真的要追第二個產業再說。
- ❌ 花俏的 pipeline plugin driver 框架——vault-as-bus 已經夠好，`pipeline.yaml` 契約足矣。
- ❌ 讓 AI 碰電子報的**判斷**（選件／熱度／發哪版）或把 LLM 放進**夜間寄送鏈**——違反紅線 #1。
  （電子報的 **prose 可以** Cowork 寫，但要走 §3.4 的 enrich 三明治、且在寄送鏈外。）
- ❌ 訂閱者 email 明碼進公開 repo——直接違反紅線 #6。
- ❌ 在還沒有訂閱者時先自建整套寄信基礎設施（路線 3 的完整版）——先租遞送（路線 2）。

---

## 6. 待你拍板的決策點

1. **模組化四軸的實作範圍**：是否照 §4 的 Phase 1–6 全做，或先只做 CP 值最高的
   Phase 1（tracks.yaml）+ Phase 4（feed.xml）？
2. **電子報遞送**：接受「先 2（Buttondown RSS-to-email）、內容用自己的 feed、未來可換 3」
   這個建議路徑嗎？還是你有偏好的服務商（Substack / Mailchimp / 自架 listmonk…）？
3. **領域字串**：`profile.yaml` 的 `site_url` / 品牌 / 口號要用什麼值（feed 需要絕對 URL）。

拍板後，我可以在一個新分支上按 Phase 逐一實作、逐一給你看 diff。
