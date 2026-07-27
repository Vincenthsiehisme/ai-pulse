"""entities.py — 命名實體字典的比對層。單一真相源。

為什麼要有這個檔：
    `normalize_text` / `build_matcher` / `match_entities` 原本住在
    `pulse-probe.py` 裡，因為當時只有抓取端需要「這段文字命中哪些實體」。
    2026-07-27 轉載鏈判定要問「兩條證據的**標題實體集合**重不重疊」，
    那是在 `pulse-cluster.py` 裡問的——而抄一份比對邏輯過去，會得到兩份
    對「什麼算命中」看法可能不同的碼。

    抄一份的失敗形態跟 `lib/sources.py` 那次一模一樣：兩邊在字典沒動過的
    日子裡給一樣的答案，正好在有人加了一個帶邊界字元的新別名那天分岔，
    而且**不會有任何東西變紅**——兩邊各自都跑得很順，只是答案不一樣。

    所以搬到這裡，兩個消費者都 import 同一份。

簡繁正規化**不在**這一層（見 probe report 的已知缺口）：目前簡體別名不會命中
繁體寫法，反之亦然。轉載鏈判定會因此低估重疊——那是往「不判成轉載」倒，
也就是往保守方向倒，不是往做假門檻的方向倒。
"""
from __future__ import annotations

import re
import unicodedata

ENTITY_SECTIONS = ("companies", "product_lines", "infrastructure",
                   "frameworks", "technologies", "policies")


def normalize_text(s: str) -> str:
    """大小寫、全半形、空白。簡繁**不在**這裡處理，見 report 的已知缺口。"""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\u200b-\u200f\ufeff]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def build_matcher(entities: dict) -> list[tuple[str, str, str]]:
    """→ [(比對用字串, entity_id, term_type)]，長字串優先避免子字串誤配。"""
    table: list[tuple[str, str, str]] = []
    for sec in ENTITY_SECTIONS:
        for item in entities.get(sec) or []:
            terms = [item["canonical"], *(item.get("aliases") or [])]
            for t in terms:
                n = normalize_text(str(t))
                if n:
                    table.append((n, item["id"], item["term_type"]))
    table.sort(key=lambda x: len(x[0]), reverse=True)
    return table


def match_entities(text: str, table) -> tuple[list[tuple[str, str]], set[str]]:
    """→ (命中的 [(entity_id, term_type)], 實際命中的表面字串集合)"""
    n = normalize_text(text)
    hits, spans, surfaces = [], [], set()
    for term, eid, ttype in table:
        start = n.find(term)
        if start < 0:
            continue
        end = start + len(term)
        if any(s < end and start < e for s, e in spans):
            continue  # 已被更長的詞覆蓋
        # 純 ASCII 詞要求邊界，避免 "ray" 命中 "array"
        if term.isascii():
            before = n[start - 1] if start else " "
            after = n[end] if end < len(n) else " "
            if before.isalnum() or after.isalnum():
                continue
        spans.append((start, end))
        surfaces.add(term)
        hits.append((eid, ttype))
    return hits, surfaces


def entity_ids(text: str, table) -> frozenset[str]:
    """這段文字命中的 entity_id 集合。轉載鏈判定要的就是這個集合。

    回 frozenset 不回 list：呼叫端要的是集合運算（交集 / 聯集），
    而 `list(set)` 的順序在 CPython 每個行程都會重新隨機化——
    這條鏈對外的承諾是「同樣的輸入給同樣的輸出」（見 cluster.keyword_tokens）。
    """
    return frozenset(eid for eid, _ in match_entities(text, table)[0])
