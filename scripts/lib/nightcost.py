# -*- coding: utf-8 -*-
"""nightcost.py — 雲端夜班成本帳的純函式（確定性，零 LLM，不碰 git 與網路）。

規格在 references/nightly-driver.md〈一晚花多少錢，要是一個被記錄的量〉，
hook 入口與 commit 條件在 scripts/nightly-cost.py、references/nightly-guard.md〈成本帳〉。

雲端排程裡寫作端跟迴圈是同一個 agent，沒有本機外殼替它記 `total_cost_usd`，
摘要那一格於是每晚都是「量不到」。這裡改從平台給的 transcript 自己算：
一個 request 的 token 分五類加總，照牌價換成 API 等價 USD。

**算不出來就是 None，不是 0。** 表外的 model、cache 寫沒有 5m／1h 拆分或拆分加總對不上、
`usage.speed` 不是標準速度、`usage.server_tool_use` 有非零用量（牌價表沒有這兩種的價），
都讓那一行的 `usd_equiv` 是 None，token 照記、`note` 寫原因（紅線 8）。

帳本一個 session 一行，key 是 `session_id`，`date` 是 transcript 第一筆紀錄的 UTC 日期。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from lib import clock

LEDGER_REL = ("_probe", "nightly-cost.jsonl")
LEDGER_PATH = "/".join(LEDGER_REL)

# 成本 commit 的作者。**刻意不是 `ai-pulse-enrich`**：pulse-monitor 的
# night_shift_commit_days() 認那個作者當作「那天夜班有推」，成本 commit 每晚都會有，
# 用同一個作者會讓潤稿鏈缺日的警報假綠。網域跟 do_commit() 同一個。
COST_AUTHOR = "ai-pulse-cost"
COST_EMAIL = f"{COST_AUTHOR}@users.noreply.github.com"

# 牌價：每百萬 token 美元。來源 claude-api skill 的模型表與 prompt-caching 說明，
# 2026-09-25 取。改價就換 PRICE_TABLE 字串，舊的帳本行不回頭重算。
PRICE_TABLE = "claude-api-2026-09-25"
PRICES = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20,
                          "cache_write_5m": 2.50, "cache_write_1h": 4.00},
}
FIELDS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")
STANDARD_SPEED = "standard"
ROW_KEYS = ("date", "session_id", "requests", "by_model", *FIELDS, "usd_equiv",
            "price_table", "note")


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


def request_usages(entries):
    """transcript 的每一行 → {request key: (model, usage)}，依第一次出現的順序。

    同一個 request 在 transcript 裡一個 content block 一行，`usage` 每行重複，
    所以同一個 key 只算一次，取最後一行的 `usage`。key 是 `requestId`，沒有就
    `message.id`，兩個都沒有就一行算一個。
    """
    out = {}
    for n, obj in enumerate(entries):
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        msg = obj.get("message") or {}
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            continue
        key = obj.get("requestId") or msg.get("id") or f"#line{n}"
        out[key] = (str(msg.get("model") or "?"), usage)
    return out


def split_usage(usage):
    """一個 request 的 usage → (五類 token, 沒拆分的 cache 寫 token, 算不了價的原因清單)。

    cache 寫有兩種價（5 分鐘與 1 小時）。`cache_creation` 缺、或 5m＋1h 跟
    `cache_creation_input_tokens` 不相等（**兩個方向都算**）就不猜是哪一種：
    少的那一截記成沒拆分，多的那一截照樣記在 5m／1h，但這個 request 算不了價。
    `speed` 不是標準、`server_tool_use` 有非零用量也算不了價：牌價表沒有這兩種的價。
    """
    counts = {"input": _int(usage.get("input_tokens")),
              "output": _int(usage.get("output_tokens")),
              "cache_read": _int(usage.get("cache_read_input_tokens")),
              "cache_write_5m": 0, "cache_write_1h": 0}
    issues = []
    written = _int(usage.get("cache_creation_input_tokens"))
    cc = usage.get("cache_creation")
    if isinstance(cc, dict):
        counts["cache_write_5m"] = _int(cc.get("ephemeral_5m_input_tokens"))
        counts["cache_write_1h"] = _int(cc.get("ephemeral_1h_input_tokens"))
        split = counts["cache_write_5m"] + counts["cache_write_1h"]
        if split != written:
            issues.append(f"cache 寫 5m＋1h 加總 {split} 不等於 cache_creation_input_tokens {written}")
    elif written:
        issues.append(f"{written} tokens cache 寫沒有 5m／1h 拆分")
    unsplit = max(0, written - counts["cache_write_5m"] - counts["cache_write_1h"])
    speed = usage.get("speed")
    if speed not in (None, STANDARD_SPEED):
        issues.append(f"speed={speed} 不是標準速度")
    stu = usage.get("server_tool_use")
    if isinstance(stu, dict):
        used = {k: v for k, v in sorted(stu.items()) if isinstance(v, (int, float)) and v}
        if used:
            issues.append("server_tool_use 有用量（"
                          + "、".join(f"{k}={v}" for k, v in used.items()) + "）")
    return counts, unsplit, issues


def usd(counts, price):
    """五類 token × 每百萬單價 → USD，四捨五入到小數 6 位。"""
    return round(sum(counts[f] * price[f] for f in FIELDS) / 1_000_000, 6)


def tally(entries, prices=PRICES):
    """transcript → 帳本那一行除了 date／session_id 以外的欄位。"""
    by_model, issues = {}, {}
    for model, usage in request_usages(entries).values():
        counts, unsplit, why = split_usage(usage)
        m = by_model.setdefault(model, {"requests": 0, **{f: 0 for f in FIELDS},
                                        "cache_write_unsplit": 0})
        m["requests"] += 1
        for f in FIELDS:
            m[f] += counts[f]
        m["cache_write_unsplit"] += unsplit
        for w in why:
            issues.setdefault(model, []).append(w)

    notes = []
    for model in sorted(by_model):
        m = by_model[model]
        tokens = sum(m[f] for f in FIELDS) + m["cache_write_unsplit"]
        why = issues.get(model, [])
        if model not in prices and tokens:
            m["usd_equiv"] = None
            notes.append(f"{model} 不在牌價表 {PRICE_TABLE}（{tokens} tokens）")
        elif why:
            m["usd_equiv"] = None
            notes.append(f"{model} 有 {len(why)} 處算不了價：" + "；".join(why[:3])
                         + ("…" if len(why) > 3 else ""))
        elif model not in prices:
            # token 全是 0 的列（例如平台插的 `<synthetic>` 訊息）不管單價是多少都是 0。
            m["usd_equiv"] = 0.0
        else:
            m["usd_equiv"] = usd(m, prices[model])

    row = {"requests": sum(m["requests"] for m in by_model.values()), "by_model": by_model}
    for f in FIELDS:
        row[f] = sum(m[f] for m in by_model.values())
    vals = [m["usd_equiv"] for m in by_model.values()]
    if not by_model:
        row["usd_equiv"] = None
        notes.append("transcript 裡沒有任何帶 usage 的 assistant 訊息")
    elif any(v is None for v in vals):
        row["usd_equiv"] = None
    else:
        row["usd_equiv"] = round(sum(vals), 6)
    row["price_table"] = PRICE_TABLE
    row["note"] = "；".join(notes) or None
    return row


def session_date(entries):
    """transcript 第一筆帶 `timestamp` 的紀錄的 UTC 日期。跨午夜不換天。沒有回 None。"""
    for obj in entries:
        ts = obj.get("timestamp") if isinstance(obj, dict) else None
        if not isinstance(ts, str):
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        return clock.utc_date_str(dt)
    return None


def ledger_row(entries, session_id, prices=PRICES):
    """帳本的一行，欄位順序固定（ROW_KEYS）。date 取 session_date()。"""
    t = tally(entries, prices)
    t.update({"date": session_date(entries), "session_id": session_id})
    return {k: t[k] for k in ROW_KEYS}


def parse_ledger(text):
    """帳本文字 → 行的清單。壞行 raise ValueError 帶行號：帳本壞了不能安靜少幾晚。"""
    rows = []
    for n, line in enumerate((text or "").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            raise ValueError(f"第 {n} 行不是合法 JSON（{e}）")
        if not isinstance(obj, dict) or not isinstance(obj.get("date"), str):
            raise ValueError(f"第 {n} 行不是帶 date 的物件")
        rows.append(obj)
    return rows


def upsert(rows, row):
    """同一個 session_id 已經有一行就原地取代，沒有就接在最後。回新的清單。"""
    out, hit = [], False
    for r in rows:
        if r.get("session_id") == row["session_id"]:
            out.append(row)
            hit = True
        else:
            out.append(r)
    if not hit:
        out.append(row)
    return out


def has_session(rows, session_id):
    return any(r.get("session_id") == session_id for r in rows)


def dump_ledger(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def day_total(rows):
    """同一天的幾行 → (USD 合計或 None, null 的那幾行)。任一行 null 那天就是 None，不當 0 加。"""
    nulls = [r for r in rows if r.get("usd_equiv") is None]
    if nulls or not rows:
        return None, nulls
    return round(sum(r["usd_equiv"] for r in rows), 6), []


def prev_night(rows, today):
    """前一晚（`date` 等於 today 的前一個 UTC 日）的帳。帳本沒有早於今天的行回 None。

    回 {date, rows, usd_equiv, note, latest}：
      rows     昨天有幾行（一個 session 一行）；0 代表昨天沒有任何行
      usd_equiv  昨天所有行的合計；任一行 null 就是 None，note 列出那幾行的原因
      latest   早於今天的最後一行的日期。昨天沒有行時靠它講「最近一筆是哪天」，
               **不把更早那晚標成前一晚**
    """
    t = today if isinstance(today, date) else date.fromisoformat(str(today))
    yday = (t - timedelta(days=1)).isoformat()
    older = [str(r.get("date")) for r in rows if str(r.get("date")) < t.isoformat()]
    if not older:
        return None
    mine = [r for r in rows if str(r.get("date")) == yday]
    usd_sum, nulls = day_total(mine)
    note = "；".join((r.get("note") or f"{r.get('session_id')} 那一行沒有寫原因")
                    for r in nulls) or None
    return {"date": yday, "rows": len(mine), "usd_equiv": usd_sum,
            "note": note if mine else None, "latest": max(older)}


def window_stats(rows, today, days):
    """近 N 天（**不含今天**，今晚的夜班還沒收尾）的成本帳統計，同一天的多行先加總。

    回 {days, usd, priced_days, null_days, null_rows, missing}：
      usd          有金額的那幾天的等價 USD 合計（一天都沒有時是 None，不是 0）
      priced_days  有金額的天數
      null_days    量不到的天數（那天任一行 null 就算，不當 0 加進合計）
      null_rows    窗口內 `usd_equiv` 為 None 的行數
      missing      窗口內沒有帳本行的天數，從帳本第一行的日期起算（帳本開始之前不算缺）
    """
    t = today if isinstance(today, date) else date.fromisoformat(str(today))
    window = [(t - timedelta(days=i)).isoformat() for i in range(days, 0, -1)]
    by_day = {}
    for r in rows:
        by_day.setdefault(str(r.get("date")), []).append(r)
    first = min(by_day) if by_day else None
    totals = {d: day_total(by_day[d]) for d in window if d in by_day}
    priced = [v for v, _ in totals.values() if v is not None]
    return {
        "days": days,
        "usd": round(sum(priced), 6) if priced else None,
        "priced_days": len(priced),
        "null_days": sum(1 for v, _ in totals.values() if v is None),
        "null_rows": sum(len(n) for _, n in totals.values()),
        "missing": sum(1 for d in window if first is not None and d >= first
                       and d not in by_day),
    }
