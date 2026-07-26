# -*- coding: utf-8 -*-
"""_corpus/ 與 _probe/ 的目錄層盤點——「這條鏈跑了沒 / 抓到東西沒」的單一真相源。

兩個時間軸刻意分開，因為它們回答的是不同的問題：

    _probe/<day>/report.md   每班都寫，**不管有沒有抓到東西** → 鏈有沒有在跑
    _corpus/<day>/*.jsonl    只有真的收到項目才會建 → 鏈有沒有看見東西

pulse-monitor 的模組說明講過「靜默死掉」與「靜默瞎掉」是兩種病。只看 `_corpus/`
會把「今天大家都沒發新聞」誤判成鏈死了；只看 `_probe/` 會把 07-24 那種
「鏈跑得很完美但什麼都看不見」判成綠燈。所以健康頁兩個都印。

抽到 lib/ 是因為 pulse-source-notes.py 與 pulse-monitor.py 都要數同一件事，
兩份實作遲早會漂。

**目錄名不是證據，內容才是。**（見 references/health-alarms.md）
目錄是「打算寫東西之前」就建好的，中間任何一步失敗都會留下一個空目錄，
而空目錄被當成「這天有語料」的話，死人開關會安靜地變成一顆綠燈。
所以這裡兩件事都做：日期名嚴格驗（`2026-13-99` 不是日期），
內容也驗（`corpus_days()` 要有非空白的 jsonl 行，`run_days()` 要有 report.md）。
"""
from collections import Counter
from datetime import datetime
from pathlib import Path

DAY_LEN = 10  # YYYY-MM-DD


def is_day_name(name: str) -> bool:
    """嚴格的 YYYY-MM-DD。

    以前的判準是「長度 10 且第 5 個字元是 `-`」，`2026-13-99` 與 ISO 週日期
    `2026-W30-1` 都通得過。strptime 不會。
    """
    if len(name) != DAY_LEN:
        return False
    try:
        datetime.strptime(name, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _day_dirs(root: Path, keep=None):
    """root 底下名字是合法日期的子目錄（升冪）。keep(dir) 可再加內容條件。"""
    if not root.exists():
        return []
    out = []
    for d in root.iterdir():
        if not (d.is_dir() and is_day_name(d.name)):
            continue
        if keep is not None and not keep(d):
            continue
        out.append(d.name)
    return sorted(out)


def _has_jsonl_rows(day_dir: Path) -> bool:
    """至少一行 strip() 後非空的 .jsonl——跟 observed() 用同一把尺。"""
    for fp in day_dir.glob("*.jsonl"):
        for ln in fp.read_text("utf-8").splitlines():
            if ln.strip():
                return True
    return False


def observed(vault: Path):
    """數 _corpus/：每條來源累計產出過幾筆、最後一天是哪天。

    回傳 (Counter{source_id: 筆數}, {source_id: 'YYYY-MM-DD'})。
    """
    counts, last_day = Counter(), {}
    corpus = vault / "_corpus"
    for day in _day_dirs(corpus):
        for fp in sorted((corpus / day).glob("*.jsonl")):
            n = sum(1 for ln in fp.read_text("utf-8").splitlines() if ln.strip())
            if n:
                counts[fp.stem] += n
                last_day[fp.stem] = day
    return counts, last_day


def corpus_days(vault: Path):
    """有語料的日子（升冪）。空目錄不算——見模組說明。"""
    return _day_dirs(vault / "_corpus", keep=_has_jsonl_rows)


def run_days(vault: Path):
    """跑過班的日子（升冪）。判準是 report.md 真的寫出來了，跟有沒有抓到東西無關。"""
    return _day_dirs(vault / "_probe", keep=lambda d: (d / "report.md").exists())
