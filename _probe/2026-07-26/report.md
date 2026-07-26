# probe report 2026-07-26

M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。

> ⚠ 本輪含 65 筆 backfill（首次抓取的既有存量）。
> backfill 不代表當期訊號，lead_days 與熱度統計應排除。

## 兩個決定性比率

| track | 條目 | 5a author 有值 | 5b 可解析自然人 | 實體命中率 |
|---|---|---|---|---|
| aggregator | 30 | 30/30 = 100% | 0/30 = 0% | 4/30 = 13% |
| kol | 90 | 70/90 = 78% | 60/90 = 67% | 34/90 = 38% |
| media | 67 | 67/67 = 100% | 59/67 = 88% | 28/67 = 42% |
| official | 218 | 48/218 = 22% | 18/218 = 8% | 159/218 = 73% |

- **5a（author 有值）只用來偵測 adapter 解析失敗**，不作任何人物層判斷。M1 實測 120/120 有值卻幾乎不可用，這個數字單獨看會騙人。
- **5b（可解析自然人）才決定人物層與獨立性升級有沒有用。**官方線若過低，people.yaml 只在 KOL 線生效。
- **實體命中率**決定字典往哪長。低命中不代表字典爛，可能是語料型態與假設不符。

### author 分類分佈（5b 的組成）

| kind | 筆數 | 計入 5b |
|---|---|---|
| none | 190 |  |
| person | 124 | ✓ |
| handle | 67 |  |
| multi_person | 13 | ✓ |
| org | 11 |  |

分類全為字面規則，無推論。判不出來一律 unknown 且不計入 5b（保守預設）。
`multi_person` 是共同作者串，本專案判定為可解析到自然人；
若要嚴格採「單一自然人」，把它移出 PERSON_KINDS 即可。

### 分類抽樣（供人工校準規則）

| author 原值 | 判定 | 來源 |
|---|---|---|
| khluu | handle | src-gh-vllm-releases |
| NVIDIA Writers | org | src-nvidia-blog |
| David Niewolny | person | src-nvidia-blog |
| Son Ho, Cédric Fournet, Antoine Delignat-Lavaud, Samuel Lee, | multi_person | src-msr-blog |
| Jianfeng Gao | person | src-msr-blog |
| michael.nunez@venturebeat.com (Michael Nuñez) | handle | src-media-venturebeat |
| Alex Music | person | src-media-ieee-spectrum |
| Jessica Hamzelou | person | src-media-mit-techreview |
| Christine McGuiness and Devang Khariwala | multi_person | src-media-mit-techreview |
| Kyle Orland | person | src-media-arstechnica |
| Molly Taft, wired.com | multi_person | src-media-arstechnica |
| WIRED | org | src-media-arstechnica |
| David Pierce | person | src-media-theverge |
| karpathy (hidden) | handle | src-kol-karpathy |
| Nathan Lambert | person | src-kol-interconnects |
| Ethan Mollick | person | src-kol-oneusefulthing |
| Sebastian Raschka, PhD | person | src-kol-raschka |
| mellosouls | handle | src-hn-frontpage |

## 命中的實體型別分佈

- company: 122
- product_line: 93
- product: 28
- technology: 26
- framework: 18
- infrastructure: 10

## 字典補漏候選（未命中且跨來源出現）

晉升門檻：跨 ≥2 來源、≥3 次。只列達標者，避免一次性雜訊灌進字典。

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 11 | 4 |
| LLM | 8 | 6 |
| U.S | 5 | 2 |
| Learn | 5 | 2 |
| San Francisco | 5 | 4 |
| AI-native | 4 | 2 |
| Pro | 4 | 3 |
| Gemma | 4 | 3 |
| Python | 4 | 2 |
| Understanding | 4 | 2 |
| There | 4 | 3 |
| Fable | 4 | 2 |
| Some | 4 | 4 |
| One | 4 | 3 |
| Frontier | 3 | 2 |
| AI-powered | 3 | 3 |
| Building | 3 | 3 |
| Flash | 3 | 2 |
| Plus | 3 | 3 |
| Power | 3 | 3 |
| NASA | 3 | 2 |
| With | 3 | 3 |
| These | 3 | 2 |
| January | 3 | 2 |
| July | 3 | 3 |
| China | 3 | 2 |
| Trump | 3 | 2 |
| Opus | 3 | 3 |

