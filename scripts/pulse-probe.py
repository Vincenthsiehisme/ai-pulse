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
#
# 2026-07-26 校準（拿 3 天 859 筆真語料回頭量的結果，不是想像出來的案例）：
#   假陽性 27/134——被判成 person 的裡面，「NVIDIA Writers」18 筆與
#   「GeForce NOW Community」9 筆是**組織**。ORG_PAT 收了 team/labs/staff，
#   卻沒收 writers / community，兩個字都以大寫開頭，於是直接落進 person。
#   兩成的「自然人」是假的，而 person 是唯一會計入 5b 的乾淨桶。
#   假陰性其一：「Sebastian Raschka, PhD」因為逗號被判 multi_person。它是一個人，
#   後面那截是學位。落在 PERSON_KINDS 裡所以 5b 沒少算，但桶子放錯，
#   之後要靠 author 綁 person_id 時會綁不上。
#   假陰性其二：「karpathy (hidden)」被判 unknown。它是 Substack 的帳號顯示格式，
#   括號內是平台加的註記不是姓名的一部分；剝掉之後就是單詞 login，該進 handle。
#
# 修法的方向仍照本檔原本的保守預設：**寧可低估人物層，不可高估獨立性。**
# 所以 ORG_PAT 只往「明確是組織」的字擴，不去猜；剝除只剝白名單內的雜訊，
# 不做任何自然語言推論。
BOT_PAT = re.compile(
    r"(?:^|[\s\-_\[\.])(?:bot|ci|actions?|automation|dependabot|renovate|"
    r"release[-_]?bot|github[-_]?actions|noreply)(?:$|[\s\-_\]\.@+])", re.I)
ORG_PAT = re.compile(
    r"\b(?:inc|llc|ltd|corp|team|labs?|research|foundation|project|group|"
    r"institute|university|committee|commission|council|editors?|staff|"
    # ↓ 2026-07-26 增補。每個字都是實測撞到、或同一形態的近親。
    #   community / writers 是 NVIDIA blog 的實際署名；其餘是同類的編制名詞。
    r"writers?|community|newsroom|editorial|desk|press\s*office|"
    r"communications|department|division|society|association|"
    r"contributors?|crew)\b\.?\s*$",
    re.I)
MULTI_PAT = re.compile(r",|\band\b|\bet al\b|&", re.I)

# 尾綴白名單：只剝這些，不剝任何其他逗號後內容——「Son Ho, Cédric Fournet」
# 那種共同作者串必須維持 multi_person。學位與世代後綴不是第二個人。
SUFFIX_PAT = re.compile(
    r"[,\s]+(?:ph\.?\s*d|m\.?\s*d|d\.?\s*phil|sc\.?\s*d|"
    r"m\.?\s*b\.?\s*a|m\.?\s*sc|b\.?\s*sc|"
    r"jr|sr|ii|iii|iv)\.?\s*$", re.I)
# 平台加的括號註記（Substack 的 "(hidden)"、部分站台的 "(guest)"）不是姓名的一部分。
PAREN_PAT = re.compile(r"\s*[（(][^）)]*[）)]\s*$")
BYLINE_PAT = re.compile(r"^\s*by[:\s]+", re.I)


def normalize_author(author: str) -> str:
    """剝掉平台雜訊，只剝白名單內的東西，不做語意推論。"""
    a = str(author).strip()
    a = BYLINE_PAT.sub("", a)
    for pat in (PAREN_PAT, SUFFIX_PAT):
        prev = None
        while prev != a:                 # 允許 "Name, PhD, Jr." 這種疊加
            prev = a
            a = pat.sub("", a).strip()
    return a.strip(" ,;")


def classify_author(author: str | None) -> str:
    """→ none | machine | handle | org | multi_person | person | unknown

    保守預設：判不出來一律 unknown，不算進自然人。
    誤判為非自然人只是低估人物層價值，誤判為自然人會讓獨立性錯誤加分。
    """
    if not author or not str(author).strip():
        return "none"
    a = normalize_author(author)
    if not a:
        return "none"                    # 剝完只剩空字串（例如 author 就是 "(hidden)"）
    if BOT_PAT.search(a):
        return "machine"
    if ORG_PAT.search(a):
        return "org"
    if MULTI_PAT.search(a):
        return "multi_person"
    if not re.search(r"\s", a):
        # 無空白單詞 → 帳號 login，不是姓名。全大寫（NVIDIA、IBM）例外：
        # 那是機構縮寫，不會是自然人的完整署名。
        return "org" if (len(a) >= 3 and a.isupper() and a.isalpha()) else "handle"
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


