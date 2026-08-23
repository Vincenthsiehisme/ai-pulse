---
id: "src-nvidia-blog"
type: "source"
owner: "NVIDIA"
media_group: "NVIDIA"
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
endpoint: "https://blogs.nvidia.com/feed/"
robots_checked_day: "2026-08-19"
first_fetch_at: "2026-07-23"
last_observed_day: "2026-08-23"
items_observed: 38
events_bound: 35
events_published: 32
health_score: 100
consecutive_failures: 0
last_status: 200
---

# NVIDIA（src-nvidia-blog）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | 會被抓 |
| 已觀測 | 38 筆 | 抓到了，但站方那陣子沒發東西 |
| 有效產出 | 35 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 32 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 媒體集團：**NVIDIA**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://blogs.nvidia.com/feed/`
- adapter：`rss`
- 授權註記：titles + links only
