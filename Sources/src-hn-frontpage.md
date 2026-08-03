---
id: "src-hn-frontpage"
type: "source"
owner: "Hacker News"
media_group: "YCombinator"
track: "aggregator"
tier: 3
role: "aggregator"
source_category: "aggregator"
corpus_type: "aggregated"
region: "global"
language: "en"
lifecycle: "probing"
robots_ok: true
license_note: "titles + links only"
can_satisfy_primary: false
endpoint: "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30"
robots_checked_day: "2026-08-03"
first_fetch_at: "2026-07-25"
last_observed_day: "2026-08-03"
items_observed: 276
events_bound: 4
events_published: 2
health_score: 100
consecutive_failures: 0
last_status: 200
---

# Hacker News（src-hn-frontpage）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | 會被抓 |
| 已觀測 | 276 筆 | 抓到了，但站方那陣子沒發東西 |
| 有效產出 | 4 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 2 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 這條來源不能單獨作為一手證據（`can_satisfy_primary: false`）。它的角色是佐證與獨立性，不是「事情發生了」的來源。

> 媒體集團：**YCombinator**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30`
- adapter：`json-api`
- 授權註記：titles + links only
