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


# ---------------------------------------------------------------- 獨立性計算
# 框架規則第 5 條：獨立性按 source + author + media group 判斷。
# 2026-07-26 之前這裡只做了 media group 那一半——pulse-cluster.py 的
# `independent = len({media_group})`。那個算法有一個**還沒發生但一定會發生**的漏洞：
#
#   同一個人在兩個地方發表（Karpathy 的 blog + Karpathy 的 YouTube），
#   media_group 是兩個不同的字串，於是一個人被算成兩個獨立來源，
#   而「heat ≥70 需 ≥2 獨立來源」這道門就被我們自己的設定檔開了。
#
# 今天還沒破，是因為 8 條 KOL 剛好一人一站。這種「靠巧合成立的正確」
# 會在下一次加來源時無聲失效，而且沒有任何測試會紅。
#
# 修法不是把 key 從 media_group 換成 person_id——那會反過來放寬：
# 同一刊物的兩位作者（Interconnects 的 Nathan Lambert 與客座 Florian Brand，
# 實測語料裡真的有）person_id 不同，會從 1 變成 2。
#
# 正確語意是**兩個條件任一成立就該合併**，也就是連通分量：
#   同一個人 → 合併（一個人不會因為換平台變成兩個獨立聲音）
#   同一個媒體集團 → 合併（同一個編輯台不是兩個獨立聲音）
# 遞移是刻意的，且只往保守方向倒：A 在 X、Y 發表，B 也在 Y 發表，
# 三者合併成 1。寧可低估獨立性，不可高估——高估就是把門檻做假。
# ------------------------------------------------------------ 轉載鏈（跨語言）
# 規格見 references/evidence-tiers.md〈evidence.translation_chain〉。
# 這一支不讀設定檔、不碰磁碟、不算實體——實體集合由呼叫端算好傳進來
# （lib/entities.entity_ids），所以它在沒有字典、沒有外網的環境也測得動。
def suspected_reposts(items, cfg=None):
    """判斷同一則 Event 裡哪幾條證據是別人的翻譯轉載。

    items: list of dict，每項要有
        lang        來源語言（`sources.yaml` 的 language），缺就是缺
        title       證據標題（只用來給呼叫端算 entities，本函式不看）
        entities    標題命中的 entity_id 集合（frozenset）
        published   發布時間（datetime，aware 或 None）
        tier        來源 tier（挑原文用）
        fingerprint 標題的模型版本鍵，或 None
    cfg: gate.yaml 的 evidence.translation_chain 那一塊。

    回傳被判成轉載的 index 集合（每一組保留一條原文）。

    三個條件同時成立才判：語言不同、時間差在窗內、實體集合 Jaccard ≥ 門檻。
    外加一個否決：兩邊都有 fingerprint 且不相等 → 不可能互為翻譯。

    **缺資料一律不判**，也就是往「維持原本算法」倒。這跟獨立性計算「寧可低估」
    的方向相反，是刻意的：捏造一個「它們是同一篇」的結論，比漏抓一次更難發現
    ——漏抓的那則停在 review 等人看，誤判的那則安靜地少一個聲音，而且沒有任何
    欄位會顯示它被扣過。
    """
    cfg = cfg or {}
    if not cfg.get("enabled"):
        return set()
    try:
        min_overlap = float(cfg.get("entity_overlap_min", 0.8))
        window = float(cfg.get("window_hours", 48))
    except (TypeError, ValueError):
        return set()

    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    linked = False
    for i in range(n):
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            la = (a.get("lang") or "").strip().lower()
            lb = (b.get("lang") or "").strip().lower()
            if not la or not lb or la == lb:
                continue
            pa, pb = a.get("published"), b.get("published")
            if pa is None or pb is None:
                continue
            if abs((pa - pb).total_seconds()) / 3600.0 > window:
                continue
            fa, fb = a.get("fingerprint"), b.get("fingerprint")
            if fa and fb and fa != fb:
                continue          # 不同版本，不可能互為翻譯
            ea = a.get("entities") or frozenset()
            eb = b.get("entities") or frozenset()
            if not ea or not eb:
                continue
            union = len(ea | eb)
            if not union or len(ea & eb) / union < min_overlap:
                continue
            ra, rb = find(i), find(j)
            if ra != rb:
                parent[ra] = rb
            linked = True

    if not linked:
        return set()

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    reposts = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        # 原文＝發布最早的；同時間取 tier 小的；再同就取證據順序在前的。
        # 三段都是確定性的，沒有任意 tie-break——否則同一份輸入會給不同答案。
        def rank(idx):
            it = items[idx]
            pub = it.get("published")
            return (pub.timestamp() if pub else float("inf"),
                    _as_int(it.get("tier"), 99), idx)
        keep = min(members, key=rank)
        reposts.update(m for m in members if m != keep)
    return reposts