def robots_verdict(url: str) -> tuple[bool | None, str]:
    """→ (允許與否, 原因碼)。原因碼是這支存在的理由。

    2026-07-24 漏抓 Claude Opus 5 的最深層根因就在這裡：舊版只回一個布林值，
    於是「拿不到 robots.txt（401/403）」跟「站方明文 Disallow」被壓成同一個 False。
    抓取端把兩者都當成拒絕還算保守合理；但**設定檔把這個 False 存了下來**，
    一次 WAF 擋包就永久關掉了整條 OpenAI 線，而且看起來像是對方的政策。

    抓不到 ≠ 不准抓。這是量測失敗，不是站方意志。分開回報之後，抓取端可以照樣
    保守跳過，重驗端則能拒絕把它寫成永久判決。

    原因碼：
      ok                 200 且規則放行
      disallow           200 且規則明文擋住 → 這才是站方政策
      no_robots          其餘 4xx（404 / 410…）＝沒有 robots.txt，依慣例放行
      unavailable_403    401 / 403：拿不到檔案。抓取端當拒絕，但不得寫成政策
      unreachable        5xx / 空 body：對方壞了
      error              連線層例外
    """
    try:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        status, body, _ = safe_fetch(robots_url)
    except Exception:  # noqa: BLE001
        return None, "error"

    if status in (401, 403):
        return False, "unavailable_403"
    if status != 200 or body is None:
        if 400 <= status < 500:
            return True, "no_robots"
        return None, "unreachable"

    rp = RobotFileParser()
    rp.parse(body.splitlines())
    allowed = rp.can_fetch(UA, url)
    return allowed, "ok" if allowed else "disallow"


def robots_allows(url: str) -> bool | None:
    """→ True 允許 / False 拒絕 / None 未知（呼叫端保守跳過）。

    必須用**與實際抓取相同的 User-Agent** 去取 robots.txt。
    舊版直接用 RobotFileParser.read()，那是 urllib 的預設 UA（Python-urllib/x.y），
    不少站台擋它 —— 等於「用 A 身分問可不可以，用 B 身分去抓」，檢查本身無效。

    抓取端要的就是一個「跑不跑」的布林值，維持原本的保守語意：
    401/403 → False（今晚不抓）。要區分「不准抓」與「抓不到」的呼叫端請改用
    robots_verdict()——差別只在能不能把結論寫進設定檔。
    """
    return robots_verdict(url)[0]


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


SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _slug_to_title(url: str) -> str:
    """從 URL 尾段還原標題：/news/claude-opus-5 → "Claude Opus 5"。

    這是**推導**不是原文標題。sitemap 沒有標題欄位，要嘛從 slug 還原、要嘛去抓內文；
    抓內文超出 license_note 的 "titles + links only"，所以選還原。
    還原不準的代價由 cluster 的實體比對吸收，不由編造吸收。
    """
    seg = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    seg = re.sub(r"\.(html?|php|aspx?)$", "", seg)
    words = [w for w in re.split(r"[-_]+", seg) if w]
    return " ".join(w if (w.isupper() or any(c.isdigit() for c in w))
                    else w.capitalize() for w in words)


