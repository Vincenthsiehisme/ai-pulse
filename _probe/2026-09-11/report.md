# probe report 2026-09-11

M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。

## 兩個決定性比率

| track | 條目 | 5a author 有值 | 5b 可解析自然人 | 實體命中率 |
|---|---|---|---|---|
| aggregator | 30 | 30/30 = 100% | 0/30 = 0% | 4/30 = 13% |
| kol | 90 | 70/90 = 78% | 60/90 = 67% | 38/90 = 42% |
| media | 79 | 79/79 = 100% | 76/79 = 96% | 38/79 = 48% |
| official | 218 | 48/218 = 22% | 20/218 = 9% | 161/218 = 74% |

- **5a（author 有值）只用來偵測 adapter 解析失敗**，不作任何人物層判斷。M1 實測 120/120 有值卻幾乎不可用，這個數字單獨看會騙人。
- **5b（可解析自然人）才決定人物層與獨立性升級有沒有用。**官方線若過低，people.yaml 只在 KOL 線生效。
- **實體命中率**決定字典往哪長。低命中不代表字典爛，可能是語料型態與假設不符。

### author 分類分佈（5b 的組成）

| kind | 筆數 | 計入 5b |
|---|---|---|
| none | 190 |  |
| person | 141 | ✓ |
| handle | 65 |  |
| multi_person | 15 | ✓ |
| org | 6 |  |

分類全為字面規則，無推論。判不出來一律 unknown 且不計入 5b（保守預設）。
`multi_person` 是共同作者串，本專案判定為可解析到自然人；
若要嚴格採「單一自然人」，把它移出 PERSON_KINDS 即可。

### 分類抽樣（供人工校準規則）

| author 原值 | 判定 | 來源 |
|---|---|---|
| khluu | handle | src-gh-vllm-releases |
| Sasa Docca | person | src-nvidia-blog |
| GeForce NOW Community | org | src-nvidia-blog |
| 黄仁勋 | handle | src-nvidia-blog |
| Naoto Usuyama, Jeya Maria Jose Valanarasu, Tristan Naumann | multi_person | src-msr-blog |
| Theresa Loconsolo, Anthony Ha, Sean O'Kane, Kirsten Korosec | multi_person | src-media-techcrunch |
| Kirsten Korosec | person | src-media-techcrunch |
| Matthew S. Smith | person | src-media-ieee-spectrum |
| Ollobot | handle | src-media-ieee-spectrum |
| Thomas Macaulay | person | src-media-mit-techreview |
| Zehra Munir, Financial Times | multi_person | src-media-arstechnica |
| Ashley Belanger | person | src-media-arstechnica |
| Jay Peters | person | src-media-theverge |
| karpathy (hidden) | handle | src-kol-karpathy |
| Nathan Lambert | person | src-kol-interconnects |
| Ethan Mollick | person | src-kol-oneusefulthing |
| Sebastian Raschka, PhD | person | src-kol-raschka |
| player85 | handle | src-hn-frontpage |

## 命中的實體型別分佈

- company: 134
- product_line: 89
- product: 30
- technology: 22
- framework: 18
- infrastructure: 6

## 字典補漏候選（未命中且跨來源出現）

晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`）。只列達標者，避免一次性雜訊灌進字典。

**這一區只算本輪。** 跨天累積的那份在 `_dashboards/dictionary-gaps.md`。

| 候選 | 次數 | 來源數 |
|---|---|---|
| Flash | 6 | 2 |
| Python | 5 | 3 |
| Astra | 5 | 2 |
| LLMs | 5 | 3 |
| Apple | 5 | 2 |
| U.S | 4 | 2 |
| Every | 4 | 3 |
| Pro | 4 | 3 |
| Some | 4 | 4 |
| LLM | 4 | 3 |
| API | 3 | 2 |
| Critical | 3 | 2 |
| Building | 3 | 3 |
| Gemma | 3 | 2 |
| Frontier | 3 | 3 |
| CEO | 3 | 2 |
| Two | 3 | 3 |
| July | 3 | 2 |
| When | 3 | 3 |
| They | 3 | 2 |

### 單來源高頻（觀察用，不列入晉升）

目前活躍來源 19 條。來源數少時「跨 ≥2 來源」門檻結構上難以成立，
上表為空不代表收割機制壞掉。此區僅供觀察，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Highlights | 14 | src-gh-vllm-releases |
| Release Notes | 5 | src-gh-vllm-releases |
| GeForce NOW | 4 | src-nvidia-blog |
| Show HN | 4 | src-hn-frontpage |
| Fix | 3 | src-gh-vllm-releases |
| Flash Cyber | 3 | src-deepmind-blog |
| The Download | 3 | src-media-mit-techreview |
| MIT Technology Review | 3 | src-media-mit-techreview |
| Their | 3 | src-media-mit-techreview |
| Tool | 3 | src-kol-simonwillison |
| Latest | 3 | src-kol-interconnects |

## 來源狀態

| source | track | status | items | new | backfill | robots | error |
|---|---|---|---|---|---|---|---|
| src-arxiv-cs-cl | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ec-digital-strategy | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-consilium-press | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ep-itre | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-kol-importai | kol | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-openai-blog | official | 200 | 50 | 2 |  | True |  |
| src-anthropic-news | official | 200 | 40 | 12 |  | True |  |
| src-gh-vllm-releases | official | 200 | 20 | 0 |  | None |  |
| src-gh-openai-codex | official | error | 0 | 0 |  | None | ValueError: upstream: body too large |
| src-deepmind-blog | official | 200 | 30 | 0 |  | True |  |
| src-hf-blog | official | 304 | 0 | 0 |  | True |  |
| src-nvidia-blog | official | 200 | 18 | 0 |  | True |  |
| src-msr-blog | official | 200 | 10 | 0 |  | True |  |
| src-meta-research | official | 200 | 10 | 0 |  | True |  |
| src-xai-news | official | 200 | 40 | 0 |  | True |  |
| src-mistral-news | official | 200 | 0 | 0 |  | True |  |
| src-qwen-blog | official | 304 | 0 | 0 |  | True |  |
| src-amd-ir | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-venturebeat | media | 429 | 0 | 0 |  | True |  |
| src-media-techcrunch | media | 200 | 19 | 7 |  | True |  |
| src-media-ieee-spectrum | media | 200 | 20 | 0 |  | True |  |
| src-media-mit-techreview | media | 200 | 10 | 2 |  | True |  |
| src-media-theregister | media | robots_disallow | 0 | 0 |  | False |  |
| src-media-arstechnica | media | 200 | 20 | 1 |  | True |  |
| src-media-theverge | media | 200 | 10 | 10 |  | True |  |
| src-kol-karpathy | kol | 200 | 10 | 0 |  | True |  |
| src-kol-simonwillison | kol | 200 | 20 | 7 |  | True |  |
| src-kol-interconnects | kol | 200 | 20 | 1 |  | True |  |
| src-kol-thezvi | kol | robots_unknown | 0 | 0 |  | False | robots.txt 回 401/403，取不到內容，保守跳過（非站方拒絕） |
| src-kol-oneusefulthing | kol | 200 | 20 | 0 |  | True |  |
| src-kol-lilianweng | kol | 304 | 0 | 0 |  | True |  |
| src-kol-raschka | kol | 200 | 20 | 0 |  | True |  |
| src-hn-frontpage | aggregator | 200 | 30 | 30 |  | True |  |

`skipped_lifecycle` = 未被請求，error 欄顯示其 lifecycle 值。
`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕（含 401/403：拿不到檔案，多半是 WAF 擋雲端 IP）。
`robots_disallow` = robots.txt 取得成功且明文 Disallow —— 只有這個才是站方政策，也只有這個可以拿來降級。


## 零產出診斷（status 200 但 0 筆）

一條「200 / 0 筆」有兩種完全不同的成因：**站方那邊沒有東西**，或**我們這邊接不上**。兩者在來源狀態表上印起來一模一樣，於是零產出的
來源只能靠人翻語料去猜。這張表把它們分開；判準是
`pulse-probe.zero_yield_reason()`，規格見 `references/health-alarms.md`〈零產出不是沉默〉。

| source | 判定 | 是誰那邊 | 說明 |
|---|---|---|---|
| src-mistral-news | `hints_matched_nothing` | 我們 | index 有 1 張子 sitemap，hints ['news', 'blog'] 一張都沒命中——**是我們的設定對不上，不是站上沒東西**；候選：https://mistral.ai/sitemap-0.xml |

### 中途數字（過濾前後各剩幾條）

- `src-mistral-news`：kind=sitemapindex；index 1 張、hints ['news', 'blog'] 命中 0 張（上限 3）、展開 0 張、抓成功 0 張；index 候選 https://mistral.ai/sitemap-0.xml；過濾前 0 條 URL、url_prefix `/news/`、過濾後 0 條

樣本只印過濾**前**的前三條 URL——過濾後的樣本回答不了「為什麼被濾掉」。
只有連結，不抓內文（紅線 7 的合規邊界沒有變）。


## 本輪已知缺口（勿當成已實現）

- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來
- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能
- `seen.json` 無保留策略，會單調成長；`_corpus` 全量進版控的問題同理未解
- backfill 以「該來源首次抓取」判定，首跑當天發布的新文章會被誤標為存量
- author 分類是字面規則，可能誤判；請對照上面的分類抽樣校準