### 單來源高頻（觀察用，不列入晉升）

目前活躍來源 19 條。來源數少時「跨 ≥2 來源」門檻結構上難以成立，
上表為空不代表收割機制壞掉。此區僅供觀察，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Highlights | 14 | src-gh-vllm-releases |
| Co-Scientist | 5 | src-deepmind-blog |
| Release Notes | 4 | src-gh-vllm-releases |
| The Download | 4 | src-media-mit-techreview |
| Fix | 3 | src-gh-vllm-releases |
| Open | 3 | src-kol-interconnects |
| LLM Research Papers | 3 | src-kol-raschka |
| List | 3 | src-kol-raschka |

## 來源狀態

| source | track | status | items | new | backfill | robots | error |
|---|---|---|---|---|---|---|---|
| src-arxiv-cs-cl | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ec-digital-strategy | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-consilium-press | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ep-itre | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-kol-importai | kol | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-openai-blog | official | 200 | 50 | 0 |  | True |  |
| src-anthropic-news | official | 200 | 40 | 0 |  | True |  |
| src-gh-vllm-releases | official | 200 | 20 | 0 |  | None |  |
| src-deepmind-blog | official | 200 | 30 | 0 |  | True |  |
| src-hf-blog | official | 304 | 0 | 0 |  | True |  |
| src-nvidia-blog | official | 200 | 18 | 0 |  | True |  |
| src-msr-blog | official | 200 | 10 | 0 |  | True |  |
| src-meta-research | official | 200 | 10 | 0 |  | True |  |
| src-xai-news | official | 200 | 40 | 0 |  | True |  |
| src-mistral-news | official | 200 | 0 | 0 |  | True |  |
| src-qwen-blog | official | 304 | 0 | 0 |  | True |  |
| src-amd-ir | official | robots_unknown | 0 | 0 |  | None | robots.txt 取不到，保守跳過 |
| src-media-venturebeat | media | 200 | 7 | 0 |  | True |  |
| src-media-techcrunch | media | 304 | 0 | 0 |  | True |  |
| src-media-ieee-spectrum | media | 200 | 20 | 1 |  | True |  |
| src-media-mit-techreview | media | 200 | 10 | 0 |  | True |  |
| src-media-theregister | media | robots_disallow | 0 | 0 |  | False |  |
| src-media-arstechnica | media | 200 | 20 | 0 |  | True |  |
| src-media-theverge | media | 200 | 10 | 1 |  | True |  |
| src-kol-karpathy | kol | 200 | 10 | 0 |  | True |  |
| src-kol-simonwillison | kol | 200 | 20 | 0 |  | True |  |
| src-kol-interconnects | kol | 200 | 20 | 0 |  | True |  |
| src-kol-thezvi | kol | robots_unknown | 0 | 0 |  | False | robots.txt 回 401/403，取不到內容，保守跳過（非站方拒絕） |
| src-kol-oneusefulthing | kol | 200 | 20 | 0 |  | True |  |
| src-kol-lilianweng | kol | 304 | 0 | 0 |  | True |  |
| src-kol-raschka | kol | 200 | 20 | 0 |  | True |  |
| src-hn-frontpage | aggregator | 200 | 30 | 8 |  | True |  |

`skipped_lifecycle` = 未被請求，error 欄顯示其 lifecycle 值。
`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕（含 401/403：拿不到檔案，多半是 WAF 擋雲端 IP）。
`robots_disallow` = robots.txt 取得成功且明文 Disallow —— 只有這個才是站方政策，也只有這個可以拿來降級。


## 本輪已知缺口（勿當成已實現）

- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來
- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能
- `seen.json` 無保留策略，會單調成長；`_corpus` 全量進版控的問題同理未解
- backfill 以「該來源首次抓取」判定，首跑當天發布的新文章會被誤標為存量
- author 分類是字面規則，可能誤判；請對照上面的分類抽樣校準
