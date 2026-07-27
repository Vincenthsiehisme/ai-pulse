# -*- coding: utf-8 -*-
"""clock.py — 這套系統唯一一個「取日期」的地方。

規格見 references/timezones.md。改這裡之前先改那裡（紅線 9）。

兩層，兩個時區：

* **儲存 / 判斷 → UTC**。目錄名、`evt-<日期>-<hash>` 的 id、所有戳記與相減。
  用 `utc_today()` / `utc_date()`。
* **顯示 → 台北，而且畫面上要標**。只有 `pulse-render.py` 能碰。
  用 `display_date()` / `display_stamp()`。

為什麼要收成一個模組：這條規則 2026-07-26 就寫下來過，也修好過——但只修在發現它
的那個消費端（`pulse-monitor._as_date()`），另一個消費端（`pulse-cluster`，產生 id
的那支）安靜地繼續用裸 `.date()`，而且**沒有任何東西會紅**，因為當時的資料剛好讓
兩種寫法答案一樣。收成一個模組本身擋不住第三次；擋得住的是 selftest 那條機械檢查
——`date.today()` 與裸 `.date()` 除了這個檔案以外一律不准出現。
"""
from __future__ import annotations

import ast
import re
from datetime import date, datetime, timedelta, timezone

# 顯示用時區。台灣沒有日光節約時間，所以固定偏移是對的；哪天要支援會 DST 的地區，
# 這裡要換成 zoneinfo，而不是把 8 改成別的數字。
DISPLAY_TZ = timezone(timedelta(hours=8))
DISPLAY_TZ_LABEL = "台北時間"


def utc_now() -> datetime:
    """現在（aware，UTC）。取代散落各處的 `datetime.now(timezone.utc)`。"""
    return datetime.now(timezone.utc)


def utc_today() -> date:
    """今天（UTC）。**取代 `date.today()`。**

    `date.today()` 讀的是執行機器的本機時區。Actions 的 runner 是 UTC 所以巧合
    一致——但你在台北 00:00–08:00 之間跑一次 probe，它會開一個「明天」的
    `_corpus/` 目錄，而 monitor 算出來的 lag 是負數。那個洞不會自癒：時間往前走
    只會讓它更綠。見 references/health-alarms.md。
    """
    return datetime.now(timezone.utc).date()


def utc_date(dt) -> date | None:
    """aware/naive datetime → **UTC** 日期。None 進 None 出。

    帶時區的值先歸零到 UTC 再取日期：`2026-07-28T02:00:00+08:00` 的 `.date()` 是
    07-28，但那個瞬間的 UTC 日期是 07-27。不帶時區的值視為 UTC（既有語意，不改；
    代價寫在 references/timezones.md）。
    """
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).date() if dt.tzinfo else dt.date()


def display_date(dt) -> date | None:
    """aware/naive datetime → **台北**日期。**只有顯示層能用。**"""
    if dt is None:
        return None
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(DISPLAY_TZ).date()


def display_date_str(dt) -> str | None:
    d = display_date(dt)
    return d.isoformat() if d else None


def display_stamp(dt=None) -> str:
    """→ `2026-07-27 20:15（台北時間）`。

    那四個字不是裝飾。一個沒有時區標示的日期，讀者無從判斷它是誰的日期，於是他會
    預設是自己的——而實測 52 則 Event 裡有 12 則，那個預設是錯的。
    """
    aware = utc_now() if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
    return (f"{aware.astimezone(DISPLAY_TZ).strftime('%Y-%m-%d %H:%M')}"
            f"（{DISPLAY_TZ_LABEL}）")


def utc_stamp(dt=None) -> str:
    """→ `2026-07-27 12:15Z`。給**機器讀**的（data/*.json 的 `generated`）。

    尾巴那個 Z 是規格的一部分：一個沒有時區標示的戳記，下一個讀它的人會用自己的
    時區去解讀。給人看的那一版在 `display_stamp()`。
    """
    aware = utc_now() if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def utc_date_str(dt) -> str | None:
    d = utc_date(dt)
    return d.isoformat() if d else None


