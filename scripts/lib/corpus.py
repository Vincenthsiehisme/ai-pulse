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
"""
from collections import Counter
from pathlib import Path

DAY_LEN = 10  # YYYY-MM-DD


def _day_dirs(root: Path):
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir()
                  if d.is_dir() and len(d.name) == DAY_LEN and d.name[4] == "-")


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
    """有語料的日子（升冪）。"""
    return _day_dirs(vault / "_corpus")


def run_days(vault: Path):
    """跑過班的日子（升冪）。有跑就有 _probe/<day>/，跟有沒有抓到東西無關。"""
    return _day_dirs(vault / "_probe")
