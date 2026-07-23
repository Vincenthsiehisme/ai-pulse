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
  _probe/state.json                        etag / last_seen（失敗不推進）

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
    """None = 取不到 robots.txt（視為未知，不當成允許）。"""
    try:
        p = urlparse(url)
        rp = RobotFileParser()
        rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(UA, url)
    except Exception:  # noqa: BLE001
        return None


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
        items.append({
            "title": e.get("title", "") or "",
            "summary": re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")[:SUMMARY_CHARS],
            "url": e.get("link", "") or "",
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

def run_source(src: dict, table, state: dict) -> tuple[list[dict], dict]:
    sid = src["id"]
    st = state.get(sid, {})
    stat = {"id": sid, "track": src.get("track"), "tier": src.get("tier"),
            "status": None, "items": 0, "error": None, "robots": None}

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
    out = []
    for it in items:
        text = f"{it['title']} {it['summary']}"
        hits, surfaces = match_entities(text, table)
        out.append({
            **it,
            "source_id": sid,
            "track": src.get("track"),
            "tier": src.get("tier"),
            "url_canonical": canonical_url(it["url"]) if it["url"] else "",
            "first_observed_at": now,          # 見 obsidian-schema 時間三分
            "entity_hits": [e for e, _ in hits],
            "entity_types": sorted({t for _, t in hits}),
            "candidates": harvest_candidates(text, surfaces),
        })
    stat["items"] = len(out)
    state[sid] = {"etag": headers.get("ETag"), "last_run": now}
    return out, stat


def write_report(vault: Path, day: str, rows: list[dict], stats: list[dict],
                 simp_trad: bool) -> Path:
    by_track: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_track[r["track"] or "unknown"].append(r)

    lines = [f"# probe report {day}", "",
             "M1 產出。來源數與條目數不是驗收標準，下面兩個比率才是。", ""]

    lines += ["## 兩個決定性比率", "",
              "| track | 條目 | author 存在率 | 實體命中率 |", "|---|---|---|---|"]
    for track, items in sorted(by_track.items()):
        n = len(items)
        a = sum(1 for i in items if i.get("author"))
        h = sum(1 for i in items if i["entity_hits"])
        lines.append(f"| {track} | {n} | {a}/{n} = {a/n:.0%} | {h}/{n} = {h/n:.0%} |"
                     if n else f"| {track} | 0 | — | — |")
    lines += ["",
              "- **author 存在率**決定人物層與獨立性升級有沒有用；官方線若過低，"
              "people.yaml 只在 KOL 線生效。",
              "- **實體命中率**決定字典往哪長。低命中不代表字典爛，"
              "可能是語料型態與假設不符。", ""]

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

    lines += ["## 來源狀態", "", "| source | track | status | items | robots | error |",
              "|---|---|---|---|---|---|"]
    for s in stats:
        lines.append(f"| {s['id']} | {s['track']} | {s['status']} | {s['items']} | "
                     f"{s['robots']} | {s['error'] or ''} |")

    lines += ["", "## 本輪已知缺口（勿當成已實現）", "",
              f"- 簡繁正規化：{'已啟用 opencc' if simp_trad else '**未啟用**'}"
              "（未啟用時，簡體別名不會命中繁體寫法，反之亦然）",
              "- 中文候選詞收割僅限括號內字串；無括號的中文新詞抽不出來",
              "- 本腳本不聚類、不評分、不開 gate——這些比率只描述語料，不代表 pipeline 效能",
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

    day = date.today().isoformat()
    rows: list[dict] = []
    stats: list[dict] = []
    for src in sources:
        if args.only and src["id"] != args.only:
            continue
        items, stat = run_source(src, table, state)
        stats.append(stat)
        rows.extend(items)
        print(f"[{stat['status']}] {stat['id']}: {stat['items']} items"
              f"{' — ' + stat['error'] if stat['error'] else ''}")
        time.sleep(1)  # 禮貌間隔

    if args.dry_run:
        print(f"\n--dry-run：共 {len(rows)} 筆，未寫檔。")
        heartbeat("dry_run", vault, f"{len(rows)} items")
        return 0

    for sid in {r["source_id"] for r in rows}:
        p = vault / "_corpus" / day / f"{sid}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for r in (x for x in rows if x["source_id"] == sid):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")

    report = write_report(vault, day, rows, stats, simp_trad)
    git_commit(vault, f"probe {day}: {len(rows)} items / {len(stats)} sources")
    ok = sum(1 for s in stats if s["status"] in (200, 304))
    heartbeat("ok", vault, f"{len(rows)} items / {ok}/{len(stats)} sources ok")
    print(f"\nreport → {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
