---
id: "src-openai-blog"
type: "source"
owner: "OpenAI"
media_group: "OpenAI"
track: "official"
tier: 1
role: "official"
source_category: "vendor"
corpus_type: "company_release"
region: "US"
language: "en"
lifecycle: "probing"
robots_ok: true
license_note: "titles + links only"
endpoint: "https://openai.com/news/rss.xml"
robots_checked_day: "2026-08-03"
first_fetch_at: "2026-07-25"
last_observed_day: "2026-08-04"
items_observed: 66
events_bound: 27
events_published: 22
health_score: 100
consecutive_failures: 0
last_status: 200
---

# OpenAI（src-openai-blog）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | 會被抓 |
| 已觀測 | 66 筆 | 抓到了，但站方那陣子沒發東西 |
| 有效產出 | 27 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 22 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 媒體集團：**OpenAI**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://openai.com/news/rss.xml`
- adapter：`rss`
- 授權註記：titles + links only
