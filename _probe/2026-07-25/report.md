# probe report 2026-07-25

M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。

> ⚠ 本輪含 300 筆 backfill（首次抓取的既有存量）。
> backfill 不代表當期訊號，lead_days 與熱度統計應排除。

## 兩個決定性比率

| track | 條目 | 5a author 有值 | 5b 可解析自然人 | 實體命中率 |
|---|---|---|---|---|
| aggregator | 30 | 30/30 = 100% | 0/30 = 0% | 4/30 = 13% |
| kol | 110 | 70/110 = 64% | 60/110 = 55% | 40/110 = 36% |
| official | 248 | 48/248 = 19% | 27/248 = 11% | 188/248 = 76% |

- **5a（author 有值）只用來偵測 adapter 解析失敗**，不作任何人物層判斷。M1 實測 120/120 有值卻幾乎不可用，這個數字單獨看會騙人。
- **5b（可解析自然人）才決定人物層與獨立性升級有沒有用。**官方線若過低，people.yaml 只在 KOL 線生效。
- **實體命中率**決定字典往哪長。低命中不代表字典爛，可能是語料型態與假設不符。

### author 分類分佈（5b 的組成）

| kind | 筆數 | 計入 5b |
|---|---|---|
| none | 240 |  |
| person | 58 | ✓ |
| handle | 51 |  |
| multi_person | 29 | ✓ |
| unknown | 10 |  |

分類全為字面規則，無推論。判不出來一律 unknown 且不計入 5b（保守預設）。
`multi_person` 是共同作者串，本專案判定為可解析到自然人；
若要嚴格採「單一自然人」，把它移出 PERSON_KINDS 即可。

### 分類抽樣（供人工校準規則）

| author 原值 | 判定 | 來源 |
|---|---|---|
| khluu | handle | src-gh-vllm-releases |
| NVIDIA Writers | person | src-nvidia-blog |
| NVIDIA | handle | src-nvidia-blog |
| Son Ho, Cédric Fournet, Antoine Delignat-Lavaud, Samuel Lee, | multi_person | src-msr-blog |
| Jianfeng Gao | person | src-msr-blog |
| karpathy (hidden) | unknown | src-kol-karpathy |
| Nathan Lambert | person | src-kol-interconnects |
| Ethan Mollick | person | src-kol-oneusefulthing |
| Sebastian Raschka, PhD | multi_person | src-kol-raschka |
| alvis | handle | src-hn-frontpage |

## 命中的實體型別分佈

- company: 126
- product_line: 99
- technology: 29
- product: 24
- framework: 17
- infrastructure: 8

## 字典補漏候選（未命中且跨來源出現）

晉升門檻：跨 ≥2 來源、≥3 次。只列達標者，避免一次性雜訊灌進字典。

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 12 | 5 |
| LLM | 7 | 4 |
| Here | 6 | 3 |
| U.S | 5 | 2 |
| Learn | 5 | 2 |
| Understanding | 5 | 3 |
| Learning | 5 | 3 |
| Building | 4 | 4 |
| Gemma | 4 | 3 |
| Python | 4 | 2 |
| Updated | 4 | 2 |
| Built | 4 | 2 |
| Power | 4 | 4 |
| Frontier | 3 | 2 |
| AI-powered | 3 | 3 |
| Pro | 3 | 2 |
| Plus | 3 | 3 |
| Extending | 3 | 2 |
| They | 3 | 3 |
| However | 3 | 2 |
| January | 3 | 2 |
| Chinese | 3 | 2 |

### 單來源高頻（觀察用，不列入晉升）

目前活躍來源 16 條。來源數少時「跨 ≥2 來源」門檻結構上難以成立，
上表為空不代表收割機制壞掉。此區僅供觀察，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Highlights | 13 | src-gh-vllm-releases |
| Qwen | 8 | src-qwen-blog |
| Co-Scientist | 5 | src-deepmind-blog |
| AI-native | 3 | src-openai-blog |
| Release Notes | 3 | src-gh-vllm-releases |
| Fix | 3 | src-gh-vllm-releases |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| Fable | 3 | src-kol-simonwillison |
| Open | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
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
| src-openai-blog | official | 200 | 50 | 50 | ✓ | True |  |
| src-anthropic-news | official | 200 | 40 | 40 | ✓ | True |  |
| src-gh-vllm-releases | official | 200 | 20 | 0 |  | None |  |
| src-deepmind-blog | official | 200 | 30 | 0 |  | True |  |
| src-hf-blog | official | 304 | 0 | 0 |  | True |  |
| src-nvidia-blog | official | 200 | 18 | 0 |  | True |  |
| src-msr-blog | official | 200 | 10 | 0 |  | True |  |
| src-meta-research | official | 200 | 10 | 0 |  | True |  |
| src-xai-news | official | 200 | 40 | 40 | ✓ | True |  |
| src-mistral-news | official | 200 | 0 | 0 | ✓ | True |  |
| src-qwen-blog | official | 200 | 30 | 30 | ✓ | True |  |
| src-kol-karpathy | kol | 200 | 10 | 10 | ✓ | True |  |
| src-kol-simonwillison | kol | 200 | 20 | 20 | ✓ | True |  |
| src-kol-interconnects | kol | 200 | 20 | 20 | ✓ | True |  |
| src-kol-thezvi | kol | robots_disallow | 0 | 0 |  | False |  |
| src-kol-oneusefulthing | kol | 200 | 20 | 20 | ✓ | True |  |
| src-kol-lilianweng | kol | 200 | 20 | 20 | ✓ | True |  |
| src-kol-raschka | kol | 200 | 20 | 20 | ✓ | True |  |
| src-hn-frontpage | aggregator | 200 | 30 | 29 | ✓ | True |  |

`skipped_lifecycle` = 未被請求，error 欄顯示其 lifecycle 值。
`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕。


## 本輪已知缺口（勿當成已實現）

- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來
- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能
- `seen.json` 無保留策略，會單調成長；`_corpus` 全量進版控的問題同理未解
- backfill 以「該來源首次抓取」判定，首跑當天發布的新文章會被誤標為存量
- author 分類是字面規則，可能誤判；請對照上面的分類抽樣校準