def adapt_sitemap(source: dict, body: str) -> list[dict]:
    """sitemap.xml → 項目清單。給「沒有 RSS，但 robots.txt 自己宣告 Sitemap:」的官方站。

    合規邊界（紅線 7）：只走站方 robots.txt 主動指出的入口，不猜路徑、不爬全站、
    不抓任何一篇內文；拿到的只有 <loc> 與 <lastmod>。
    摘要一律留空——sitemap 本來就沒有摘要，**空摘要比生出來的摘要好**（紅線 2）。

    設定欄位：
      url_prefix     只收 path 以此開頭的 URL（例：/news/）。缺省＝全收。
      sitemap_hints  遇上 sitemap index 時，只展開 <loc> 含這些字串的子 sitemap。
      max_sitemaps   子 sitemap 展開上限（預設 3），避免一次打爆對方。
    """
    import xml.etree.ElementTree as ET

    prefix = source.get("url_prefix") or ""
    quota = int(source.get("quota_per_run", 50))

    def parse(xml_text: str) -> tuple[str, list[tuple[str, str]]]:
        root = ET.fromstring(xml_text.lstrip("﻿ \r\n\t"))
        tag = root.tag.split("}")[-1]
        child = "sitemap" if tag == "sitemapindex" else "url"
        nodes = root.findall(f"{SM_NS}{child}") or root.findall(child)
        out = []
        for node in nodes:
            loc = node.findtext(f"{SM_NS}loc") or node.findtext("loc") or ""
            mod = node.findtext(f"{SM_NS}lastmod") or node.findtext("lastmod") or ""
            if loc.strip():
                out.append((loc.strip(), mod.strip()))
        return tag, out

    kind, entries = parse(body)

    if kind == "sitemapindex":
        hints = source.get("sitemap_hints") or ([prefix.strip("/")] if prefix else [])
        picked = [loc for loc, _ in entries
                  if not hints or any(h and h in loc for h in hints)]
        picked = picked[: int(source.get("max_sitemaps", 3))]
        entries = []
        for sub in picked:
            status, sub_body, _ = safe_fetch(sub)
            if status == 200 and sub_body:
                entries.extend(parse(sub_body)[1])

    rows = [(loc, mod) for loc, mod in entries
            if not prefix or urlsplit(loc).path.startswith(prefix)]
    # sitemap 不保證排序；lastmod 新的排前面，「今天發生什麼」才問得出來。
    rows.sort(key=lambda r: r[1] or "", reverse=True)

    return [{
        "title": _slug_to_title(loc),
        "summary": "",
        "url": loc,
        "published": mod,
        "author": None,
    } for loc, mod in rows[:quota]]


