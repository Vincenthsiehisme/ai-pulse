# -*- coding: utf-8 -*-
"""cluster.py — 去AI化聚類鍵：fingerprint / facet / 標題相似度
（移植 agent-pulse src/domain/clustering.ts，純規則、零 embedding、零 LLM）。

- titleTokens / title_similarity：標題 token 化 + Jaccard 近似重複
- keyword_tokens：標題 → 給人看的關鍵詞（有序、確定性；與上面那組刻意分家）
- event_fingerprint：model 家族正則 → "family:version"（同一版本聚成一個 Event 的主鍵）
- event_facet / event_facet_bucket：事件面向（release/capital/pricing/...）
- belongs_to_event：3b 聚類判定（同 fingerprint+facet+時間窗，或標題相似度 ≥ 門檻）
"""
from __future__ import annotations

import re
import unicodedata
from datetime import timezone

from .quality import parse_dt  # 共用日期解析

# 給 Jaccard 用的停用詞。**這份清單刻意留小。**
# 它參與 title_similarity，也就是參與「兩則標題算不算同一個 Event」的判定；
# 加一個詞就等於改聚類結果，屬於排名規則變更（紅線 9：要先改文件再改碼）。
# 所以不要為了「關鍵詞欄位太醜」順手往這裡加詞——那是下面那份的工作。
STOP_WORDS = {
    "a", "an", "and", "for", "in", "of", "on", "the", "to", "update", "with",
}

# 給 keywords 欄位用的停用詞。這欄只給人看、不參與任何判定，所以可以放心加大。
# 兩份分家的理由就是上面那段：共用一份的話，「調關鍵詞」會悄悄改掉聚類，
# 而且改完沒有任何一個測試會紅。
KEYWORD_STOP_WORDS = STOP_WORDS | {
    # 冠詞、介系詞、連接詞
    "as", "at", "by", "from", "into", "over", "than", "that", "this", "these",
    "those", "or", "but", "nor", "if", "then", "so", "up", "out", "off",
    "about", "after", "before", "during", "via", "per", "amid", "across",
    # 代名詞、限定詞
    "it", "its", "we", "our", "us", "you", "your", "they", "their", "them",
    "he", "she", "his", "her", "who", "whose", "which", "what", "all", "any",
    "both", "each", "more", "most", "other", "some", "such", "no", "not",
    # be 動詞與常見助動詞
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does",
    "did", "has", "have", "had", "can", "could", "will", "would", "may",
    "might", "should", "must",
    # 新聞稿套語（標題天天出現，指不到任何東西）
    "new", "how", "why", "when", "where", "now", "today", "here", "introducing",
    "announcing", "announces", "announce", "launching", "launches", "launch",
    "presenting", "unveils", "unveiling", "brings", "bringing", "meet",
    "read", "more", "blog", "post", "news", "release", "released", "using",
    "use", "make", "makes", "get", "gets", "way", "ways",
}

_TOKEN_STRIP = re.compile(r"[^a-z0-9一-鿿]+")


def _nfkc_lower(s):
    return unicodedata.normalize("NFKC", s or "").lower()


def title_tokens(title):
    text = _TOKEN_STRIP.sub(" ", _nfkc_lower(title))
    return {t for t in text.split() if len(t) > 1 and t not in STOP_WORDS}


def keyword_tokens(title, limit=8):
    """標題 → keywords[]：**依標題原順序**、去重、去虛詞、去純數字。

    不要用 `list(title_tokens(t))[:limit]` 代替這支。title_tokens 回傳的是 set，
    而 CPython 的字串雜湊預設每個行程都重新隨機化，於是 `list(set)` 的順序
    每跑一次就換一次——同一個標題、同一份程式碼，會得到不同的 keywords。

    實測（同一句標題跑五種 PYTHONHASHSEED）：
        'At AI Summit, South Korea Outlines Its AI Future With NVIDIA and Partners'
        → 五次五種結果；at / its 每次都在，nvidia 有兩次被擠出前八。
    也就是說被隨機丟掉的，剛好是唯一有指涉的那個詞。

    這條鏈對外的承諾是「同樣的輸入給同樣的輸出」。順序不確定就沒有這回事，
    所以這裡走 list 不走 set，截斷發生在過濾之後、順序固定之時。
    """
    out, seen = [], set()
    for tok in _TOKEN_STRIP.sub(" ", _nfkc_lower(title)).split():
        if len(tok) < 2 or tok.isdigit() or tok in KEYWORD_STOP_WORDS or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def title_similarity(left, right):
    a = title_tokens(left)
    b = title_tokens(right)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


