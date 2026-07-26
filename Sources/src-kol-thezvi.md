---
id: "src-kol-thezvi"
type: "source"
owner: "Zvi Mowshowitz"
media_group: "Don't Worry About the Vase"
person_id: "person-zvi-mowshowitz"
track: "kol"
tier: 2
role: "expert"
source_category: "individual"
corpus_type: "person_signal"
region: "US"
language: "en"
lifecycle: "probing"
robots_ok: true
license_note: "titles + excerpt + link"
can_satisfy_primary: false
endpoint: "https://thezvi.substack.com/feed"
robots_checked_day: "2026-07-26"
first_fetch_at:
last_observed_day:
items_observed:
events_bound: 0
events_published: 0
health_score: 100
consecutive_failures: 0
last_status: "robots_unknown"
---

# Zvi Mowshowitz（src-kol-thezvi）

> 由 `pulse-source-notes.py` 自動產生（零 LLM）。設定欄位抄自 `_config/sources.yaml`，數字數自 `_corpus/` 與 `Events/`。**手動編輯會在下一班被覆蓋。**

## 四態

| 層 | 數字 | 這一格是 0 代表什麼 |
|---|---|---|
| 收錄 | `probing` | **每班都被跳過**：robots.txt 取不到，保守跳過（不是站方拒絕） |
| 已觀測 | **尚未抓取過** | 我們對它的產出量一無所知 |
| 有效產出 | 0 則事件 | 抓到了但聚類沒把它綁成證據 |
| 已發布 | 0 則 | 綁上了但門禁擋著——那是設計，不是故障 |

> 這條來源**從來沒有成功抓取過一次**（`_probe/state.json` 沒有它的 `first_fetch_at`）。所以上面那格是**量不到**，不是量到 0——我們對它的產出量一無所知。（紅線 8）上一班的狀態是 `robots_unknown`。

> 這條來源不能單獨作為一手證據（`can_satisfy_primary: false`）。它的角色是佐證與獨立性，不是「事情發生了」的來源。

> 媒體集團：**Don't Worry About the Vase**。獨立性是按 source + author + media group 判的，所以同一個 media_group 的兩條來源**加起來只算一個獨立聲音**。

## 端點

- `https://thezvi.substack.com/feed`
- adapter：`rss`
- 授權註記：titles + excerpt + link