def adapt_json_api(source: dict, body: str) -> list[dict]:
    """JSON 端點 → 項目清單。目前的使用者是 HN topstories：第一跳只回 id 陣列，
    內容要對每個 id 再打一次 item 端點。這個第二跳用 item_endpoint 表達。

    設定欄位：
      root_path      回應是物件時，陣列藏在哪個 key（例：Algolia 的 "hits"）。
      item_endpoint  第二跳 URL 樣板，含 {id}。缺省＝第一跳回的就是物件陣列。
      field_map      {輸出欄位: 來源欄位}，預設照 HN 的 title / url / by / time / text。
      url_fallback   url 欄位為空時的替代樣板，含 {id}（例：Ask HN 沒有外連）。
      id_field       url_fallback 取 id 用哪個欄位，預設 objectID。
    """
    quota = int(source.get("quota_per_run", 30))
    fm = source.get("field_map") or {"title": "title", "url": "url",
                                     "author": "by", "published": "time",
                                     "summary": "text"}
    data = json.loads(body)
    for key in str(source.get("root_path") or "").split("."):
        if key and isinstance(data, dict):
            data = data.get(key)
    if not isinstance(data, list):
        return []
    tmpl = source.get("item_endpoint")

    records = []
    if tmpl:
        for ident in data[:quota]:
            status, sub, _ = safe_fetch(tmpl.replace("{id}", str(ident)))
            if status != 200 or not sub:
                continue
            try:
                obj = json.loads(sub)
            except ValueError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    else:
        records = [o for o in data[:quota] if isinstance(o, dict)]

    items = []
    for obj in records:
        pub = obj.get(fm.get("published", "published")) or ""
        # HN 的 time 是 unix epoch；下游只認字串日期，這裡就地正規化。
        if isinstance(pub, (int, float)):
            pub = datetime.fromtimestamp(pub, timezone.utc).isoformat()
        url = obj.get(fm.get("url", "url")) or ""
        if not url and source.get("url_fallback"):
            ident = obj.get(source.get("id_field", "objectID"))
            url = source["url_fallback"].replace("{id}", str(ident)) if ident else ""
        items.append({
            "title": obj.get(fm.get("title", "title"), "") or "",
            "summary": re.sub(r"<[^>]+>", " ",
                              str(obj.get(fm.get("summary", "summary")) or ""))[:SUMMARY_CHARS],
            "url": url,
            "published": pub,
            "author": obj.get(fm.get("author", "author")) or None,
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
            "sitemap": adapt_sitemap, "json-api": adapt_json_api,
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
        # 決策仍用 robots_verdict()[0]（＝ robots_allows 的回傳值，抓取行為一個字
        # 沒變），但**標籤改用 reason code**。2026-07-26 實測踩到的洞：
        #   src-kol-thezvi 的 robots.txt 回 401/403，robots_verdict 正確回
        #   (False, "unavailable_403")，重驗端也正確判成 unknown_keep 不寫回設定檔
        #   ——但這裡只取布林值，於是報告印成 `robots_disallow`，
        #   也就是**把量測失敗印成站方政策**。
        # 那正是 07-24 事故的同一個形態，只是這次出現在報告欄位而不是設定檔。
        # 後果不抽象：人看報告會以為對方拒絕，再拿「連三天零產出」去降級一條
        # 其實只是被 WAF 擋住的來源。抓取端保守跳過沒問題，說法不可以說錯。
        stat["robots"], robots_reason = robots_verdict(url)
        stat["robots_reason"] = robots_reason
        if stat["robots"] is False and robots_reason == "unavailable_403":
            stat["status"] = "robots_unknown"
            stat["error"] = "robots.txt 回 401/403，取不到內容，保守跳過（非站方拒絕）"
            return [], stat
        if stat["robots"] is False:
            stat["status"] = "robots_disallow"   # 200 且明文 Disallow，這才是政策
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
              "`robots_unknown` = robots.txt 取不到而保守跳過，不是對方拒絕"
              "（含 401/403：拿不到檔案，多半是 WAF 擋雲端 IP）。",
              "`robots_disallow` = robots.txt 取得成功且明文 Disallow —— "
              "只有這個才是站方政策，也只有這個可以拿來降級。", ""]

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


# 當日快照被同日的下一班整包重寫時，這兩個欄位要沿用**當天第一次**的判定。
#
# 它們描述的是「這一天第一次看到這則」，不是「這一輪看到什麼」。`backfill` 由
# `not st["first_fetch_at"]` 決定，第二班跑的時候 first_fetch_at 已經有值，於是
# 整批變成 false；`is_new` 由 seen.json 決定，第二班也一律 false。把本輪值寫回
# 檔案，早上標好的存量標記就這樣被抹掉。
#
# 壞掉的時候看不出來：檔案還在、筆數一樣、沒有錯誤，只有 report 開頭那句
# 「本輪含 N 筆 backfill，lead_days 與熱度統計應排除」會安靜消失，而該被排除的
# 存量從此跟當期訊號長得一模一樣。一天只跑一班的時代這條路徑永遠踩不到，是
# 2026-07-25 改成每 2 小時一班之後才第一次踩出來的（實測：05:21 那班標了 300
# 筆 backfill，08:13 那班把 300 筆全部翻成 false，警語整段不見）。
DAY_STICKY_FIELDS = ("backfill", "is_new")


def load_day_flags(path: Path) -> dict:
    """讀當日既有快照，回傳 {canonical_url: {sticky 欄位}}。

    檔不存在、空行、壞掉的 JSON 一律當作沒有——保護性讀取，不該讓一行壞資料擋掉
    整班抓取。
    """
    out: dict = {}
    if not path.exists():
        return out
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("url_canonical") or row.get("url")
        if key:
            out[key] = {k: row[k] for k in DAY_STICKY_FIELDS if k in row}
    return out


def carry_day_flags(row: dict, prior: dict) -> dict:
    """就地把當日既有的 sticky 欄位蓋回 row，回傳同一個 row。

    當日沒看過的項目維持本輪判定——那才是它第一次被看到。
    """
    keep = prior.get(row.get("url_canonical") or row.get("url"))
    if keep:
        row.update(keep)
    return row


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

    # 幽靈設定防護：adapter 沒註冊的來源＝寫在設定檔裡但永遠跑不起來。
    # 這種東西看起來像覆蓋範圍，其實是零。dormant 的也要唸出來，因為它就是
    # 「哪天把它拉起來」時會踩到的地雷。（src-hn-frontpage 當過這個地雷。）
    ghosts = [s["id"] for s in sources if s.get("adapter") not in ADAPTERS]
    if ghosts:
        print(f"[warn] {len(ghosts)} 條來源的 adapter 未註冊，永遠跑不起來："
              + ", ".join(ghosts), file=sys.stderr)

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

    sids = sorted({r["source_id"] for r in rows})

    # 先把當日既有快照的 sticky 欄位讀出來，蓋回本輪的 rows，再整包重寫。
    # 順序很重要：report 也吃同一份 rows，不先蓋回去的話，檔案修好了、報告
    # 開頭那句 backfill 警語還是會消失。見 DAY_STICKY_FIELDS 上方的說明。
    prior: dict = {}
    for sid in sids:
        prior.update(load_day_flags(vault / "_corpus" / day / f"{sid}.jsonl"))
    if prior:
        for r in rows:
            carry_day_flags(r, prior)

    for sid in sids:
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
