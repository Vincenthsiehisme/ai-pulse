# -*- coding: utf-8 -*-
"""nightcost.py — 雲端夜班成本帳的純函式（確定性，零 LLM，不碰 git 與網路）。

規格在 references/nightly-driver.md〈一晚花多少錢，要是一個被記錄的量〉，
hook 入口與 commit 條件在 scripts/nightly-cost.py、references/nightly-guard.md〈成本帳〉。

雲端排程裡寫作端跟迴圈是同一個 agent，沒有本機外殼替它記 `total_cost_usd`，
摘要那一格於是每晚都是「量不到」。這裡改從平台給的 transcript 自己算：
一個 request 的 token 分五類加總，照牌價換成 API 等價 USD。

**算不出來就是 None，不是 0。** 表外的 model、有 cache 寫卻沒有 5m／1h 拆分，
兩種都讓那一晚的 `usd_equiv` 是 None，token 照記、`note` 寫原因（紅線 8）。
"""
from __future__ import annotations

import json
from datetime import date, timedelta

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
    """一個 request 的 usage → (五類 token, 沒拆分的 cache 寫 token)。

    cache 寫有兩種價（5 分鐘與 1 小時），`cache_creation` 缺、或拆分加總對不上
    `cache_creation_input_tokens` 時，對不上的那一截記成沒拆分，不猜是哪一種。
    """
    counts = {"input": _int(usage.get("input_tokens")),
              "output": _int(usage.get("output_tokens")),
              "cache_read": _int(usage.get("cache_read_input_tokens")),
              "cache_write_5m": 0, "cache_write_1h": 0}
    written = _int(usage.get("cache_creation_input_tokens"))
    cc = usage.get("cache_creation")
    if isinstance(cc, dict):
        counts["cache_write_5m"] = _int(cc.get("ephemeral_5m_input_tokens"))
        counts["cache_write_1h"] = _int(cc.get("ephemeral_1h_input_tokens"))
    unsplit = max(0, written - counts["cache_write_5m"] - counts["cache_write_1h"])
    return counts, unsplit


def usd(counts, price):
    """五類 token × 每百萬單價 → USD，四捨五入到小數 6 位。"""
    return round(sum(counts[f] * price[f] for f in FIELDS) / 1_000_000, 6)


def tally(entries, prices=PRICES):
    """transcript → 帳本那一行除了 date／session_id 以外的欄位。"""
    by_model = {}
    for model, usage in request_usages(entries).values():
        counts, unsplit = split_usage(usage)
        m = by_model.setdefault(model, {"requests": 0, **{f: 0 for f in FIELDS},
                                        "cache_write_unsplit": 0})
        m["requests"] += 1
        for f in FIELDS:
            m[f] += counts[f]
        m["cache_write_unsplit"] += unsplit

    notes = []
    for model in sorted(by_model):
        m = by_model[model]
        tokens = sum(m[f] for f in FIELDS) + m["cache_write_unsplit"]
        if model not in prices:
            # token 全是 0 的列（例如平台插的 `<synthetic>` 訊息）不管單價是多少都是 0。
            m["usd_equiv"] = 0.0 if tokens == 0 else None
            if tokens:
                notes.append(f"{model} 不在牌價表 {PRICE_TABLE}（{tokens} tokens）")
        elif m["cache_write_unsplit"]:
            m["usd_equiv"] = None
            notes.append(f"{model} 有 {m['cache_write_unsplit']} tokens cache 寫沒有 5m／1h 拆分")
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


def ledger_row(entries, day, session_id, prices=PRICES):
    """帳本的一行，欄位順序固定（ROW_KEYS）。"""
    t = tally(entries, prices)
    t.update({"date": day, "session_id": session_id})
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
    """同一天已經有一行就原地取代，沒有就接在最後。回新的清單。"""
    out, hit = [], False
    for r in rows:
        if r.get("date") == row["date"]:
            out.append(row)
            hit = True
        else:
            out.append(r)
    if not hit:
        out.append(row)
    return out


def dump_ledger(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def prev_night(rows, today):
    """`date` 早於今天的最後一行（依 date 排），沒有回 None。"""
    t = str(today)
    older = [r for r in rows if str(r.get("date")) < t]
    return max(older, key=lambda r: str(r["date"])) if older else None


def window_stats(rows, today, days):
    """近 N 天（**不含今天**，今晚的夜班還沒收尾）的成本帳統計。

    回 {days, usd, priced, null, missing}：
      usd      有金額的那幾晚的等價 USD 合計（一晚都沒有時是 None，不是 0）
      priced   有金額的晚數
      null     `usd_equiv` 為 None 的晚數（量不到，不算進合計）
      missing  窗口內沒有帳本行的天數，從帳本第一行的日期起算（帳本開始之前不算缺）
    """
    t = today if isinstance(today, date) else date.fromisoformat(str(today))
    window = [(t - timedelta(days=i)).isoformat() for i in range(days, 0, -1)]
    by_day = {str(r.get("date")): r for r in rows}
    first = min(by_day) if by_day else None
    inwin = [by_day[d] for d in window if d in by_day]
    priced = [r["usd_equiv"] for r in inwin if r.get("usd_equiv") is not None]
    return {
        "days": days,
        "usd": round(sum(priced), 6) if priced else None,
        "priced": len(priced),
        "null": sum(1 for r in inwin if r.get("usd_equiv") is None),
        "missing": sum(1 for d in window if first is not None and d >= first
                       and d not in by_day),
    }
