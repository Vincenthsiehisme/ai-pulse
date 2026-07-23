# probe report 2026-07-24

M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。

## 兩個決定性比率

| track | 條目 | author 存在率 | 實體命中率 |
|---|---|---|---|
| official | 120 | 120/120 = 100% | 37/120 = 31% |

- **author 存在率**決定人物層與獨立性升級有沒有用；官方線若過低，people.yaml 只在 KOL 線生效。
- **實體命中率**決定字典往哪長。低命中不代表字典爛，可能是語料型態與假設不符。

## 命中的實體型別分佈

- company: 17
- technology: 17
- framework: 16
- infrastructure: 4
- product_line: 3

## 字典補漏候選（未命中且跨來源出現）

晉升門檻：跨 ≥2 來源、≥3 次。只列達標者，避免一次性雜訊灌進字典。

| 候選 | 次數 | 來源數 |
|---|---|---|
| （本輪無達標候選） | | |

## 來源狀態

| source | track | status | items | robots | error |
|---|---|---|---|---|---|
| src-openai-blog | official | robots_disallow | 0 | False |  |
| src-arxiv-cs-cl | official | 200 | 100 | None |  |
| src-gh-vllm-releases | official | 200 | 20 | None |  |
| src-hn-frontpage | aggregator | unsupported_adapter | 0 | None | json-api |

## 本輪已知缺口（勿當成已實現）

- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來
- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能