# ─── 機械檢查：除了這個檔案，誰都不准自己取日期 ──────────────────────────
# 收成一個模組本身擋不住第三次犯——2026-07-26 那次就是「規則寫下來、修好了、
# 還記了為什麼」，然後另一個消費端安靜地繼續用舊寫法。擋得住的是下面這條。
#
# 走 ast 不走 regex：註解與 docstring 裡本來就會出現 `.date()`（這個檔案自己就有
# 好幾處在解釋為什麼不能用），regex 會把說明文字讀成違規。ast 只看真的呼叫。
_BANNED = {
    "date": "裸 .date()：帶時區的值要先歸零，用 clock.utc_date()",
    "today": "date.today() 讀本機時區，用 clock.utc_today()",
    "strftime": "自己格式化日期字串，用 clock.utc_stamp() / display_stamp()",
}
# strftime 只有在格式字串裡含日期欄位時才算——`%H:%M` 這種純時間格式不管。
_DATE_DIRECTIVES = ("%Y", "%y", "%m", "%d", "%j", "%F", "%x", "%c")


def _is_date_strftime(node) -> bool:
    for a in node.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return any(d in a.value for d in _DATE_DIRECTIVES)
    return False


def banned_date_calls(source: str) -> list[str]:
    """→ 這份原始碼裡違規的取日期呼叫，`第N行:寫法` 形式。

    不保證什麼：只認**字面**的屬性呼叫。`getattr(dt, "date")()` 繞得過去。
    這條檢查防的是遺忘，不是防惡意。
    """
    bad = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        attr = node.func.attr
        if attr not in _BANNED:
            continue
        if attr == "today" and not (isinstance(node.func.value, ast.Name)
                                    and node.func.value.id == "date"):
            continue
        if attr == "strftime" and not _is_date_strftime(node):
            continue
        bad.append(f"{node.lineno}:{attr}()")
    return bad


# ─── 排程：cron 是 UTC，但這個站的日是台北日 ────────────────────────────
# 規格 references/timezones.md〈排程〉。
#
# Actions 的 cron 沒有時區設定，永遠是 UTC——**連 day-of-week 也是**。
# 這一格踩過一次：一個叫「每週一」的排程寫 `0 16 * * 1`，那是 UTC 週一 16:00，
# 已經是**台北週二 00:00**。名字跟事實差一天，而不會有任何東西紅。
#
# 所以規矩是：**每一行 cron 都要在同一行的註解裡寫出它的台北時間。**
# 列舉是機械的（下面這條 regex），換算是人寫的（註解），測試比對兩者存在與否。
# 這條檢查不驗算得對不對——它擋的是「一個沒有人換算過的 cron 悄悄長出來」。
_CRON_RE = re.compile(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]\s*(#.*)?$", re.M)

# 這個站的「一天」是台北日。要讓「一班收到的新項目」剛好等於「台北那一整天」，
# 每日班必須跑在 UTC 16:00 —— 那是台北隔日 00:00，上一班是台北當日 00:00，
# 中間那段正好是台北的一整天。而 `_corpus/<UTC 日>/` 的目錄名也正好等於那個台北日。
#
# 這個對應**只有 16 成立**。改成 `0 20 * * *`（台北 04:00）看起來完全無害，
# 但目錄名會跟它裝的內容錯開一天，而不會有任何東西紅。所以釘住它。
DAILY_UTC_HOUR = 16


def cron_entries(text: str):
    """→ [{'expr', 'comment', 'line'}]，YAML 文字裡每一行 cron。"""
    out = []
    for m in _CRON_RE.finditer(text):
        out.append({"expr": m.group(1).strip(),
                    "comment": (m.group(2) or "").strip(),
                    "line": text[: m.start()].count("\n") + 1})
    return out


def cron_unannotated(text: str) -> list[str]:
    """→ 沒有在同一行註解裡寫出台北時間的 cron。"""
    return [e["expr"] for e in cron_entries(text)
            if DISPLAY_TZ_LABEL[:2] not in e["comment"]]


def daily_utc_hour(expr: str):
    """→ 這條 cron 每天固定跑一班的 UTC 小時；不是「每天一班」就回 None。

    `0 16 * * *` → 16。`0 */2 * * *`（一天 12 班）、`0 16 * * 1`（每週）都回 None
    ——前者是暫時加密期，後者是週班，兩種都不該被這條規則管。
    """
    parts = expr.split()
    if len(parts) != 5:
        return None
    minute, hour, dom, mon, dow = parts
    if (dom, mon, dow) != ("*", "*", "*"):
        return None
    if not (minute.isdigit() and hour.isdigit()):
        return None
    return int(hour)


def misanchored_daily(text: str) -> list[str]:
    """→ 每天一班、但沒跑在 UTC 16:00 的 cron（＝收班窗口跟台北日對不上）。"""
    return [e["expr"] for e in cron_entries(text)
            if (h := daily_utc_hour(e["expr"])) is not None and h != DAILY_UTC_HOUR]
