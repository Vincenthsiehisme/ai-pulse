# probe report 2026-07-24

M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。

> ⚠ 本輪含 133 筆 backfill（首次抓取的既有存量）。
> backfill 不代表當期訊號，lead_days 與熱度統計應排除。

## 兩個決定性比率

| track | 條目 | 5a author 有值 | 5b 可解析自然人 | 實體命中率 |
|---|---|---|---|---|
| official | 133 | 48/133 = 36% | 27/133 = 20% | 62/133 = 47% |

- **5a（author 有值）只用來偵測 adapter 解析失敗**，不作任何人物層判斷。M1 實測 120/120 有值卻幾乎不可用，這個數字單獨看會騙人。
- **5b（可解析自然人）才決定人物層與獨立性升級有沒有用。**官方線若過低，people.yaml 只在 KOL 線生效。
- **實體命中率**決定字典往哪長。低命中不代表字典爛，可能是語料型態與假設不符。

### author 分類分佈（5b 的組成）

| kind | 筆數 | 計入 5b |
|---|---|---|
| none | 85 |  |
| handle | 21 |  |
| person | 18 | ✓ |
| multi_person | 9 | ✓ |

分類全為字面規則，無推論。判不出來一律 unknown 且不計入 5b（保守預設）。
`multi_person` 是共同作者串，本專案判定為可解析到自然人；
若要嚴格採「單一自然人」，把它移出 PERSON_KINDS 即可。

### 分類抽樣（供人工校準規則）

| author 原值 | 判定 | 來源 |
|---|---|---|
| khluu | handle | src-gh-vllm-releases |
| GeForce NOW Community | person | src-nvidia-blog |
| NVIDIA | handle | src-nvidia-blog |
| Son Ho, Cédric Fournet, Antoine Delignat-Lavaud, Samuel Lee, | multi_person | src-msr-blog |
| Jianfeng Gao | person | src-msr-blog |

## 命中的實體型別分佈

- company: 44
- framework: 18
- product_line: 12
- technology: 11
- infrastructure: 8

## 字典補漏候選（未命中且跨來源出現）

晉升門檻：跨 ≥2 來源、≥3 次。只列達標者，避免一次性雜訊灌進字典。

| 候選 | 次數 | 來源數 |
|---|---|---|
| Industry | 16 | 2 |
| Security | 6 | 3 |
| July | 5 | 2 |
| Gemma | 3 | 2 |

### 單來源高頻（觀察用，不列入晉升）

目前活躍來源 7 條。來源數少時「跨 ≥2 來源」門檻結構上難以成立，
上表為空不代表收割機制壞掉。此區僅供觀察，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Committee | 15 | src-ep-itre |
| Research | 15 | src-ep-itre |
| Highlights | 13 | src-gh-vllm-releases |
| European Union | 12 | src-ep-itre |
| Draft | 10 | src-ep-itre |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Union | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Energy | 8 | src-ep-itre |
| Minutes | 7 | src-ep-itre |
| June | 6 | src-ep-itre |
| Co-Scientist | 5 | src-deepmind-blog |
| Wednesday | 4 | src-ep-itre |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Source | 4 | src-ep-itre |
| Release Notes | 3 | src-gh-vllm-releases |
| Fix | 3 | src-gh-vllm-releases |
| U.S | 3 | src-nvidia-blog |
| Defence Source | 3 | src-ep-itre |
| Thursday | 3 | src-ep-itre |
| Tuesday | 3 | src-ep-itre |
| Video | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Only | 3 | src-ep-itre |

## 來源狀態

| source | track | status | items | new | backfill | robots | error |
|---|---|---|---|---|---|---|---|
| src-openai-blog | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-arxiv-cs-cl | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-ec-digital-strategy | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-consilium-press | official | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-hn-frontpage | aggregator | skipped_lifecycle | 0 | 0 |  | None | dormant |
| src-gh-vllm-releases | official | 200 | 20 | 20 | ✓ | None |  |
| src-deepmind-blog | official | 200 | 30 | 30 | ✓ | True |  |
| src-hf-blog | official | 200 | 20 | 20 | ✓ | True |  |
| src-nvidia-blog | official | 200 | 18 | 18 | ✓ | True |  |
| src-msr-blog | official | 200 | 10 | 10 | ✓ | True |  |
| src-meta-research | official | 200 | 10 | 10 | ✓ | True |  |
| src-ep-itre | official | 200 | 25 | 25 | ✓ | True |  |

`skipped_lifecycle` = 未被請求，error 欄顯示其 lifecycle 值。
`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕。


## 本輪已知缺口（勿當成已實現）

- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來
- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能
- `seen.json` 無保留策略，會單調成長；`_corpus` 全量進版控的問題同理未解
- backfill 以「該來源首次抓取」判定，首跑當天發布的新文章會被誤標為存量
- author 分類是字面規則，可能誤判；請對照上面的分類抽樣校準
