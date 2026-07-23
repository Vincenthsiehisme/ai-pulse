#!/usr/bin/env python3
"""pulse-probe.py — M1：把兩軌語料收回來，並產出決定後續設計的兩個比率。

刻意**不做**的事（M1 邊界，別擴張）：
  - 不聚類、不去重、不算 quality score
  - 不開 readiness gate、不產 Event
  - 不碰人物層 / 任職邊
只做：抓 → 落地原始標題 → 量測 → git commit。

產出：
  _corpus/<YYYY-MM-DD>/<source_id>.jsonl   逐筆原始項目（標題 + 節錄 + 連結）
  _probe/<YYYY-MM-DD>/report.md            兩個比率 + 候選詞收割
  _probe/state.json                        etag / first_fetch_at / last_run（失敗不推進）
  _probe/seen.json                         url_canonical → first_observed_at（寫入一次永不重寫）

lifecycle 語意（v2.1）：
  active / degraded / probing → 會被抓
  draft / dormant            → 不抓，但仍列入來源狀態表標 skipped_lifecycle
  probing = 「會被抓，但還沒通過 checklist」。七天觀測期的來源應設此值。
  --only 為明示除錯覆寫，會略過 lifecycle 過濾。

用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-probe.py            # 正常跑
  VAULT_DIR=... python scripts/pulse-probe.py --dry-run                # 不寫檔不 commit
  VAULT_DIR=... python scripts/pulse-probe.py --only src-openai-blog   # 單源除錯

紅線：0 LLM / 0 Claude。全部規則，結果可重現。
依賴：requests, PyYAML, feedparser
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import random
import re
import socket
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser

import yaml

UA = "ai-pulse-probe/1.0 (+deterministic; contact via repo)"
MAX_BODY = 5 * 1024 * 1024
MAX_REDIRECTS = 5
SUMMARY_CHARS = 300  # 尊重 license_note 的 "titles + excerpt"，不落全文

# 只有這三種 lifecycle 會被實際請求。draft / dormant 一律跳過但仍出現在狀態表。
RUN_LIFECYCLES = {"active", "degraded", "probing"}

# --------------------------------------------------------- author 分類（5a/5b）
# M1 實測：120/120 有 author，但 arXiv 是具名論文作者、GitHub release 是發版者
# login（常為 bot）。「欄位有沒有值」與「值能不能用」是兩件事，必須分開量。
# 下面全是字面規則，沒有推論。分類會抽樣寫進報告供人工校準。
BOT_PAT = re.compile(
    r"(?:^|[\s\-_\[\.])(?:bot|ci|actions?|automation|dependabot|renovate|"
    r"release[-_]?bot|github[-_]?actions|noreply)(?:$|[\s\-_\]\.@+])", re.I)
ORG_PAT = re.compile(
    r"\b(?:inc|llc|ltd|corp|team|labs?|research|foundation|project|group|"
    r"institute|university|committee|commission|council|editors?|staff)\b\.?\s*$",
    re.I)
MULTI_PAT = re.compile(r",|\band\b|\bet al\b|&", re.I)


def classify_author(author: str | None) -> str:
    """→ none | machine | handle | org | multi_person | person | unknown

    保守預設：判不出來一律 unknown，不算進自然人。
    誤判為非自然人只是低估人物層價值，誤判為自然人會讓獨立性錯誤加分。
    """
    if not author or not str(author).strip():
        return "none"
    a = str(author).strip()
    if BOT_PAT.search(a):
        return "machine"
    if ORG_PAT.search(a):
        return "org"
    if MULTI_PAT.search(a):
        return "multi_person"
    if not re.search(r"\s", a):
        return "handle"          # 無空白單詞 → 帳號 login，不是姓名
    toks = [t for t in re.split(r"\s+", a) if t]
    if len(toks) >= 2 and sum(1 for t in toks if t[:1].isupper()) >= 2:
        return "person"
    return "unknown"


# person_resolvable 的定義是本專案的判斷，不是通則：
#   multi_person（論文共同作者串）算「可解析到自然人」，因為第一作者可定位。
#   若你認為 checklist 5b 的「單一自然人」應嚴格排除共同作者，
#   把 "multi_person" 從下面移除即可，報告會同時列出兩種算法的分母。
PERSON_KINDS = {"person", "multi_person"}

# --------------------------------------------------------------------- config


def load_config(vault: Path) -> tuple[dict, list[dict]]:
    cfg = vault / "_config"
    entities = yaml.safe_load((cfg / "entities.yaml").read_text("utf-8"))
    raw = yaml.safe_load((cfg / "sources.yaml").read_text("utf-8"))

    sources: list[dict] = []
    for key in ("official_sources", "kol_sources", "aggregator_sources"):
        for s in raw.get(key) or []:
            if str(s.get("id", "")).endswith("<slug>"):
                continue  # 樣板佔位條目，跳過
            sources.append(s)
    return entities, sources


# ----------------------------------------------------------------- safe fetch

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "fbclid", "gclid", "ref", "spm"}
PRIVATE_NETS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
    "169.254.0.0/16", "0.0.0.0/8", "100.64.0.0/10",
    "::1/128", "fc00::/7", "fe80::/10")]


def assert_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError(f"security: scheme {p.scheme!r}")
    if p.username or p.password:
        raise ValueError("security: credentials in URL")
    host = p.hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"network: dns {e}") from e
    for *_, sa in infos:
        ip = ipaddress.ip_address(sa[0])
        if any(ip in net for net in PRIVATE_NETS):
            raise ValueError(f"security: private ip {ip}")


def canonical_url(url: str) -> str:
    s = urlsplit(url)
    q = sorted((k, v) for k, v in parse_qsl(s.query) if k not in TRACKING)
    host = s.netloc.lower().removeprefix("www.")
    path = s.path.rstrip("/") or "/"
    return urlunsplit((s.scheme, host, path, urlencode(q), ""))


def safe_fetch(url: str, etag: str | None = None) -> tuple[int, str | None, dict]:
    """每一跳 redirect 都重跑 SSRF 檢查（骨架版用 allow_redirects=True，是個洞）。"""
    import requests

    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        assert_public_url(current)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                headers = {"User-Agent": UA}
                if etag:
                    headers["If-None-Match"] = etag
                r = requests.get(current, headers=headers, timeout=15,
                                 stream=True, allow_redirects=False)
                if r.status_code == 304:
                    return 304, None, dict(r.headers)
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("Location")
                    if not loc:
                        raise ValueError("upstream: redirect without Location")
                    current = requests.compat.urljoin(current, loc)
                    break  # 跳出 retry，回外圈重驗新 URL
                if r.status_code == 429:
                    time.sleep(int(r.headers.get("Retry-After", 2 ** attempt))
                               + random.random())
                    continue
                if r.status_code >= 500:
                    time.sleep(2 ** attempt + random.random())
                    continue
                body = r.raw.read(MAX_BODY + 1, decode_content=True)
                if len(body) > MAX_BODY:
                    raise ValueError("upstream: body too large")
                return r.status_code, body.decode("utf-8", "replace"), dict(r.headers)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt + random.random())
        else:
            if last_exc:
                raise last_exc
    raise ValueError("upstream: too many redirects")


def robots_allows(url: str) -> bool | None:
    """→ True 允許 / False 拒絕 / None 未知（呼叫端保守跳過）。

    必須用**與實際抓取相同的 User-Agent** 去取 robots.txt。
    舊版直接用 RobotFileParser.read()，那是 urllib 的預設 UA（Python-urllib/x.y），
    不少站台擋它 —— 等於「用 A 身分問可不可以，用 B 身分去抓」，檢查本身無效。

    狀態碼處理依 robots 慣例：
      200        → 依內容判定
      401 / 403  → 視為全面拒絕
      其餘 4xx   → 沒有 robots.txt，視為允許（含 404 / 410）
      5xx / 例外 → 未知，交給呼叫端保守跳過
    """
    try:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        status, body, _ = safe_fetch(robots_url)
    except Exception:  # noqa: BLE001
        return None

    if status in (401, 403):
        return False
    if status != 200 or body is None:
        return True if 400 <= status < 500 else None

    rp = RobotFileParser()
    rp.parse(body.splitlines())
    return rp.can_fetch(UA, url)


# ------------------------------------------------------------------- entities

def normalize_text(s: str) -> str:
    """大小寫、全半形、空白。簡繁**不在**這裡處理，見 report 的已知缺口。"""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\u200b-\u200f\ufeff]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


ENTITY_SECTIONS = ("companies", "product_lines", "infrastructure",
                   "frameworks", "technologies", "policies")


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


# ------------------------------------------------- candidate harvest (更新機制)

CAND_LATIN = re.compile(r"\b(?:[A-Z][a-zA-Z0-9]*(?:[-.][A-Za-z0-9]+)*"
                        r"(?:\s[A-Z][a-zA-Z0-9]*){0,2})\b")
CAND_BRACKET = re.compile(r"[「『《【\"“]([^」』》】\"”]{2,20})[」』》】\"”]")
CAND_STOP = {"The", "This", "That", "New", "AI", "How", "Why", "What", "We",
             "It", "In", "On", "For", "And", "But", "You", "Our", "A", "An",
             "Introducing", "Announcing", "Launching", "Presenting", "Meet",
             "Today", "Now", "Update", "Release", "Blog", "Read", "More"}


def harvest_candidates(text: str, matched: set[str]) -> list[str]:
    """只做拉丁字與括號內字串。中文無詞邊界，未括號的候選抽不出來——已知缺口。

    matched = match_entities 回傳的表面字串集合；候選若已是既有實體的一部分就排除，
    否則報告會被自己字典裡的詞洗版。
    """
    seen: set[str] = set()
    out: list[str] = []

    def consider(tok: str) -> None:
        tok = tok.strip()
        if len(tok) < 3 or tok in CAND_STOP:
            return
        n = normalize_text(tok)
        if not n or n in seen:
            return
        if any(n in m or m in n for m in matched):
            return
        seen.add(n)
        out.append(tok)

    for m in CAND_LATIN.finditer(text):
        consider(m.group(0))
    for m in CAND_BRACKET.finditer(text):
        consider(m.group(1))
    return out


# -------------------------------------------------------------------- adapters

def adapt_rss(source: dict, body: str) -> list[dict]:
    import feedparser

    feed = feedparser.parse(body)
    items = []
    for e in feed.entries[: int(source.get("quota_per_run", 50))]:
        author = e.get("author") or (e.get("authors") or [{}])[0].get("name")
        # Hugging Face 的 item 沒有 <link>，只有 <guid isPermaLink="true">。
        # feedparser 把 guid 映到 id。少了這段 fallback 會靜默產出空 url。
        link = e.get("link") or ""
        if not link:
            gid = e.get("id") or ""
            if gid.startswith(("http://", "https://")):
                link = gid
        items.append({
            "title": e.get("title", "") or "",
            "summary": re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")[:SUMMARY_CHARS],
            "url": link,
            "published": e.get("published") or e.get("updated") or "",
            "author": author or None,
        })
    return items


def adapt_github_releases(source: dict, _body: str) -> list[dict]:
    repo = source["endpoint"]
    status, body, _ = safe_fetch(f"https://api.github.com/repos/{repo}/releases")
    if status != 200 or not body:
        return []
    items = []
    for rel in json.loads(body)[: int(source.get("quota_per_run", 20))]:
        items.append({
            "title": rel.get("name") or rel.get("tag_name") or "",
            "summary": (rel.get("body") or "")[:SUMMARY_CHARS],
            "url": rel.get("html_url", ""),
            "published": rel.get("published_at", ""),
            "author": (rel.get("author") or {}).get("login"),
        })
    return items


ADAPTERS = {"rss": adapt_rss, "atom": adapt_rss,
            "github-releases": adapt_github_releases}

# 這些 adapter 的 endpoint 不是 URL（例如 github-releases 是 owner/repo），
# 由 adapter 自己組 URL 並 fetch，run_source 不做通用抓取。
SELF_FETCH = {"github-releases"}


# ------------------------------------------------------------------------ main

def run_source(src: dict, table, state: dict, seen: dict) -> tuple[list[dict], dict]:
    sid = src["id"]
    st = state.get(sid, {})
    stat = {"id": sid, "track": src.get("track"), "tier": src.get("tier"),
            "status": None, "items": 0, "error": None, "robots": None,
            "backfill": False, "new": 0}

    adapter = ADAPTERS.get(src.get("adapter"))
    if adapter is None:
        stat["status"] = "unsupported_adapter"
        stat["error"] = src.get("adapter")
        return [], stat

    url = src["endpoint"]
    self_fetch = src.get("adapter") in SELF_FETCH

    if not self_fetch:
        stat["robots"] = robots_allows(url)
        if stat["robots"] is False:
            stat["status"] = "robots_disallow"
            return [], stat
        if stat["robots"] is None:
            # robots.txt 取不到 = 未知。保守預設往「不允許」倒，與 robots_allows
            # 的 docstring 一致。舊版只擋 is False，等於未知時照抓，是自我欺騙。
            stat["status"] = "robots_unknown"
            stat["error"] = "robots.txt 取不到，保守跳過"
            return [], stat

    try:
        if self_fetch:
            # endpoint 非 URL，交給 adapter 自己組並抓
            items = adapter(src, "")
            stat["status"] = 200
            headers = {}
        else:
            status, body, headers = safe_fetch(url, st.get("etag"))
            stat["status"] = status
            if status == 304 or body is None:
                return [], stat
            if status != 200:
                stat["error"] = f"http {status}"
                return [], stat
            items = adapter(src, body)
    except Exception as e:  # noqa: BLE001
        stat["status"] = "error"
        stat["error"] = f"{type(e).__name__}: {e}"
        return [], stat  # 失敗不推進 cursor

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # backfill 判定：純 deterministic，不需要比對日期區間。
    # 這個來源從沒抓過 → 這一整批都是既有存量，不是當期訊號。
    # 誤差方向：首跑當天剛發布的新文章會被錯標為 backfill。
    # 這是保守的一邊——寧可少算一筆 lead_days，不要讓半年前的存量污染它。
    is_backfill = not st.get("first_fetch_at")
    stat["backfill"] = is_backfill

    out, new_count = [], 0
    for it in items:
        text = f"{it['title']} {it['summary']}"
        hits, surfaces = match_entities(text, table)
        canon = canonical_url(it["url"]) if it["url"] else ""

        # first_observed_at 的合約是「寫入一次永不重寫」（見 obsidian-schema 時間三分）。
        # 舊版無條件填 now，同一則文章連續三天出現就有三個首次觀測時間，lead_days 失真。
        if canon and canon in seen:
            first_seen = seen[canon]
            is_new = False
        else:
            first_seen = now
            is_new = True
            if canon:
                seen[canon] = now
            new_count += 1

        out.append({
            **it,
            "source_id": sid,
            "track": src.get("track"),
            "tier": src.get("tier"),
            "url_canonical": canon,
            "first_observed_at": first_seen,
            "is_new": is_new,
            "backfill": is_backfill,
            "author_kind": classify_author(it.get("author")),
            "entity_hits": [e for e, _ in hits],
            "entity_types": sorted({t for _, t in hits}),
            "candidates": harvest_candidates(text, surfaces),
        })

    stat["items"] = len(out)
    stat["new"] = new_count
    # 保留既有欄位，不整包覆寫（否則 first_fetch_at 每跑一次就被清掉）
    st = dict(st)
    st["etag"] = headers.get("ETag")
    st["last_run"] = now
    st.setdefault("first_fetch_at", now)
    state[sid] = st
    return out, stat


def write_report(vault: Path, day: str, rows: list[dict], stats: list[dict],
                 simp_trad: bool) -> Path:
    by_track: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_track[r["track"] or "unknown"].append(r)

    lines = [f"# probe report {day}", "",
             "M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。", ""]

    backfill_n = sum(1 for r in rows if r.get("backfill"))
    if backfill_n:
        lines += [f"> ⚠ 本輪含 {backfill_n} 筆 backfill（首次抓取的既有存量）。",
                  "> backfill 不代表當期訊號，lead_days 與熱度統計應排除。", ""]

    lines += ["## 兩個決定性比率", "",
              "| track | 條目 | 5a author 有值 | 5b 可解析自然人 | 實體命中率 |",
              "|---|---|---|---|---|"]
    for track, items in sorted(by_track.items()):
        n = len(items)
        if not n:
            lines.append(f"| {track} | 0 | — | — | — |")
            continue
        a = sum(1 for i in items if i.get("author"))
        p = sum(1 for i in items if i.get("author_kind") in PERSON_KINDS)
        h = sum(1 for i in items if i["entity_hits"])
        lines.append(f"| {track} | {n} | {a}/{n} = {a/n:.0%} | "
                     f"{p}/{n} = {p/n:.0%} | {h}/{n} = {h/n:.0%} |")
    lines += ["",
              "- **5a（author 有值）只用來偵測 adapter 解析失敗**，不作任何人物層判斷。"
              "M1 實測 120/120 有值卻幾乎不可用，這個數字單獨看會騙人。",
              "- **5b（可解析自然人）才決定人物層與獨立性升級有沒有用。**"
              "官方線若過低，people.yaml 只在 KOL 線生效。",
              "- **實體命中率**決定字典往哪長。低命中不代表字典爛，"
              "可能是語料型態與假設不符。", ""]

    lines += ["### author 分類分佈（5b 的組成）", "",
              "| kind | 筆數 | 計入 5b |", "|---|---|---|"]
    ak = Counter(r.get("author_kind") or "none" for r in rows)
    for kind, c in ak.most_common():
        lines.append(f"| {kind} | {c} | {'✓' if kind in PERSON_KINDS else ''} |")
    lines += ["",
              "分類全為字面規則，無推論。判不出來一律 unknown 且不計入 5b（保守預設）。",
              "`multi_person` 是共同作者串，本專案判定為可解析到自然人；",
              "若要嚴格採「單一自然人」，把它移出 PERSON_KINDS 即可。", ""]

    lines += ["### 分類抽樣（供人工校準規則）", "",
              "| author 原值 | 判定 | 來源 |", "|---|---|---|"]
    sampled: set = set()
    for r in rows:
        key = (r["source_id"], r.get("author_kind"))
        if key in sampled or not r.get("author"):
            continue
        sampled.add(key)
        lines.append(f"| {str(r['author'])[:60]} | {r.get('author_kind')} | "
                     f"{r['source_id']} |")
    lines.append("")

    lines += ["## 命中的實體型別分佈", ""]
    tc = Counter(t for r in rows for t in r["entity_types"])
    lines += [f"- {t}: {c}" for t, c in tc.most_common()] or ["- （無）"]
    lines.append("")

    lines += ["## 字典補漏候選（未命中且跨來源出現）", "",
              "晉升門檻：跨 ≥2 來源、≥3 次。只列達標者，避免一次性雜訊灌進字典。", "",
              "| 候選 | 次數 | 來源數 |", "|---|---|---|"]
    cnt: Counter = Counter()
    srcs: dict[str, set] = defaultdict(set)
    for r in rows:
        for c in r["candidates"]:
            cnt[c] += 1
            srcs[c].add(r["source_id"])
    promoted = [(c, n, len(srcs[c])) for c, n in cnt.most_common()
                if n >= 3 and len(srcs[c]) >= 2]
    lines += [f"| {c} | {n} | {s} |" for c, n, s in promoted[:40]] or \
             ["| （本輪無達標候選） | | |"]
    lines.append("")

    # 冷啟階段來源少且詞彙不重疊時，「跨 ≥2 來源」結構上不可能成立，
    # 上面那張表會永遠是空的 —— 看起來機制在跑，實際永遠不輸出。
    # 這一區讓收割機制在冷啟階段也看得見，但明確不參與晉升。
    single = [(c, n, next(iter(srcs[c]))) for c, n in cnt.most_common()
              if n >= 3 and len(srcs[c]) == 1]
    lines += ["### 單來源高頻（觀察用，不列入晉升）", "",
              f"目前活躍來源 {len({r['source_id'] for r in rows})} 條。"
              "來源數少時「跨 ≥2 來源」門檻結構上難以成立，",
              "上表為空不代表收割機制壞掉。此區僅供觀察，不得直接寫進字典。", "",
              "| 候選 | 次數 | 唯一來源 |", "|---|---|---|"]
    lines += [f"| {c} | {n} | {s} |" for c, n, s in single[:40]] or \
             ["| （無） | | |"]
    lines.append("")

    lines += ["## 來源狀態", "",
              "| source | track | status | items | new | backfill | robots | error |",
              "|---|---|---|---|---|---|---|---|"]
    for s in stats:
        lines.append(f"| {s['id']} | {s['track']} | {s['status']} | {s['items']} | "
                     f"{s.get('new', 0)} | {'✓' if s.get('backfill') else ''} | "
                     f"{s['robots']} | {s['error'] or ''} |")
    lines += ["",
              "`skipped_lifecycle` = 未被請求，error 欄顯示其 lifecycle 值。",
              "`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕。", ""]

    lines += ["", "## 本輪已知缺口（勿當成已實現）", "",
              f"- 簡繁正規化：{'已啟用 opencc' if simp_trad else '**未啟用**'}"
              "（未啟用時，簡體別名不會命中繁體寫法，反之亦然）",
              "- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來",
              "- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能",
              "- `seen.json` 無保留策略，會單調成長；`_corpus` 全量進版控的問題同理未解",
              "- backfill 以「該來源首次抓取」判定，首跑當天發布的新文章會被誤標為存量",
              "- author 分類是字面規則，可能誤判；請對照上面的分類抽樣校準",
              ""]

    path = vault / "_probe" / day / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def git_commit(vault: Path, msg: str) -> None:
    try:
        subprocess.run(["git", "-C", str(vault), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(vault), "commit", "-m", msg], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[warn] git commit 失敗（可能無變更）：{e}", file=sys.stderr)


def heartbeat(status: str, vault: Path, detail: str = "") -> None:
    """心跳寫在 vault **外面**。

    若 vault 所在磁碟未掛載，vault 內的 health.md 也跟著消失，紅燈就永遠看不到。
    這個檔是唯一能證明「排程確實有跑」的訊號，路徑不隨 VAULT_DIR 變動。
    """
    home = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    hb = home / "ai-pulse" / "heartbeat.json"
    try:
        hb.parent.mkdir(parents=True, exist_ok=True)
        prev = json.loads(hb.read_text("utf-8")) if hb.exists() else {}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        prev["last_attempt"] = now
        prev["vault"] = str(vault)
        prev["status"] = status
        prev["detail"] = detail
        if status == "ok":
            prev["last_success"] = now
        hb.write_text(json.dumps(prev, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] heartbeat 寫入失敗：{e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])

    # preflight：碟沒掛上 / 路徑打錯時大聲失敗，不要默默建出一個空 vault
    if not vault.is_dir():
        heartbeat("vault_missing", vault, "VAULT_DIR 不存在（磁碟未掛載？代號變了？）")
        print(f"[fatal] VAULT_DIR 不存在：{vault}", file=sys.stderr)
        return 2
    if not (vault / "_config").is_dir():
        heartbeat("config_missing", vault, "_config/ 不存在")
        print(f"[fatal] 找不到 {vault / '_config'}", file=sys.stderr)
        return 2

    heartbeat("running", vault)
    entities, sources = load_config(vault)
    table = build_matcher(entities)
    try:
        import opencc  # noqa: F401
        simp_trad = True
    except ImportError:
        simp_trad = False

    state_path = vault / "_probe" / "state.json"
    state = json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}
    seen_path = vault / "_probe" / "seen.json"
    seen = json.loads(seen_path.read_text("utf-8")) if seen_path.exists() else {}

    # lifecycle 過濾。跳過的來源仍進 stats —— 靜默丟棄是這個系統最危險的失敗模式。
    runnable, skipped = [], []
    for src in sources:
        if args.only:
            if src["id"] == args.only:
                runnable.append(src)   # 明示除錯，覆寫 lifecycle
            continue
        (runnable if src.get("lifecycle") in RUN_LIFECYCLES else skipped).append(src)

    # 硬防護：可跑來源為 0 時，不准安靜地成功收工。
    # 目前九條來源可能全是 draft，過濾一上線就會發生這件事。
    if not runnable:
        detail = (f"0 個可跑來源（共 {len(sources)} 條，"
                  f"lifecycle 需為 {sorted(RUN_LIFECYCLES)} 之一）")
        heartbeat("no_runnable_sources", vault, detail)
        print(f"[fatal] {detail}", file=sys.stderr)
        for src in skipped:
            print(f"  - {src['id']}: {src.get('lifecycle')}", file=sys.stderr)
        return 3

    day = date.today().isoformat()
    rows: list[dict] = []
    stats: list[dict] = []
    for src in skipped:
        stats.append({"id": src["id"], "track": src.get("track"),
                      "tier": src.get("tier"), "status": "skipped_lifecycle",
                      "items": 0, "error": src.get("lifecycle"), "robots": None,
                      "backfill": False, "new": 0})
    for src in runnable:
        items, stat = run_source(src, table, state, seen)
        stats.append(stat)
        rows.extend(items)
        flag = " [backfill]" if stat["backfill"] else ""
        print(f"[{stat['status']}] {stat['id']}: {stat['items']} items"
              f" ({stat['new']} new){flag}"
              f"{' — ' + stat['error'] if stat['error'] else ''}")
        time.sleep(1)  # 禮貌間隔

    if skipped:
        print(f"\n跳過 {len(skipped)} 條（lifecycle 不在 {sorted(RUN_LIFECYCLES)}）："
              + ", ".join(s["id"] for s in skipped))

    if args.dry_run:
        print(f"\n--dry-run：共 {len(rows)} 筆，未寫檔（state / seen 也未更新）。")
        heartbeat("dry_run", vault, f"{len(rows)} items")
        return 0

    for sid in {r["source_id"] for r in rows}:
        p = vault / "_corpus" / day / f"{sid}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        # "w" 不是 "a"：每個 source 的當日資料是一次全寫的，附加模式只會讓
        # 同日重跑疊加重複資料、污染比率。同日重跑 = 取代當日快照。
        with p.open("w", encoding="utf-8") as f:
            for r in (x for x in rows if x["source_id"] == sid):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
    seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), "utf-8")

    report = write_report(vault, day, rows, stats, simp_trad)
    git_commit(vault, f"probe {day}: {len(rows)} items / {len(stats)} sources")
    ok = sum(1 for s in stats if s["status"] in (200, 304))
    heartbeat("ok", vault, f"{len(rows)} items / {ok}/{len(stats)} sources ok")
    print(f"\nreport → {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
