---
id: "src-media-theregister"
type: "source"
owner: "The Register"
media_group: "Situation Publishing"
track: "media"
tier: 2
role: "media"
source_category: "media"
corpus_type: "media_report"
region: "UK"
language: "en"
lifecycle: "probing"
robots_ok: false
license_note: "titles + excerpt + link"
can_satisfy_primary: false
endpoint: "https://www.theregister.com/software/ai_ml/headlines.atom"
robots_checked_day: "2026-09-02"
first_fetch_at:
last_observed_day:
items_observed:
events_bound: 0
events_published: 0
health_score: 100
consecutive_failures: 0
last_status: "robots_disallow"
---

# The Register（src-media-theregister）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | **每班都被跳過**：站方 robots.txt 明文 Disallow（合規，不是故障） |
| 已觀測 | **尚未抓取過** | 我們對它的產出量一無所知 |
| 有效產出 | 0 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 0 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 這條來源**從來沒有成功抓取過一次**（`_probe/state.json` 沒有它的 `first_fetch_at`）。所以上面那格是**量不到**，不是量到 0——我們對它的產出量一無所知。（紅線 8）上一班的狀態是 `robots_disallow`。

> 這條來源不能單獨作為一手證據（`can_satisfy_primary: false`）。它的角色是佐證與獨立性，不是「事情發生了」的來源。

> 媒體集團：**Situation Publishing**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://www.theregister.com/software/ai_ml/headlines.atom`
- adapter：`atom`
- 授權註記：titles + excerpt + link
