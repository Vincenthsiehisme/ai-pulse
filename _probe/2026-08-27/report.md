# probe report 2026-08-27

M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。

## 兩個決定性比率

| track | 條目 | 5a author 有值 | 5b 可解析自然人 | 實體命中率 |
|---|---|---|---|---|
| official | 10 | 10/10 = 100% | 10/10 = 100% | 5/10 = 50% |

- **5a（author 有值）只用來偵測 adapter 解析失敗**，不作任何人物層判斷。M1 實測 120/120 有值卻幾乎不可用，這個數字單獨看會騙人。
- **5b（可解析自然人）才決定人物層與獨立性升級有沒有用。**官方線若過低，people.yaml 只在 KOL 線生效。
- **實體命中率**決定字典往哪長。低命中不代表字典爛，可能是語料型態與假設不符。

### author 分類分佈（5b 的組成）

| kind | 筆數 | 計入 5b |
|---|---|---|
| multi_person | 10 | ✓ |

分類全為字面規則，無推論。判不出來一律 unknown 且不計入 5b（保守預設）。
`multi_person` 是共同作者串，本專案判定為可解析到自然人；
若要嚴格採「單一自然人」，把它移出 PERSON_KINDS 即可。

### 分類抽樣（供人工校準規則）

| author 原值 | 判定 | 來源 |
|---|---|---|
| Sebastian Ehlert, Stefano Battaglia, Thijs Vogels, Jan Herma | multi_person | src-msr-blog |

## 命中的實體型別分佈

- company: 3
- framework: 1
- technology: 1

## 字典補漏候選（未命中且跨來源出現）

晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`）。只列達標者，避免一次性雜訊灌進字典。

**這一區只算本輪。** 跨天累積的那份在 `_dashboards/dictionary-gaps.md`。

| 候選 | 次數 | 來源數 |
|---|---|---|
| （本輪無達標候選） | | |

### 單來源高頻（觀察用，不列入晉升）

目前活躍來源 1 條。來源數少時「跨 ≥2 來源」門檻結構上難以成立，
上表為空不代表收割機制壞掉。此區僅供觀察，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| （無） | | |

## 來源狀態

| source | track | status | items | new | backfill | robots | error |
|---|---|---|---|---|---|---|---|
| src-arxiv-cs-cl | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ec-digital-strategy | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-consilium-press | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ep-itre | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-kol-importai | kol | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-openai-blog | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-anthropic-news | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-gh-vllm-releases | official | 403 | 0 | 0 |  | None | http 403（adapter 自己抓的） |
| src-gh-openai-codex | official | 403 | 0 | 0 | ✓ | None | http 403（adapter 自己抓的） |
| src-deepmind-blog | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-hf-blog | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-nvidia-blog | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-msr-blog | official | 200 | 10 | 0 |  | True |  |
| src-meta-research | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-xai-news | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-mistral-news | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-qwen-blog | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-amd-ir | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-venturebeat | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-techcrunch | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-ieee-spectrum | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-mit-techreview | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-theregister | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-arstechnica | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-theverge | media | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-karpathy | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-simonwillison | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-interconnects | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-thezvi | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-oneusefulthing | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-lilianweng | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-kol-raschka | kol | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-hn-frontpage | aggregator | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |

`skipped_lifecycle` = 未被請求，error 欄顯示其 lifecycle 值。
`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕（含 401/403：拿不到檔案，多半是 WAF 擋雲端 IP）。
`robots_disallow` = robots.txt 取得成功且明文 Disallow —— 只有這個才是站方政策，也只有這個可以拿來降級。


## 零產出診斷（status 200 但 0 筆）

一條「200 / 0 筆」有兩種完全不同的成因：**站方那邊沒有東西**，或**我們這邊接不上**。兩者在來源狀態表上印起來一模一樣，於是零產出的
來源只能靠人翻語料去猜。這張表把它們分開；判準是
`pulse-probe.zero_yield_reason()`，規格見 `references/health-alarms.md`〈零產出不是沉默〉。

（本輪沒有 status 200 而 0 筆的來源。）


## 本輪已知缺口（勿當成已實現）

- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來
- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能
- `seen.json` 無保留策略，會單調成長；`_corpus` 全量進版控的問題同理未解
- backfill 以「該來源首次抓取」判定，首跑當天發布的新文章會被誤標為存量
- author 分類是字面規則，可能誤判；請對照上面的分類抽樣校準
