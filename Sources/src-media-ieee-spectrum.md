---
id: "src-media-ieee-spectrum"
type: "source"
owner: "IEEE Spectrum"
media_group: "IEEE"
track: "media"
tier: 2
role: "media"
source_category: "media"
corpus_type: "media_report"
region: "US"
language: "en"
lifecycle: "probing"
robots_ok: true
license_note: "titles + excerpt + link"
can_satisfy_primary: false
endpoint: "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss"
robots_checked_day: "2026-07-27"
first_fetch_at: "2026-07-26"
last_observed_day: "2026-08-02"
items_observed: 25
events_bound: 0
events_published: 0
health_score: 100
consecutive_failures: 0
last_status: 200
---

# IEEE Spectrum（src-media-ieee-spectrum）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | 會被抓 |
| 已觀測 | 25 筆 | 抓到了，但站方那陣子沒發東西 |
| 有效產出 | 0 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 0 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 這條來源不能單獨作為一手證據（`can_satisfy_primary: false`）。它的角色是佐證與獨立性，不是「事情發生了」的來源。

> 媒體集團：**IEEE**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss`
- adapter：`rss`
- 授權註記：titles + excerpt + link
