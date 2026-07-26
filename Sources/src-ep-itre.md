---
id: "src-ep-itre"
type: "source"
owner: "European Parliament"
media_group: "EU-Parliament"
track: "official"
tier: 1
role: "official"
source_category: "regulator"
corpus_type: "policy"
region: "EU"
language: "en"
lifecycle: "dormant"
robots_ok: true
license_note: "titles + links only"
endpoint: "https://www.europarl.europa.eu/rss/committee/itre/en.xml"
robots_checked_day: "2026-07-26"
first_fetch_at: "2026-07-23"
last_observed_day: "2026-07-24"
items_observed: 25
events_bound: 0
events_published: 0
health_score: 100
consecutive_failures: 0
last_status: "skipped_lifecycle"
---

# European Parliament（src-ep-itre）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `dormant` | **不會被抓**：lifecycle 不在 active / degraded / probing |
| 已觀測 | 25 筆 | 抓到了，但站方那陣子沒發東西 |
| 有效產出 | 0 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 0 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 媒體集團：**EU-Parliament**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://www.europarl.europa.eu/rss/committee/itre/en.xml`
- adapter：`rss`
- 授權註記：titles + links only
