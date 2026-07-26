---
id: "src-arxiv-cs-cl"
type: "source"
owner: "arXiv"
media_group: "arXiv"
track: "official"
tier: 1
role: "official"
source_category: "research"
corpus_type: "research_paper"
region: "global"
language: "en"
lifecycle: "dormant"
robots_ok: false
license_note: "abstract + link"
endpoint: "http://export.arxiv.org/rss/cs.CL"
robots_checked_day: "2026-07-26"
first_fetch_at:
last_observed_day:
items_observed:
events_bound: 0
events_published: 0
health_score: 100
consecutive_failures: 0
last_status: "skipped_lifecycle"
---

# arXiv（src-arxiv-cs-cl）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `dormant` | **不會被抓**：lifecycle 不在 active / degraded / probing |
| 已觀測 | **尚未抓取過** | 我們對它的產出量一無所知 |
| 有效產出 | 0 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 0 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 這條來源**從來沒有成功抓取過一次**（`_probe/state.json` 沒有它的 `first_fetch_at`）。所以上面那格是**量不到**，不是量到 0——我們對它的產出量一無所知。（紅線 8）上一班的狀態是 `skipped_lifecycle`。

> 媒體集團：**arXiv**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `http://export.arxiv.org/rss/cs.CL`
- adapter：`rss`
- 授權註記：abstract + link
