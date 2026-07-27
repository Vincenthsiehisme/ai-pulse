---
id: "src-hf-blog"
type: "source"
owner: "Hugging Face"
media_group: "HuggingFace"
track: "official"
tier: 1
role: "official"
source_category: "vendor"
corpus_type: "company_release"
region: "US"
language: "en"
lifecycle: "probing"
robots_ok: true
license_note: "titles + excerpt + link"
endpoint: "https://huggingface.co/blog/feed.xml"
robots_checked_day: "2026-07-27"
first_fetch_at: "2026-07-23"
last_observed_day: "2026-07-27"
items_observed: 21
events_bound: 2
events_published: 1
health_score: 100
consecutive_failures: 0
last_status: 304
---

# Hugging Face（src-hf-blog）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | 會被抓 |
| 已觀測 | 21 筆 | 抓到了，但站方那陣子沒發東西 |
| 有效產出 | 2 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 1 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 媒體集團：**HuggingFace**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://huggingface.co/blog/feed.xml`
- adapter：`rss`
- 授權註記：titles + excerpt + link
