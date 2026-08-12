---
generated_day: "2026-08-12"
---

# 覆蓋缺口：我們看不到什麼

> 由 `pulse-coverage-gap.py --write` 產生（零 LLM）。**手動編輯會在下一班被覆蓋。**

左邊是**需求**（人回答 `unanswerable` 時填的原因碼），右邊是**供給**（`_config/sources.yaml` 裡會被抓的來源宣稱的能力）。
兩邊用同一份詞彙表，所以可以放在同一列比較——理由見 `references/source-capabilities.md`。

## 矩陣

供給拆兩欄：**官方**是當事人自己說，**獨立**是媒體線與 KOL 線。
`track: aggregator`（HN）兩欄都不算——設定檔寫明它只當候選來源、
不作任何事實依據。**燈號只看獨立那一欄**，理由見 `references/vault-pages.md`。

| 能力 | 需求（答不了幾次） | 官方 | 獨立 | 判斷 | 說明 |
|---|---:|---:|---:|:---:|---|
| `benchmark` | 7 | 3 | 1 | 🔴 | 需求是獨立供給的 7.0 倍 |
| `enterprise_adoption` | 4 | 2 | 5 | 🟢 | 獨立供給跟得上 |
| `policy_execution` | 3 | 1 | 3 | 🟢 | 獨立供給跟得上 |
| `third_party_validation` | 1 | 0 | 10 | 🟢 | 獨立供給跟得上 |
| `developer_feedback` | 1 | 1 | 3 | 🟢 | 獨立供給跟得上 |
| `financial_impact` | 1 | 1 | 2 | 🟢 | 獨立供給跟得上 |
| `product_release` | 1 | 11 | 2 | 🟢 | 獨立供給跟得上 |
| `procurement` | 1 | 0 | 0 | 🔴 | 沒有任何來源在看 |
| `social_signal` | 0 | 0 | 8 | ⚪ | 這一輪沒有人問到這一類 |
| `research_replication` | 0 | 0 | 5 | ⚪ | 這一輪沒有人問到這一類 |
| `legal_proceeding` | 0 | 0 | 3 | ⚪ | 這一輪沒有人問到這一類 |
| `infrastructure` | 0 | 1 | 1 | ⚪ | 這一輪沒有人問到這一類 |
| `supply_chain` | 0 | 2 | 1 | ⚪ | 這一輪沒有人問到這一類 |
| `official_announcement` | 0 | 9 | 0 | ⚪ | 只有當事人自己在說 |
| `research_release` | 0 | 8 | 0 | ⚪ | 只有當事人自己在說 |

- `other` 佔比：3/22 = 14%

**1 種能力沒有任何在跑的來源宣稱**：`procurement`

這一格不需要等人回答就成立——它是今天就量得到的盲區。

## 這張表要拿來做什麼

決定下一波要補哪一類來源，而不是補幾條來源。
PRD §20：Source Expansion 的完成條件是「有沒有補到新的觀測能力」，
不是「新增來源數」。

**但先讀 `docs/design/` 底下 2026-08-11 的 attach 實測**：
補來源不會自動讓獨立佐證上升——第三方後續有 12/14 黏不上原事件，
卡在標題相似度 0.46 那道閘。供給補起來之前，先確認接得上。