def verbatim_reposts(items, cfg=None):
    """同語言的逐字轉載。回傳被判成轉載的 index 集合（每一組保留一條原文）。

    規格見 references/evidence-tiers.md〈`evidence.verbatim_repost`〉與
    references/attach-rule.md〈順序〉。

    ## 為什麼 suspected_reposts 蓋不到這一格

    那一支的第一個條件就是「語言不同」——它認的是**跨語言翻譯**。
    2026-08-11 實測：

        同語言（en/en，逐字轉載）→ 空集合＝沒攔到
        跨語言（en/zh）           → {1}

    而 P0-e 量到，現行 attach 規則唯一黏得上的兩篇第三方後續，**兩篇都是
    標題一字不差的逐字轉載**。也就是說系統唯一收得到的「第二個獨立來源」，
    正好是最不獨立的那一種，而防線在旁邊看著。

    ## 判準只有兩條，刻意不抄 suspected_reposts 那三條

    標題相似度 ≥ `title_similarity_min` 且時間差在 `window_hours` 內。

    不做實體 Jaccard：相似度 0.95 以上的兩個標題，實體集合必然幾乎相同，
    再算一次只是把同一件事量兩遍。跨語言那支需要實體，是因為中英文標題的
    token 交集趨近於零、相似度那條路走不通——兩支的判準不同不是不一致，
    是它們在對付不同的東西。

    同一條來源的兩筆不必特別處理：`independent_voices` 本來就會把它們併成
    一個聲音，這裡再判一次不會改變任何數字。
    """
    cfg = cfg or {}
    if not cfg.get("enabled"):
        return set()
    try:
        min_sim = float(cfg.get("title_similarity_min", 0.95))
        window = float(cfg.get("window_hours", 168))
    except (TypeError, ValueError):
        return set()

    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    linked = False
    for i in range(n):
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            ta, tb = (a.get("title") or "").strip(), (b.get("title") or "").strip()
            # 缺標題一律不判——往「維持原本算法」倒，同 suspected_reposts。
            # 捏造一個「它們是同一篇」的結論比漏抓一次更難發現。
            if not ta or not tb:
                continue
            pa, pb = a.get("published"), b.get("published")
            if pa is None or pb is None:
                continue
            if abs((pa - pb).total_seconds()) / 3600.0 > window:
                continue
            if title_similarity(ta, tb) < min_sim:
                continue
            ra, rb = find(i), find(j)
            if ra != rb:
                parent[ra] = rb
            linked = True

    if not linked:
        return set()
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    reposts = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        # 原文的選法跟 suspected_reposts 一模一樣：最早發布 → tier 小 → 順序在前。
        # 三段都是確定性的，同一份輸入永遠給同一個答案。
        def rank(idx):
            it = items[idx]
            pub = it.get("published")
            return (pub.timestamp() if pub else float("inf"),
                    _as_int(it.get("tier"), 99), idx)
        keep = min(members, key=rank)
        reposts.update(m for m in members if m != keep)
    return reposts


def _as_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def independent_voices(items):
    """items: iterable of (source_id, source_cfg)。回傳獨立聲音數（連通分量數）。

    person_id 全空時，結果與舊版 `len({media_group})` 完全相同——
    這條性質有測試釘住，是本次改動可以安全上線的依據。
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:      # 路徑壓縮
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    nodes = []
    for idx, (sid, cfg) in enumerate(items):
        cfg = cfg or {}
        node = ("item", idx)
        find(node)
        nodes.append(node)
        anchors = []
        mg = str(cfg.get("media_group") or "").strip()
        pid = str(cfg.get("person_id") or "").strip()
        if mg:
            anchors.append(("media_group", mg))
        if pid:
            anchors.append(("person", pid))
        if not anchors:
            # 兩個欄位都空 → 退回 source_id，維持舊行為（每條來源自成一組）。
            anchors.append(("source", str(sid or f"#{idx}")))
        for a in anchors:
            union(node, a)
    return len({find(n) for n in nodes})