# fingerprint —— model 家族正則（順序即優先序）。移植自 clustering.ts。
_FP_CJK = [("通义", "qwen"), ("月之暗面", "kimi"), ("智谱", "zhipu"), ("阶跃星辰", "stepfun")]
_FP_PATTERNS = [
    # 對 agent-pulse 的標註小修：原式 \d+ 讓 GPT-4o 塌成 gpt:4、與 GPT-4 撞鍵。
    # 加 o? 讓 4o / 4o-mini 保留字母後綴，不與 GPT-4 併成同一 Event。
    ("openai:gpt", re.compile(r"\bgpt[-\s]?(\d+(?:\.\d+)?o?(?:[-\s]?(?:mini|nano|pro))?)")),
    ("openai:o", re.compile(r"\bo(\d+(?:[-\s]?mini)?)")),
    ("google:gemini", re.compile(r"\bgemini[-\s]?(\d+(?:\.\d+)?(?:[-\s]?(?:flash|pro|ultra))?)")),
    ("anthropic:claude", re.compile(r"\bclaude[-\s]?(opus|sonnet|haiku)?[-\s]?(\d+(?:\.\d+)?)")),
    ("deepseek", re.compile(r"\bdeepseek[-\s]?(v\d+(?:\.\d+)?|r\d+)")),
    ("qwen", re.compile(r"\bqwen[-\s]?(\d+(?:\.\d+)?|coder|vl|max|plus)")),
    ("kimi", re.compile(r"\bkimi[-\s]?(k\d+(?:\.\d+)?|\d+(?:\.\d+)?)")),
    ("minimax", re.compile(r"\bminimax[-\s]?(m\d+|text[-\s]?\d+|video[-\s]?\d+)")),
    ("lingbot", re.compile(r"\blingbot[-\s]?(vla|world|video|vision)(?:[-\s]?(\d+(?:\.\d+)?))?")),
    ("longcat", re.compile(r"\blongcat[-\s]?(\d+(?:\.\d+)?)")),
    ("llama", re.compile(r"\bllama[-\s]?(\d+(?:\.\d+)?)")),
]
_WS = re.compile(r"\s+")


def event_fingerprint(title):
    """回 "family:version" 或 None（辨識不出具名模型版本時）。"""
    norm = _nfkc_lower(title)
    for zh, en in _FP_CJK:
        norm = norm.replace(zh, en)
    norm = re.sub(r"[–—_]", "-", norm)  # – — _ → -
    for family, pat in _FP_PATTERNS:
        m = pat.search(norm)
        if not m:
            continue
        parts = [g for g in m.groups() if g]
        tail = ":".join(parts)
        tail = _WS.sub("-", tail)
        return f"{family}:{tail}" if tail else family
    return None


# facet —— 事件面向關鍵字（順序即優先序）。移植自 clustering.ts。
_FACETS = [
    ("incident", re.compile(r"outage|incident|breach|漏洞|宕机|故障|事故|诉讼|lawsuit")),
    ("capital", re.compile(r"series [a-z]|funding|融资|估值|ipo|s-1|并购|acqui")),
    ("pricing", re.compile(r"price|pricing|降价|涨价|定价|subscription")),
    ("distribution", re.compile(r"available (?:in|for|on)|integration|integrat|microsoft 365|github copilot|进入.+copilot|接入|集成|分发")),
    ("benchmark", re.compile(r"benchmark|eval|测评|评测|score|榜单")),
    ("capability", re.compile(r"capabilit|reasoning level|performance|solv(?:e|es|ed|ing)|post-train|证明|推理等级|能力|自主训练")),
    ("release", re.compile(r"release|launch|introduc|announce|发布|推出|开源|available")),
]


