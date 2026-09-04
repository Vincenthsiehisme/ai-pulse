#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-cluster.py — Sprint 3b：signals → Event（純規則，零 LLM）。

讀 _probe/<day>/signals-scored.jsonl（3a 產）+ _config/{sources,entities,gate}.yaml，
依「同 fingerprint+facet+時間窗 / 或標題相似度 ≥0.46」把 signals 聚成 Event，
綁定證據、算 confidence/heat/independent_sources/primary_evidence，
寫 Events/<id>.md（六層標題 + 待編輯佔位；prose 留給 3c enrich 填）。
跨日：會讀既有 Events/*.md，新 signal 可 attach 到昨天的 Event 並重評分。

紅線：獨立數 = 「同人或同媒體集團就合併」的連通分量（框架規則第 5 條），
      比 agent-pulse 原碼嚴。實作見 lib/cluster.independent_voices()。
用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-cluster.py [--day YYYY-MM-DD] [--dry-run]
依賴：PyYAML。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cluster, entities as entities_lib, scoring  # noqa: E402
from lib import coverage as coverage_lib  # noqa: E402  observed/backfilled 判準單一真相源
from lib.sources import SECTIONS  # noqa: E402  分節清單單一真相源
from lib.notes import PLACEHOLDER  # noqa: E402  單一來源，見 lib/notes.py
from lib import notes  # noqa: E402  外科式改單一 frontmatter 欄位（patch_coverage）
from lib.quality import authority_score_from_tier, parse_dt  # noqa: E402
from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md

import yaml  # noqa: E402


def load_first_fetch(probe):
    """`_probe/state.json` → `{source_id: first_fetch_at}`。缺檔或壞檔回空 dict。

    這是**既有真相源**：`pulse-probe` 寫、`pulse-monitor` 的
    `silent_pending_clock` 讀（`fix/coverage-uses-own-clock` 就是把沉默判準改成
    吃這一格）。這裡是第三個消費者，讀同一份，不另存一份。

    讀不到就回空 dict，而空 dict 會讓每一則判成 `unknown`——不是 `observed`。
    設定檔壞掉的時候規則要變嚴，不是變鬆（跟 `lib/dictgaps.thresholds()` 同一條）。
    """
    p = probe / "state.json"
    if not p.exists():
        return {}
    try:
        st = json.loads(p.read_text("utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(st, dict):
        return {}
    return {k: (v or {}).get("first_fetch_at")
            for k, v in st.items() if isinstance(v, dict)}


def load_sources(cfg):
    raw = yaml.safe_load((cfg / "sources.yaml").read_text("utf-8"))
    out = {}
    for key in SECTIONS:
        for s in (raw.get(key) or []):
            if isinstance(s, dict) and s.get("id"):
                out[s["id"]] = s
    return out


def load_entities(cfg):
    """id → (canonical, term_type, 所屬公司)。用於 Event 的 company 初判。

    ## 2026-08-13：這支函式讀了兩個不存在的東西

    在此之前它有兩個各自獨立的錯，兩個都不會讓任何東西變紅：

    **一、分節清單是手寫的第二份。** 它自己列
    `("companies", "product_lines", "products", "technologies", "policy")`，
    而 `entities.yaml` 的實際分節是 `companies / product_lines / infrastructure
    / frameworks / technologies / policies`。於是 `products` 與 `policy`
    永遠讀到空的，`infrastructure`（7）/ `frameworks`（12）/ `policies`（4）
    整批沒被載入——**104 個實體只載了 70 個**。

    而單一真相源一直都在：`lib/entities.ENTITY_SECTIONS`，`build_matcher()`
    用的就是它。同一份清單兩個消費端、只釘住一個——這是 `SECTIONS`、
    `RUN_LIFECYCLES` 之後第三次同一個病。

    **二、公司欄位讀成 `parent`。** `entities.yaml` 的 23 個 product_line
    **全部**帶著 `company: <公司 id>`，而且每一個都指到存在的公司。
    沒有任何一個有 `parent`。

    後果是 `infer_company()` 的第二段（product_line → 往上解析到公司）
    **從來沒有執行成功過**——它是死碼。所有只命中產品線的訊號都落到
    `"industry"` 兜底，然後被 gate 掛上 `generic_entity`。

    實測：132 則事件裡 12 則是 `company: industry`，其中 **7 則**的
    entity_hits 有產品線可解（6 則 claude → Anthropic、1 則 grok → xAI）。
    剩下 5 則是真的一個實體都沒命中，那不是這個 bug。

    **設定檔一直是對的，是讀的人拿錯鑰匙。**
    """
    p = cfg / "entities.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    out = {}
    for key in entities_lib.ENTITY_SECTIONS:
        for e in (raw.get(key) or []):
            if isinstance(e, dict) and e.get("id"):
                out[e["id"]] = (e.get("canonical") or e["id"], e.get("term_type"),
                                e.get("company"))
    return out


def attach_rank(title, event):
    """一個候選有多好。→ `(指紋一致, facet 一致, 標題相似度)`，大的贏。

    **時間距離刻意不在這個鍵裡面**，而《修正版》的建議把它排在第 4 位。
    理由是實測（2026-08-12，934 訊號 × 125 事件）：

        訊號「Claude For Teachers」對 9 則 Claude 系列事件全部 sim=0.33，
        加上時間距離之後會挑出「Claude Sonnet 4.6」——理由是差 0.2 小時。

    一個師資產品公告，用 0.2 小時的時間差挑一則模型發布事件。**那是把
    first-match 的任意性換成另一種任意性，而且看起來更精確。**

    更根本的：時間已經是硬閘了（96 小時 / 21 天，見 belongs_to_event）。
    再拿它當偏好，是把同一個訊號用兩次——閘後面的每一個候選，時間都已經
    「夠近」了，那之後誰更近不再是證據。
    """
    cfp, efp = cluster.event_fingerprint(title), cluster.event_fingerprint(event.title)
    cf = cluster.event_facet_bucket(cluster.event_facet(title))
    ef = cluster.event_facet_bucket(cluster.event_facet(event.title))
    return (1 if (cfp and cfp == efp) else 0,
            1 if cf == ef else 0,
            round(cluster.title_similarity(title, event.title), 6))


def attach_target(title, published, events, sim_min):
    """這則 signal 該掛到哪個既有 Event，沒有或分不出來就回 None。純函式。

    抽出來是為了讓門檻可測。`sim_min` **刻意沒有預設值**：這樣「忘記把 gate.yaml
    的門檻傳進來」會在呼叫的當下丟 TypeError，而不是安靜地退回某個內建數字繼續跑。
    一個讀得到、註解也寫了消費者、實際上沒被傳進去的門檻，就是這個 repo 抓過
    很多次的假旋鈕——把它做成語法上不可能，比再加一條測試可靠。

    ## 2026-08-12：從「第一個符合的」改成「最好的那個，分不出來就不掛」

    在此之前這裡是 `next(c for c in events if belongs_to_event(...))`。
    `events` 來自 `sorted(Events/*.md)`，檔名是 `evt-<日期>-<hash>`，所以
    「第一個符合的」實際上等於**最舊的那個符合的**——而「最舊」跟「最像」
    沒有任何關係。

    這不是不確定性（同樣輸入給同樣輸出，這條鏈仍然是 deterministic 的），
    是**確定地挑錯**。差別在於：不確定性可以用「跑兩次比對」抓，
    確定地挑錯跑一百次都一樣綠。

    ### 誠實話：排名這一半，今天量不到任何效果

    實測 934 訊號 × 125 事件：`first-match ≠ 最佳候選` 的筆數是 **0**。
    身分否決（`belongs_to_event` 的 fingerprint veto）已經把排名會修的那些
    全修掉了。**這一半是結構修正，不是量出來的修正**——留著它是因為
    「挑檔名最前面的」本來就不是一個判斷，而且候選蒐集本來就是平手守門的前置。

    ### 平手不掛，而且門檻不開成旋鈕

    語意鍵完全相同的候選有兩個以上 → 回 None，這則 signal 去開自己的 Event
    或被 defer。**寧可少 attach，也不要錯 attach**：漏掉的代價是少一個聲音，
    掛錯的代價是 `independent_sources` 記一個不存在的來源，而那個數字會進
    frontmatter、進看板、進 KPI，事後分不出哪些是虛的。

    《修正版》建議 `attach_ambiguity_margin: 0.08`。**這一輪不做成可調的門檻**：
    實測整份語料只有一筆多候選（`Claude For Teachers`，9 路平手，差距 0.00），
    n=1 的資料校準不出 0.02 跟 0.30 哪個對。一個沒有資料支撐的旋鈕，
    日後會被當成校準過的旋鈕來調——同 `coverage_gap.min_answers` 那條。
    等真的出現 0.61 / 0.59 那種形狀，再把它變成可調的。
    """
    cands = [c for c in events if cluster.belongs_to_event(
        title, published, c.title, c.happened_at, sim_min)]
    if not cands:
        return None
    best = max(attach_rank(title, c) for c in cands)
    tied = [c for c in cands if attach_rank(title, c) == best]
    return tied[0] if len(tied) == 1 else None


def normalize_url_loose(u):
    """粗略正規化，只用來判斷「是不是同一顆 URL」——不進 frontmatter，不做完整 canonical。

    去 `www.`、去結尾斜線。跟 `pulse-probe.py` 的 `canonical_url()` 不是同一支
    （那支還處理 tracking query string），這裡只需要判斷兩個 URL 是不是同一個
    資源，用不到那麼多。
    """
    if not u:
        return ""
    s = urlsplit(u)
    host = s.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = s.path.rstrip("/") or "/"
    return f"{host}{path}"


def attach_by_url(sig_url, events):
    """訊號的 URL 跟哪個既有 Event 的證據是同一顆。回那個 Event 或 None。

    規格見 `references/attach-rule.md`〈同一顆 URL 二次進站〉：這條刻意排在
    `attach_target()` 判不出來之後才問，而且**不受 21 天窗口或標題相似度門檻
    限制**——URL 相同不是「像」，是同一個資源被觀測了兩次。典型觸發：來源的
    sitemap lastmod 被站方後補更新，同一篇文章隔了一個多月又跑進當天語料，
    `published` 因此跳到 35 天後，撞穿 21 天硬上限，被誤判成新故事。

    `Event.add_evidence()` 本來就用 `(source_id, url)` 去重，所以這裡 attach
    之後那筆證據會被原地吞掉、`ev.dirty` 不會被設成 True——同一顆 URL 第二次
    出現，不該讓任何東西動。
    """
    key = normalize_url_loose(sig_url)
    if not key:
        return None
    for ev in events:
        for e in ev.evidence:
            if normalize_url_loose(e.get("url", "")) == key:
                return ev
    return None


def load_title_similarity_min(cfg):
    """gate.yaml 的 `cluster.title_similarity_min`。缺檔／缺值／壞值 → 回舊的 0.46。

    退回**舊值**不是退回新值，方向是刻意的：設定檔壞掉的時候規則要變嚴，
    不是變鬆（同 `lib/dictgaps.thresholds()`）。一個在 YAML 打錯字的那天
    悄悄放寬聚類的系統，會把汙染混進 independent_sources 而沒有人知道。
    """
    p = cfg / "gate.yaml"
    if not p.exists():
        return cluster.DEFAULT_TITLE_SIMILARITY_MIN
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    v = ((raw.get("cluster") or {}).get("title_similarity_min"))
    try:
        return float(v)
    except (TypeError, ValueError):
        return cluster.DEFAULT_TITLE_SIMILARITY_MIN


def load_verbatim_repost_cfg(cfg):
    """gate.yaml 的 `evidence.verbatim_repost`。缺檔／缺區塊 → 回空 dict。

    跟上面那支同一條原則：**設定檔讀不到不可以退回「照判」**。
    一條在設定檔壞掉時反而更積極扣分的規則，會在最沒人注意的那天改變結果。
    """
    p = cfg / "gate.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    return ((raw.get("evidence") or {}).get("verbatim_repost") or {})


def load_translation_chain_cfg(cfg):
    """gate.yaml 的 evidence.translation_chain。缺檔／缺區塊 → 回空 dict。

    回空 dict 等於 `enabled` 不成立，也就是這條規則不判——跟設定檔明寫
    `enabled: false` 走同一條路。**設定檔讀不到不可以退回「照判」**：
    一條在設定檔壞掉時反而更積極扣分的規則，會在最沒人注意的那天改變結果。
    """
    p = cfg / "gate.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    return ((raw.get("evidence") or {}).get("translation_chain") or {})


def load_entity_table(cfg):
    """命名實體字典 → 比對表（lib/entities.build_matcher）。缺檔回空 list。"""
    p = cfg / "entities.yaml"
    if not p.exists():
        return []
    return entities_lib.build_matcher(yaml.safe_load(p.read_text("utf-8")) or {})


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(title):
    s = _SLUG_STRIP.sub("-", (title or "").lower()).strip("-")
    return s[:60] or "event"


def infer_company(entity_hits, entities):
    # 1) 直接命中 company 型別
    for hid in entity_hits or []:
        canon, ttype, _ = entities.get(hid, (None, None, None))
        if ttype == "company":
            return canon
    # 2) 命中產品線／基礎設施／框架 → 往上解析到所屬公司（例：gemini → Google DeepMind）。
    #    第三格來自 entities.yaml 的 `company:` 欄位。2026-08-13 之前 load_entities
    #    讀的是 `parent`，而那個欄位一個都不存在——這一整段是死碼。見該函式的說明。
    for hid in entity_hits or []:
        canon, ttype, owner = entities.get(hid, (None, None, None))
        if owner:
            pcanon, pttype, _ = entities.get(owner, (None, None, None))
            if pttype == "company":
                return pcanon
    return "industry"  # 泛稱 → 會觸發 generic_entity blocker，待 enrich 修正


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[3:end]) or {}
    body = text[end + 4:]
    return fm, body


class Event:
    def __init__(self, eid, slug, title, happened_at, fingerprint=None, facet=None):
        self.id = eid
        self.slug = slug
        self.title = title
        self.happened_at = happened_at
        self.fingerprint = fingerprint
        self.facet = facet
        self.evidence = []  # list of {source_id, url, title, relevance}
        self.company = "industry"
        self.keywords = []
        self.dirty = True  # 需要寫檔
        self.scores = None
        self.path = None
        self.enriched = False   # 已 enrich（3c）→ 重寫時只更新 frontmatter 分數，不動 prose body
        self.orig_body = None   # reload 時保存的原 body（enriched 時用來保留潤好的 prose）
        self.fm = None          # reload 時保存的完整 frontmatter
        # 這則 Event **進到我們庫裡**的時刻，跟 happened_at（外面世界發生的時刻）
        # 是兩件事。寫一次就不再動；規格見 references/event-timestamps.md。
        self.ingested_at = None
        # 標題的中文譯文與它綁的原文雜湊，由潤稿端寫（pulse-title-apply.py）。
        # 跟 ingested_at 同樣是 sticky 欄位：event_markdown() 會整份重寫
        # frontmatter，沒被明確帶過去的欄位會被抹掉——那正是
        # fix/backfill-flag-erased-by-second-run 修的坑，這裡是第三個踩到它的欄位。
        self.title_zh = None
        self.title_zh_src = None
        # 這則 Event 是**修復腳本補寫的**，不是這條鏈自己長出來的。
        # 值是那支遷移的標籤（例：identity-repair-2026-08-12），沒有就是 None。
        #
        # 為什麼不共用下面那格的 `coverage: backfilled`：那一格說的是
        # 「事情發生時我們的來源還沒開始觀測」，是 lib/coverage.py 每班重算的
        # 推導欄位。一個欄位兩個意思正是這個 repo 一直在抓的病——而且這兩個意思
        # 會同時成立（補寫的事件當時通常真的看得到，只是被歸錯了檔）。
        #
        # 跟 ingested_at / title_zh 同樣 sticky。這是第四個踩到那個坑的欄位，
        # 所以 selftest 有一條釘住它「跑第二輪還在」。
        self.recovered_by = None
        # 事情發生時我們看不看得到（observed / backfilled / unknown）。
        # 跟上面那批 sticky 欄位**相反**：這一格每班從 _probe/state.json 重算，
        # reload 時刻意不從 frontmatter 讀回來——寫死之後，來源的 first_fetch_at
        # 修正了它也不會跟著改。判準見 lib/coverage.py。
        self.coverage = coverage_lib.UNKNOWN

    def add_evidence(self, source_id, url, title, relevance, published=None):
        """新增一條證據。`title` 與 `published` 是**判斷用的欄位，不是展示用的**。

        規格見 references/evidence-tiers.md〈證據記錄要留下什麼〉。簡短版：
        跨語言轉載鏈判定要問「這兩條的標題實體重不重疊、發布時間差幾小時」，
        兩個問題都只有在證據記錄自己帶著 title 與 published 時才回答得出來。
        在此之前這兩個值只活在建立那一班的記憶體裡，重新讀檔就沒了。
        """
        if any(e["source_id"] == source_id and e["url"] == url for e in self.evidence):
            return
        self.evidence.append({"source_id": source_id, "url": url, "title": title,
                              "relevance": relevance, "published": published})
        self.dirty = True


_EVIDENCE_FIELDS = ("source_id", "url", "title", "relevance", "published",
                    "suspected_repost")


def evidence_frontmatter(evidence):
    """證據記錄 → frontmatter 的 list。欄位白名單，順序固定。

    規格見 references/evidence-tiers.md。白名單是刻意的：證據記錄不是語料的
    副本，只留下**判斷會用到的**那幾個欄位（紅線 6，原始內容只進 _evidence_raw/）。
    順序固定是為了 diff——欄位順序每跑一次換一次的話，`git diff` 上每則 Event
    都會看起來像被改過。
    """
    return [{k: e.get(k) for k in _EVIDENCE_FIELDS} for e in evidence]


def evidence_from_frontmatter(items):
    """frontmatter 的 `evidence[]` → 記憶體裡的證據記錄。跨日 attach 會走這條路。

    `title` 缺席時填 `None`，**不填 url**。舊版填的是 `e.get("url")`，於是重新
    讀檔之後每一條證據的「標題」都是它自己的網址：body 的證據清單會把同一個
    網址印兩次，而任何拿 `title` 做判斷的規則（轉載鏈的實體重疊）會拿到一串
    網址去比對，比出來的相似度是假的、而且看起來很正常。

    缺就是缺——量不到不可以寫成一個看起來像值的東西（紅線 8）。
    規格見 references/evidence-tiers.md〈證據記錄要留下什麼〉。
    """
    out = []
    for e in (items or []):
        out.append({"source_id": e.get("source_id"), "url": e.get("url"),
                    "title": e.get("title"), "relevance": e.get("relevance", 0),
                    "published": e.get("published")})
    return out


def evidence_line(e):
    """body 的〈證據〉那一行。標題缺席時只印網址，不把網址印成標題。

    舊版是 `— {title}（{url}）`，而重新讀檔之後 title 就是 url，於是同一個網址
    被印兩次、中間夾一個破折號，看起來像「這篇文章的標題就叫 https://…」。
    """
    title = (e.get("title") or "").strip()
    head = f"- [[Sources/{e['source_id']}|{e['source_id']}]] — "
    if not title or title == (e.get("url") or "").strip():
        return f"{head}（標題未留存）{e.get('url') or ''}"
    return f"{head}{title}（{e.get('url') or ''}）"


def mark_reposts(ev, sources, tc_cfg, ent_table, vr_cfg=None):
    """在證據上標 `suspected_repost`。回傳被標記的 index 集合。

    規格見 references/evidence-tiers.md〈evidence.translation_chain〉。
    每一輪都重算並重寫這個欄位——它是判斷的產物，不是人填的事實，
    留著上一輪的結論會在字典或門檻改動之後變成一句沒人維護的舊話。
    """
    rows = []
    for e in ev.evidence:
        src = sources.get(e["source_id"], {}) or {}
        title = e.get("title") or ""
        rows.append({
            "title": title,           # verbatim_reposts 用；suspected_reposts 不看
            "lang": src.get("language"),
            "tier": src.get("tier"),
            "published": parse_dt(e.get("published")),
            # 實體集合走命名實體字典，不走 token 交集——中英文標題的 token
            # 交集趨近於零，而字典的 aliases 兩種語言都收。
            "entities": entities_lib.entity_ids(title, ent_table) if (title and ent_table) else frozenset(),
            "fingerprint": cluster.event_fingerprint(title) if title else None,
        })
    # 兩支合起來才是完整的「這不是第二個聲音」：一支認跨語言翻譯，
    # 一支認同語言逐字轉載。少了後者，2026-08-11 量到的那兩篇（相似度 1.00）
    # 會實實在在地讓 independent_sources 從 1 變成 2。
    flagged = cluster.suspected_reposts(rows, tc_cfg)
    flagged = flagged | cluster.verbatim_reposts(rows, vr_cfg)
    for idx, e in enumerate(ev.evidence):
        e["suspected_repost"] = idx in flagged
    return flagged


def apply_coverage(ev, first_fetch):
    """算這則的 `coverage`。→ 跟磁碟上寫的**不一樣**嗎。

    **只算，不標髒。** 標不標髒由 `main()` 決定，因為 `ev.dirty` 在這支腳本裡
    的意思是「整份重寫這個檔」，而整份重寫的代價遠不只多一個欄位：

    - `event_markdown()` 會把 `status` 寫死回 `review`，且不帶 `published_at` /
      `dropped_at` / `drop_reason` / `enriched` / `summary`——一則**還沒潤稿的
      `dropped` 事件**會就這樣被復活成 review，人工判定的「不追」消失。
    - 兩條寫檔路徑都會拿**今天的** `ref_now` 重算所有分數。實測一次遷移會讓
      52 則的 `value` / `freshness` 全部位移，而那不是「加一個欄位」該做的事。

    所以只有 coverage 變了的那些走 `patch_coverage()`（外科式改一格），
    真的有新證據的才整份重寫。

    回傳「跟磁碟上不一樣」，不是「跟記憶體裡的預設值不一樣」。後者聽起來一樣、
    但每一則都會回 True——reload 不從 frontmatter 讀這一格，記憶體裡永遠是
    UNKNOWN 起跳。第一版就是這樣，摘要行印「52 有變」而實際寫檔 0 筆。
    """
    ev.coverage = coverage_lib.coverage_of(ev.happened_at, ev.evidence, first_fetch)
    return (ev.fm or {}).get("coverage") != ev.coverage


def patch_coverage(path, coverage):
    """只改 frontmatter 的 `coverage` 一格，其餘（含 body）原樣保留。

    走 `parse_note` → 改 dict → `dump_frontmatter`，跟 `pulse-gate.py` 與
    `pulse-enrich-apply.py` 同一條路——那條路會保留所有它不認識的欄位。
    `event_markdown()` 那條是**從頭重建**，這一格不值得付那個代價。
    """
    fm, body = notes.parse_note(path.read_text("utf-8"))
    if fm is None:
        return False
    fm["coverage"] = coverage
    body = body if body.startswith("\n") else "\n" + body
    path.write_text(f"---\n{notes.dump_frontmatter(fm)}\n---{body}", encoding="utf-8")
    return True


def rescore(ev, sources, ref_now, tc_cfg=None, ent_table=None, first_fetch=None,
            vr_cfg=None):
    reposts = mark_reposts(ev, sources, tc_cfg, ent_table, vr_cfg)
    # gate.yaml 的 excluded_from 真的被讀：把它寫成一個「改了也沒效果」的清單，
    # 就是這個 repo 一直在抓的假旋鈕。清單裡的 heat 今天是**由 independent_sources
    # 承擔的**（heat 的證據面輸入只有獨立來源數，metrics 還是 []），社群線接上那天
    # 要回來把它單獨接一次——那件事寫在 references/evidence-tiers.md。
    # 兩支轉載守門的排除清單取**聯集**。它們排除的語意相同（那一條不是第二個
    # 聲音），分開設定沒有意義。真要分開的話，得先讓 mark_reposts 回報是哪一支
    # 判的——在那之前，聯集是唯一不會靜靜漏掉一邊的選法。
    excluded = (set((tc_cfg or {}).get("excluded_from") or [])
                | set((vr_cfg or {}).get("excluded_from") or []))
    authority_scores, tiers, voices, primary = [], [], [], 0
    for idx, e in enumerate(ev.evidence):
        src = sources.get(e["source_id"], {})
        tier = src.get("tier")
        try:
            tier = int(tier)
        except (TypeError, ValueError):
            tier = 3
        authority_scores.append(authority_score_from_tier(tier))
        tiers.append(tier)
        # 轉載鏈：被判成別人的翻譯的那一條，不進獨立性計算
        # （gate.yaml 的 excluded_from 第一項）。authority 與 primary 照算——
        # 那兩項不在排除清單裡，翻譯的權威性由它自己的 tier 表達。
        if not (idx in reposts and "independent_sources" in excluded):
            voices.append((e["source_id"], src))
        role = src.get("role")
        scat = src.get("source_category")
        if tier == 1 and role != "aggregator" and scat != "aggregator":
            primary += 1
    # 紅線第 5 條：source + author + media group。2026-07-26 之前這裡只算了
    # media group 那一半，同一個人在兩個站台發表會被當成兩個獨立來源。
    # 判定搬到 lib/cluster.independent_voices()（連通分量），理由寫在該函式上方。
    independent = cluster.independent_voices(voices)
    happened = parse_dt(ev.happened_at)
    age_hours = max(0.0, (ref_now - happened).total_seconds() / 3600.0) if (happened and ref_now) else 0.0
    ev.scores = scoring.score_event(authority_scores, primary, independent, metrics=[], age_hours=age_hours)
    ev.scores["tier_evidence"] = min(tiers) if tiers else None
    ev.scores["independent_sources"] = independent
    ev.scores["primary_evidence"] = primary
    # 印出來給人看：0 也要印。一個只在有東西時才出現的數字，看不見的時候
    # 有兩種意思（沒有轉載／這條規則沒跑）——那是這個 repo 一直在抓的形態。
    ev.scores["suspected_reposts"] = len(reposts)
    # 事情發生時我們看不看得到。每班重算，不是 sticky。
    # first_fetch 沒傳進來時判準回 unknown，不是 observed——預設值倒向誠實
    # 那一邊（紅線 8）。規格見 references/event-timestamps.md〈第三個現場〉。
    apply_coverage(ev, first_fetch)


def event_markdown(ev):
    s = ev.scores
    hd = parse_dt(ev.happened_at)
    # 裸 `.date()` 會拿到「發布者當地」的日期。`2026-07-28T02:00+08:00` 的 .date()
    # 是 07-28，UTC 卻還是 07-27——而這個字串會進 `evt-<日期>-<hash>` 的 id，
    # id 寫進 Events/ 之後不能改。見 references/timezones.md。
    date_str = (clock.utc_date(hd).isoformat() if hd
                else (ev.happened_at[:10] if ev.happened_at else None))
    fm = {
        "id": ev.id,
        "slug": ev.slug,
        "title": ev.title,
        # 中文標題跟原文並排，原文永遠留著（跟榜單描述同一條規矩：譯文是二手的，
        # 讀者要能看到一手的那句）。沒有譯文時兩格都是 None，不是空字串——
        # 空字串會讓 prep 分不出「沒翻過」跟「翻出來是空的」。
        "title_zh": ev.title_zh,
        "title_zh_src": ev.title_zh_src,
        "date": date_str,
        "happened_at": hd.isoformat() if hd else ev.happened_at,
        # 監控佇列年紀只能看這個。拿 happened_at 去量「我們放了多久」，
        # 等於新增一條會補歷史的來源就讓 CI 立刻紅——2026-07-26 就是這樣紅的。
        "ingested_at": ev.ingested_at,
        # 補寫標記。沒被補寫過就是 None——**不是省略**：省略的話一則被補寫的
        # Event 在下一次整份重寫時會靜靜變回「看起來是自己長出來的」。
        "recovered_by": ev.recovered_by,
        # 事情發生時我們看不看得到：observed / backfilled / unknown。
        # 上面兩格是「什麼時候」，這一格是「當時我們在不在場」——少了它，
        # 一則 backfilled 的舊事件在時間軸上跟真的追到的長得一模一樣。
        "coverage": ev.coverage,
        "status": "review",
        "category": None,          # enrich 填
        "company": ev.company,
        "track": None,             # 敘事 Track，enrich 填
        "fingerprint": ev.fingerprint,
        "facet": ev.facet,
        "tier_evidence": s["tier_evidence"],
        "independent_sources": s["independent_sources"],
        "suspected_reposts": s["suspected_reposts"],
        "primary_evidence": s["primary_evidence"],
        "confidence": s["confidence"],
        "heat": s["heat"],
        "impact": s["impact"],
        "value": s["value"],
        "score_factors": s["factors"],
        "blockers": [],            # 3d gate 填
        "warnings": [],
        "keywords": ev.keywords,
        "next_signal": "",
        "evidence": evidence_frontmatter(ev.evidence),
        "tags": ["event", "review"],
    }
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
    ev_lines = "\n".join(evidence_line(e) for e in ev.evidence)
    body = f"""
## 事實
{PLACEHOLDER}：一句話講清楚發生了什麼（enrich 依證據填、過 speak-human-tw）。

## 證據
{ev_lines}

## 脈絡
{PLACEHOLDER}：這件事放在什麼背景下才看得懂。

## 影響
{PLACEHOLDER}：對能力 / 成本 / 競爭結構的影響。

## 判斷
{PLACEHOLDER}（規則標註）：{'單一獨立來源 → 待證實' if ev.scores['independent_sources'] < 2 else '多來源佐證'}。

## 下一個訊號
{PLACEHOLDER}：接下來要觀察哪個可驗證訊號。
"""
    return f"---\n{front}\n---\n{body}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    cfg = vault / "_config"
    probe = vault / "_probe"
    events_dir = vault / "Events"

    # 選日：預設用 _probe 下最新有 signals-scored 的那天
    if args.day:
        day = args.day
    else:
        days = sorted(p.name for p in probe.iterdir()
                      if p.is_dir() and (p / "signals-scored.jsonl").exists()) if probe.exists() else []
        day = days[-1] if days else None
    if not day:
        print("[fatal] 找不到 signals-scored.jsonl（先跑 pulse-score.py）", file=sys.stderr)
        return 2
    scored_path = probe / day / "signals-scored.jsonl"
    if not scored_path.exists():
        print(f"[fatal] 無 {scored_path}", file=sys.stderr)
        return 2

    sources = load_sources(cfg)
    entities = load_entities(cfg)
    # 每條來源自己的觀測起點。讀不到 → 每則判 unknown（見 load_first_fetch）。
    first_fetch = load_first_fetch(probe)
    # 轉載鏈判定要的兩樣東西：gate.yaml 的門檻，與命名實體字典的比對表。
    # 字典讀原始 yaml 不讀 load_entities()——後者是給 infer_company 用的縮減版，
    # 沒有 aliases，而 aliases 正是這條規則能跨語言的原因。
    tc_cfg = load_translation_chain_cfg(cfg)
    vr_cfg = load_verbatim_repost_cfg(cfg)
    sim_min = load_title_similarity_min(cfg)
    ent_table = load_entity_table(cfg)

    signals = [json.loads(x) for x in scored_path.read_text("utf-8").splitlines() if x.strip()]
    ref_now = max([parse_dt(s.get("first_observed_at")) for s in signals if parse_dt(s.get("first_observed_at"))],
                  default=datetime.now(timezone.utc))

    # 讀既有 Events（跨日 attach）
    events = []
    existing_by_id = {}
    if events_dir.exists():
        for p in sorted(events_dir.glob("*.md")):
            fm, body = parse_frontmatter(p.read_text("utf-8"))
            if not fm.get("id"):
                continue
            happened = fm.get("happened_at") or ((str(fm.get("date")) + "T00:00:00Z") if fm.get("date") else "")
            ev = Event(fm["id"], fm.get("slug") or p.stem, fm.get("title") or p.stem,
                       happened, fm.get("fingerprint"), fm.get("facet"))
            ev.company = fm.get("company", "industry")
            ev.keywords = fm.get("keywords", [])
            ev.enriched = bool(fm.get("enriched"))   # 3c 已潤 → 重寫時保 prose
            # sticky：event_markdown() 會整份重寫 frontmatter，沒帶過去的欄位
            # 會被抹掉（fix/backfill-flag-erased-by-second-run 修的就是這個坑）。
            ev.ingested_at = fm.get("ingested_at")
            ev.title_zh = fm.get("title_zh")
            ev.title_zh_src = fm.get("title_zh_src")
            ev.recovered_by = fm.get("recovered_by")
            ev.orig_body = body
            ev.fm = fm
            ev.evidence.extend(evidence_from_frontmatter(fm.get("evidence")))
            ev.dirty = False
            ev.path = p
            events.append(ev)
            existing_by_id[ev.id] = ev

    # 依 eventability 排序（高的先，能開新 Event）
    signals = [s for s in signals if (s.get("title") or "").strip()]
    signals.sort(key=lambda s: (eventability(s, sources), s.get("published") or ""), reverse=True)

    created = attached = deferred = 0
    for sig in signals:
        title = sig["title"]
        published = sig.get("published") or sig.get("first_observed_at") or ""
        ev = attach_target(title, published, events, sim_min)
        if ev is None:
            ev = attach_by_url(sig.get("url", ""), events)
        if ev is None:
            score = eventability(sig, sources)
            if score < 70:
                deferred += 1
                continue
            fp = sig.get("fingerprint")
            # id 用「事件發生日 + (fingerprint|facet) 雜湊」→ 跨日穩定、同鍵不同 facet 不撞
            hkey = f"{fp or title}|{sig.get('facet')}"
            h = hashlib.sha1(hkey.encode("utf-8")).hexdigest()[:6]
            hd = parse_dt(published)
            hdate = clock.utc_date(hd).isoformat() if hd else day
            eid = f"evt-{hdate}-{h}"
            if eid in existing_by_id:  # 同鍵同日 → 視為既有
                ev = existing_by_id[eid]
            else:
                slug = f"{slugify(title)}-{h[:4]}"
                ev = Event(eid, slug, title, published, fp, sig.get("facet"))
                # 建立這則 Event 的那個訊號，probe 是什麼時候第一次看到它的。
                ev.ingested_at = sig.get("first_observed_at")
                ev.company = infer_company(sig.get("entity_hits"), entities)
                # 曾經是 list(cluster.title_tokens(title))[:8]，那是 set → 順序隨機，
                # 同一個標題每跑一次就換一組關鍵詞。理由與實測見 lib/cluster.py。
                ev.keywords = cluster.keyword_tokens(title, 8)
                events.append(ev)
                existing_by_id[eid] = ev
                created += 1
        else:
            attached += 1
        rel = int(round(cluster.title_similarity(title, ev.title) * 100))
        ev.add_evidence(sig["source_id"], sig.get("url", ""), title, rel, published)

    # coverage 是每班重算的推導欄位，所以要在挑「哪些要重寫」**之前**算完。
    # 只算 dirty 的那些，這一格永遠長不到「這一班沒有新證據」的 Event 上——
    # 而那是絕大多數。見 apply_coverage() 的 docstring。
    #
    # 分兩桶：本來就要整份重寫的（有新證據）讓 event_markdown 順手帶出去；
    # **只有 coverage 變了**的那些走外科式 patch，不整份重寫、不重算分數、
    # 不動 status——後者會把還沒潤稿的 dropped 事件復活成 review。
    cov_only = []
    for ev in events:
        if apply_coverage(ev, first_fetch) and not ev.dirty and ev.path is not None:
            cov_only.append(ev)

    # rescore 所有動到的 Event
    changed = [e for e in events if e.dirty]
    for ev in changed:
        rescore(ev, sources, ref_now, tc_cfg, ent_table, first_fetch, vr_cfg)

    # 摘要
    conf = [e.scores["confidence"] for e in changed if e.scores]
    print(f"pulse-cluster  day={day}  signals={len(signals)}")
    print(f"  created={created}  attached={attached}  deferred(eventability<70)={deferred}")
    print(f"  events changed={len(changed)}  (total in vault={len(events)})")
    # 印出來給人看：0 也要印。一個只在有東西時才出現的數字，看不見的時候有兩種
    # 意思（沒有變／這段沒跑），而這一格上線那天正好就是「沒跑」。
    # 印出來給人看：0 也要印。這個數字只算「本來不用重寫、單純為了 coverage
    # 而改一格」的那些，不含本來就要整份重寫的——兩者混在一起會讓遷移那天的
    # 數字看起來像「52 則被改動」，而實際上絕大多數只是多了一個欄位。
    print(f"  只補 coverage（不重寫、不重算分數）的: {len(cov_only)}")
    if conf:
        import statistics
        print(f"  confidence: min={min(conf)} median={int(statistics.median(conf))} max={max(conf)}")
    multi = [e for e in changed if e.scores and e.scores['independent_sources'] >= 2]
    print(f"  ≥2 獨立來源的 Event: {len(multi)}/{len(changed)}")

    if args.dry_run:
        print("  [dry-run] 未寫檔")
        return 0
    events_dir.mkdir(parents=True, exist_ok=True)
    for ev in changed:
        out = ev.path or (events_dir / f"{ev.id}.md")
        if ev.enriched and ev.orig_body is not None and ev.fm is not None:
            out.write_text(rescored_enriched_markdown(ev), encoding="utf-8")  # 保 prose，只更新分數
        else:
            out.write_text(event_markdown(ev), encoding="utf-8")
    patched = sum(1 for ev in cov_only if patch_coverage(ev.path, ev.coverage))
    print(f"  → 寫入 {len(changed)} 個 Events/*.md，另外 {patched} 個只補了 coverage 一格")
    return 0


def rescored_enriched_markdown(ev):
    """已 enrich 的 Event 拿到新證據時：只更新分數與 evidence frontmatter，保留潤好的 prose body。"""
    s = ev.scores
    fm = dict(ev.fm)
    fm["tier_evidence"] = s["tier_evidence"]
    fm["independent_sources"] = s["independent_sources"]
    fm["suspected_reposts"] = s["suspected_reposts"]
    fm["primary_evidence"] = s["primary_evidence"]
    fm["confidence"] = s["confidence"]
    fm["heat"] = s["heat"]
    fm["impact"] = s["impact"]
    fm["value"] = s["value"]
    fm["score_factors"] = s["factors"]
    fm["evidence"] = evidence_frontmatter(ev.evidence)
    # coverage 每班重算，所以已潤稿的那條路也要更新——這裡漏掉的話，
    # 這一格只會出現在**沒潤過稿**的 Event 上，而且 apply_coverage 每班都會
    # 判定「跟檔案上不一樣」→ 每班重寫全部 Event、每班寫的還是舊值。
    # 實測就是這樣：52 則全被重寫，只有 1 則真的拿到這一格。
    fm["coverage"] = ev.coverage
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
    body = ev.orig_body if ev.orig_body.startswith("\n") else "\n" + ev.orig_body
    return f"---\n{front}\n---{body}"


def eventability(sig, sources):
    return cluster.eventability_score(sig, sources.get(sig.get("source_id")))


if __name__ == "__main__":
    sys.exit(main())
