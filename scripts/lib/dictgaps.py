"""dictgaps.py — 字典補漏候選的計數與晉升判準。單一真相源。

為什麼要有這個檔：晉升門檻（跨 ≥2 來源、≥3 次）原本硬寫在
`pulse-probe.write_report()` 裡，而 `gate.yaml` 的 `clustering.unknown_entity`
說字典缺口要收到 `_dashboards/dictionary-gaps.md`——那個檔案不存在，也沒有任何
一行碼會產生它。

補上那一頁的時候有兩條路：在新腳本裡把門檻再寫一次，或把判準搬出來讓兩邊共用。
抄一份的失敗形態這個 repo 已經量過三次（`lib/sources.py`、`lib/entities.py`、
還有那份手寫的未接線清單）：兩邊在門檻沒動過的日子裡給一樣的答案，正好在有人
調了其中一邊的那天分岔，而**不會有任何東西變紅**。

所以判準住這裡，門檻住 `gate.yaml`，兩個消費者都讀同一份。

不讀磁碟、不讀時鐘、不呼叫任何模型。
"""
from __future__ import annotations

from collections import Counter, defaultdict

DEFAULT_MIN_HITS = 3
DEFAULT_MIN_SOURCES = 2


def thresholds(gate: dict) -> tuple[int, int]:
    """→ (最少出現次數, 最少來源數)。讀不到就用預設值。

    讀不到時退回預設而不是 0：0 會讓每一個一次性雜訊都晉升，也就是設定檔壞掉
    的時候規則反而變鬆。設定讀不到不可以讓門檻自己打開。
    """
    blk = ((gate or {}).get("clustering") or {}).get("unknown_entity") or {}
    def _int(key, default):
        try:
            v = int(blk.get(key, default))
        except (TypeError, ValueError):
            return default
        return v if v > 0 else default
    return _int("promote_min_hits", DEFAULT_MIN_HITS), \
        _int("promote_min_sources", DEFAULT_MIN_SOURCES)


def tally(rows):
    """rows: iterable of {source_id, candidates}。→ (次數 Counter, 候選→來源集合)。

    **一列語料算一次。** 呼叫端負責先去重——`_corpus/<日>/` 是「當天看到的清單」
    不是「當天新增的清單」，同一則新聞每天都會再被寫進當天的檔案一次，跨天累加
    行數數到的是「項目 × 天」。同一個坑 `Sources/*.md` 的 `items_observed` 踩過
    一次（實測 956 行對 461 個相異項目，虛胖一倍），寫在
    references/vault-pages.md。
    """
    cnt: Counter = Counter()
    srcs: dict[str, set] = defaultdict(set)
    for r in rows:
        sid = r.get("source_id")
        for c in r.get("candidates") or []:
            cnt[c] += 1
            srcs[c].add(sid)
    return cnt, srcs


def promoted(cnt, srcs, min_hits, min_sources):
    """達標的候選：[(候選, 次數, 來源數)]，次數高的在前。"""
    return [(c, n, len(srcs[c])) for c, n in cnt.most_common()
            if n >= min_hits and len(srcs[c]) >= min_sources]


def single_source(cnt, srcs, min_hits):
    """次數夠但只有一個來源的候選：[(候選, 次數, 那個來源)]。

    冷啟階段來源少且詞彙不重疊時，「跨 ≥2 來源」結構上不可能成立，晉升表會永遠
    是空的——看起來機制在跑，實際永遠不輸出。這一區讓收割機制在那個階段也看得見，
    但**明確不參與晉升**：它不是一份比較寬鬆的晉升清單，是一份觀察清單。
    """
    return [(c, n, sorted(srcs[c])[0]) for c, n in cnt.most_common()
            if n >= min_hits and len(srcs[c]) == 1]