def event_facet(title):
    norm = _nfkc_lower(title)
    for name, pat in _FACETS:
        if pat.search(norm):
            return name
    return "update"


def event_facet_bucket(facet):
    if facet == "update":
        return "release"
    if facet == "benchmark":
        return "capability"
    return facet


# ── eventability（移植 pipeline/cluster.ts eventabilityScore；決定一條 signal 能否「開一個新 Event」）──
_EVENTABILITY_TITLE = re.compile(
    r"releas(?:e|ed|es|ing)|launch(?:es|ed|ing)?|announc(?:e|ed|es|ing)|introduc(?:e|ed|es|ing)"
    r"|\bavailable\b|availability|general(?:ly)? available|preview(?:ing|ed)?|\badds?\b"
    r"|now supports?|support for|open[- ]source|funding|acqui(?:re|red|sition)|regulation|policy"
    r"|发布|推出|上线|可用|预览|新增|支持|开源|融资|并购|收购|监管|政策", re.I)
_RESEARCH_CONTRIB = re.compile(
    r"benchmark|dataset|framework|method|mechanism|architecture|evaluation|empirical|study|analysis|taxonomy"
    r"|基准|数据集|框架|方法|机制|架构|评测|实证|研究", re.I)
_DECISION_DOMAIN = re.compile(
    r"large language model|\bLLMs?\b|agent|reasoning|long[- ]context|coding|code model|multimodal"
    r"|vision[- ]language|training|inference|alignment|robot|memory|context compression|tool use|causal"
    r"|智能体|推理|长上下文|编码|多模态|训练|对齐|机器人|记忆|上下文压缩|工具使用|因果", re.I)

# 本 vault 的 source_category → 是否屬「實質發布者」bucket（對映 agent-pulse 的 frontier-lab/company/... 判斷）
_SUBSTANTIVE_CATEGORIES = {"vendor", "research", "framework", "regulator"}


def is_decision_relevant_research(title, summary):
    content = f"{title or ''} {summary or ''}"
    return (len((summary or "").strip()) >= 160
            and bool(_RESEARCH_CONTRIB.search(content))
            and bool(_DECISION_DOMAIN.search(content)))


def eventability_score(rec, source):
    """rec = signals-scored 記錄（含 effective_role/quality）；source = sources.yaml 條目。
    回 0..100。<70 者不足以開新 Event（會被 defer）。aggregator → 0。
    """
    if source is None:
        return 0
    role = rec.get("effective_role")
    scat = source.get("source_category")
    if role == "aggregator" or scat == "aggregator":
        return 0
    title = rec.get("title") or ""
    summary = rec.get("summary") or ""
    research_source = role == "research"
    decision_research = research_source and is_decision_relevant_research(title, summary)
    try:
        tier = int(source.get("tier"))
    except (TypeError, ValueError):
        tier = 3
    score = 25 if tier == 1 else (10 if tier == 2 else 0)
    if role in ("primary", "policy"):
        score += 20
    elif role == "research":
        score += 10
    if scat in _SUBSTANTIVE_CATEGORIES:
        score += 15
    if decision_research:
        score += 25
    if _EVENTABILITY_TITLE.search(title):
        score += 20
    if event_fingerprint(title):
        score += 20
    q = rec.get("quality")
    if isinstance(q, (int, float)) and q >= 70:
        score += 10
    if research_source and not decision_research:
        return min(65, score)
    return min(100, score)


def belongs_to_event(cand_title, cand_published, event_title, event_happened, threshold=0.46):
    """3b 聚類判定（移植 belongsToEvent）。cand_*/event_* 為標題與時間字串。"""
    cp = parse_dt(cand_published)
    ep = parse_dt(event_happened)
    if cp is None or ep is None:
        return False
    hours = abs((cp - ep).total_seconds()) / 3600.0
    if hours > 21 * 24:
        return False
    cfp = event_fingerprint(cand_title)
    efp = event_fingerprint(event_title)
    if cfp and cfp == efp:
        cf = event_facet_bucket(event_facet(cand_title))
        ef = event_facet_bucket(event_facet(event_title))
        return cf == ef and hours <= (7 if cf == "incident" else 21) * 24
    return hours <= 96 and title_similarity(cand_title, event_title) >= threshold
