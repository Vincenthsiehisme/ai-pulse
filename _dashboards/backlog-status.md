---
generated_day: '2026-08-01'
generator: scripts/pulse-backlog-status.py
---

# 現況（機器量的）

這一頁**每班重新生成**，`BACKLOG.md` 不再手寫任何數字。
理由與規格見 `references/vault-pages.md`；為什麼非這樣不可，見
`BACKLOG.md` 的實例清單第 9 條——上一版的手寫表在寫下之後 3 小時就過期了。

**這一頁只有量測，沒有判斷。** 哪一條重要、壞了會不會變紅、現在有沒有在
騙人——那些在 `BACKLOG.md`，那裡一個手寫數字都不留。

## Events

| 量到什麼 | 值 |
|---|---|
| 總數 | 80 |
| `published` | 60 |
| `review` | 19 |
| `dropped` | 1 |
| 帶 `stale_backfill` | 12 |

## 語料

| 量到什麼 | 值 |
|---|---|
| `_corpus/` 天數 | 9 |
| 起訖 | 2026-07-24 … 2026-08-01 |

## 來源

| 量到什麼 | 值 |
|---|---|
| 來源總數 | 32 |
| lifecycle 分佈 | dormant 5、probing 27 |
| language 分佈 | en 32 |
| `coverage_watch.must_watch` | 32 條，其中 20 條 `pending` |

## `gate.yaml` 接線

| 量到什麼 | 值 |
|---|---|
| leaf key 總數 | 57 |
| 標成 ⚠ 未接線 | 31 |
| 有指名消費者 | 26 |

判準在 `scripts/lib/gate_keys.py`，它**不保證**什麼寫在
`references/gate-config-status.md` 最後一節。

## 最後一班 probe

| 量到什麼 | 值 |
|---|---|
| 時間 | 2026-08-01T16:43:39+00:00 |
| 條目 / 來源 | 425 items / 32 sources |
| status 分佈 | 200 21、304 3、robots_disallow 1、robots_unknown 2、skipped_lifecycle 5 |
| 零產出（200 但 0 筆） | src-mistral-news |

零產出那一格屬於哪一種 0，看那一天的 `_probe/<日>/report.md`
〈零產出診斷〉——**這一頁不重算它**，重算就會有兩份判準。

## 這一頁刻意沒有的兩格

**selftest 條數**與**變異結果**不在這裡。它們不是每班量得到的事實：
跑一次要幾十秒到幾分鐘，而且各自已經有自己的 workflow 在紅綠。
放上來只會得到一個「上次不知道什麼時候量的」數字，
**而這一頁存在的理由就是不要有那種數字**。

要那兩個數字就自己跑，指令在 `BACKLOG.md`〈附：怎麼重新盤點這份清單〉：

```bash
python3 scripts/selftest.py | tail -1     # 有幾條測試
python3 scripts/mutate.py                 # 有幾格守不住
```

`main` 的 commit 也不在這裡：這一頁自己就住在 repo 裡，
它是哪一版產生的，`git log` 比任何自我宣稱都準。
