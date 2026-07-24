#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline self-test for verify-policy-sources.py. No network."""
import importlib.util
import io
import urllib.error
import urllib.request

import os
_HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "v", os.path.join(_HERE, "verify-policy-sources.py"))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

UA = "ai-pulse-tracker/0.1 (+probe)"

ARXIV_ROBOTS = "User-agent: *\nDisallow: /\n"
PERMISSIVE = "User-agent: *\nDisallow: /admin/\nCrawl-delay: 5\n"

RSS_OK = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>Council press</title>
<item><title>A</title><link>https://x/1</link><pubDate>Mon, 20 Jul 2026 10:00:00 GMT</pubDate><guid>g1</guid></item>
<item><title>B</title><link>https://x/2</link><pubDate>Mon, 21 Jul 2026 10:00:00 GMT</pubDate><guid>g2</guid><dc:creator>Someone</dc:creator></item>
</channel></rss>"""

RSS_NOLINK = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>HF-like</title>
<item><title>A</title><guid>https://x/1</guid><pubDate>Mon, 20 Jul 2026 10:00:00 GMT</pubDate></item>
<item><title>B</title><guid>https://x/2</guid><pubDate>Mon, 21 Jul 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeResp(io.BytesIO):
    def __init__(self, body, status=200, ctype="application/xml"):
        super().__init__(body.encode() if isinstance(body, str) else body)
        self.status = status
        self.headers = {"Content-Type": ctype}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_opener(routes):
    def _open(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        assert req.get_header("User-agent") == UA, "UA not propagated"
        for frag, val in routes.items():
            if frag in url:
                if isinstance(val, int):
                    raise urllib.error.HTTPError(url, val, "err", {}, None)
                return FakeResp(val)
        raise urllib.error.URLError("no route")
    return _open


results = []


def case(name, routes, url, expect_allowed, expect_items=None, expect_fallback=None):
    urllib.request.urlopen = make_opener(routes)
    allowed, reason = v.check_robots(url, UA)
    ok = allowed is expect_allowed
    detail = f"robots={allowed!r}"
    if expect_items is not None and allowed is True:
        feed = v.inspect_feed(url, UA)
        ok = ok and feed.get("items") == expect_items
        detail += f" items={feed.get('items')}"
        if expect_fallback is not None:
            ok = ok and feed.get("link_fallback_needed") is expect_fallback
            detail += f" link_fallback={feed.get('link_fallback_needed')}"
    results.append((ok, name, detail, reason))


case("arXiv-style Disallow: / -> DENY",
     {"robots.txt": ARXIV_ROBOTS}, "https://export.arxiv.org/rss/cs.CL", False)

case("permissive robots + healthy RSS -> ALLOW, 2 items",
     {"robots.txt": PERMISSIVE, "pressreleases.ashx": RSS_OK},
     "https://www.consilium.europa.eu/en/rss/pressreleases.ashx", True, 2, False)

case("permissive robots + RSS missing <link> -> flags guid fallback",
     {"robots.txt": PERMISSIVE, "feed.xml": RSS_NOLINK},
     "https://example.org/feed.xml", True, 2, True)

case("robots 403 -> DENY (not 'unknown')",
     {"robots.txt": 403}, "https://example.org/feed.xml", False)

case("robots 404 -> ALLOW (no robots file)",
     {"robots.txt": 404, "feed.xml": RSS_OK}, "https://example.org/feed.xml", True, 2, False)

case("robots 503 -> UNKNOWN (must NOT become allow)",
     {"robots.txt": 503}, "https://example.org/feed.xml", None)

case("robots network failure -> UNKNOWN",
     {}, "https://example.org/feed.xml", None)

# --------------------------------------------------------------- adapter 測試
# 純離線：直接餵 payload 給 adapter，不碰網路。這兩支是 2026-07-25 為了補
# 「來源清單裡沒有 Anthropic」那個洞新加的——沒測過的 adapter 等於沒有的 adapter。
import json as _json  # noqa: E402

import yaml as _yaml  # noqa: E402

_ps = importlib.util.spec_from_file_location(
    "pulse_probe", os.path.join(_HERE, "pulse-probe.py"))
_pp = importlib.util.module_from_spec(_ps)
_ps.loader.exec_module(_pp)


def acase(name, got, want):
    results.append((got == want, name, f"got={got!r}", f"want={want!r}"))


SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
 <url><loc>https://www.anthropic.com/news/claude-opus-5</loc><lastmod>2026-07-24</lastmod></url>
 <url><loc>https://www.anthropic.com/careers/roles</loc><lastmod>2026-07-25</lastmod></url>
 <url><loc>https://www.anthropic.com/news/older-thing</loc><lastmod>2026-07-01</lastmod></url>
</urlset>"""

_sm = _pp.adapt_sitemap({"url_prefix": "/news/", "quota_per_run": 10}, SITEMAP)
acase("sitemap: url_prefix 濾掉非 /news/，且照 lastmod 新到舊",
      [i["title"] for i in _sm], ["Claude Opus 5", "Older Thing"])
acase("sitemap: 摘要留空（sitemap 沒有摘要欄位，不得編造）",
      sorted({i["summary"] for i in _sm}), [""])

_IDX = ('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<sitemap><loc>https://x.test/sitemap-pages.xml</loc></sitemap></sitemapindex>')
acase("sitemap: index 的 hint 沒命中 → 回空清單，不得爆炸",
      _pp.adapt_sitemap({"url_prefix": "/news/"}, _IDX), [])

ALGOLIA = _json.dumps({"hits": [
    {"title": "A", "url": "https://a.test/x", "author": "pg",
     "created_at": "2026-07-24T16:02:00.000Z", "objectID": "1", "story_text": None},
    {"title": "Ask HN", "url": None, "author": "dang",
     "created_at": "2026-07-24T18:00:00.000Z", "objectID": "2", "story_text": "<p>hi</p>"}]})
_HN_SRC = {"root_path": "hits", "quota_per_run": 30,
           "field_map": {"title": "title", "url": "url", "author": "author",
                         "published": "created_at", "summary": "story_text"},
           "url_fallback": "https://news.ycombinator.com/item?id={id}",
           "id_field": "objectID"}
_hn = _pp.adapt_json_api(_HN_SRC, ALGOLIA)
acase("json-api: root_path 挖得到 hits", len(_hn), 2)
acase("json-api: url 為空時走 url_fallback（Ask HN 沒有外連）",
      _hn[1]["url"], "https://news.ycombinator.com/item?id=2")
acase("json-api: HTML 標籤剝乾淨", _hn[1]["summary"], " hi ")
acase("json-api: unix epoch 正規化成 ISO 日期",
      _pp.adapt_json_api({"quota_per_run": 5},
                         _json.dumps([{"title": "T", "url": "u", "by": "a",
                                       "time": 1769270400}]))[0]["published"][:10],
      "2026-01-24")
acase("json-api: 回應不是陣列 → 回空清單，不得爆炸",
      _pp.adapt_json_api({}, '{"error":"nope"}'), [])

# ------------------------------------------------- robots：抓不到 vs 不准抓
# 這是 07-24 事故最深的一層。舊版把兩者壓成同一個 False，一次 403 就被存進
# sources.yaml 變成永久判決，整條 OpenAI 線靜靜關掉。抓取端保守跳過沒問題，
# 但**判決不可以由量測失敗做出**——所以要有 reason code 把兩者分開。
_rcases = [
    ("robots 403 → 抓取端仍拒絕，但原因是 unavailable_403（非政策）",
     403, None, (False, "unavailable_403")),
    ("robots 200 + Disallow: / → disallow，這才是站方政策",
     200, "User-agent: *\nDisallow: /\n", (False, "disallow")),
    ("robots 200 + 放行 → ok", 200, PERMISSIVE, (True, "ok")),
    ("robots 404 → no_robots，依慣例放行", 404, None, (True, "no_robots")),
    ("robots 503 → unreachable，不得變成放行", 503, None, (None, "unreachable")),
]
for _name, _st, _body, _want in _rcases:
    _pp.safe_fetch = (lambda st, bd: (lambda u: (st, bd, {})))(_st, _body)
    acase(_name, _pp.robots_verdict("https://example.org/feed.xml"), _want)

_pp.safe_fetch = lambda u: (_ for _ in ()).throw(OSError("boom"))
acase("robots 連線例外 → (None, error)，交呼叫端保守跳過",
      _pp.robots_verdict("https://example.org/feed.xml"), (None, "error"))

_pp.safe_fetch = lambda u: (403, None, {})
acase("robots_allows 只是薄包裝：403 仍回 False，抓取端行為一個字沒變",
      _pp.robots_allows("https://example.org/feed.xml"), False)

# 重驗端的分岔：同樣是 False，403 不得寫回設定檔，明文 Disallow 才可以。
_rc = importlib.util.spec_from_file_location(
    "recheck", os.path.join(_HERE, "pulse-robots-recheck.py"))
_rr = importlib.util.module_from_spec(_rc)
_rc.loader.exec_module(_rr)
_rr._probe.safe_fetch = lambda u: (403, None, {})
_DOC = {"official_sources": [{"id": "s1", "lifecycle": "probing",
                              "robots_ok": True, "endpoint": "https://e.test/f"}]}
acase("重驗：403 → unknown_keep（不得把 WAF 擋包寫成 robots_ok: false）",
      _rr.check(_DOC)[0]["verdict"], "unknown_keep")
acase("重驗：403 的 unknown_keep 不產生任何 robots_ok 異動",
      [c for c in _rr.apply_changes(_DOC, _rr.check(_DOC)) if c["field"] == "robots_ok"], [])
_rr._probe.safe_fetch = lambda u: (200, "User-agent: *\nDisallow: /\n", {})
acase("重驗：200 + Disallow → closed（真政策才寫得回去）",
      _rr.check(_DOC)[0]["verdict"], "closed")

# 幽靈設定防護：設定檔裡每一條來源的 adapter 都必須註冊過。
# 未註冊的來源看起來像覆蓋範圍，其實永遠是零——src-hn-frontpage 當過這個地雷。
_cfg = _yaml.safe_load(
    open(os.path.join(_HERE, "..", "_config", "sources.yaml"), encoding="utf-8"))
_ghosts = [s["id"] for k in ("official_sources", "kol_sources", "aggregator_sources")
           for s in (_cfg.get(k) or []) if s.get("adapter") not in _pp.ADAPTERS]
acase("sources.yaml: 沒有 adapter 未註冊的幽靈來源", _ghosts, [])
acase("sources.yaml: 官方線含 Anthropic（07-24 漏抓 Opus 5 的根因）",
      any(s.get("owner") == "Anthropic" for s in _cfg.get("official_sources") or []),
      True)

acase("sources.yaml: KOL 線不是空的（空的話 lead_days 恆不可計算）",
      len(_cfg.get("kol_sources") or []) > 0, True)
acase("sources.yaml: KOL 各條 media_group 互不相同"
      "（都填 Substack 的話獨立來源數會塌成 1，等於自己作弊過門檻 4）",
      len({s["media_group"] for s in _cfg["kol_sources"]}),
      len(_cfg["kol_sources"]))
acase("sources.yaml: KOL 一律非 tier 1（即使本人任職於被追蹤公司）",
      sorted({s["tier"] for s in _cfg["kol_sources"]}), [2])
acase("sources.yaml: KOL 一律 can_satisfy_primary: false",
      sorted({bool(s["can_satisfy_primary"]) for s in _cfg["kol_sources"]}), [False])
# robots_ok 只有兩種誠實的值：真的讀過 robots.txt → true；本機量不到 → null。
# 沒讀到卻寫 false，就是把量測失敗偽裝成站方政策——那正是 07-24 的病灶。
acase("sources.yaml: 沒有任何 KOL 條目寫著未經證實的 robots_ok: false",
      [s["id"] for s in _cfg["kol_sources"] if s.get("robots_ok") is False], [])
acase("sources.yaml: robots_ok 為 null 者必須明示 revive_when_allowed（否則永遠不會被重驗）",
      [s["id"] for s in _cfg["kol_sources"]
       if s.get("robots_ok") is None and not s.get("revive_when_allowed")], [])

# ------------------------------------------------ 重驗：明示 opt-in 才會被復活
_rr._probe.safe_fetch = lambda u: (200, PERMISSIVE, {})
_D2 = {"kol_sources": [
    {"id": "opt-in", "lifecycle": "dormant", "robots_ok": None,
     "revive_when_allowed": True, "endpoint": "https://a.test/feed"},
    {"id": "hand-off", "lifecycle": "dormant", "robots_ok": None,
     "endpoint": "https://b.test/feed"},
]}
_ch = _rr.apply_changes(_D2, _rr.check(_D2), revive=True)
acase("重驗：robots_ok 為 null + revive_when_allowed → 真網路放行時升 probing",
      [c["to"] for c in _ch if c["id"] == "opt-in" and c["field"] == "lifecycle"],
      ["probing"])
acase("重驗：同樣是 null 但沒有明示旗標 → 不碰（漏填不等於授權復活）",
      [c for c in _ch if c["id"] == "hand-off" and c["field"] == "lifecycle"], [])

# ------------------------------------------------------- 覆蓋率看門狗
# 這幾條測的是「警報會不會在該叫的時候叫、在不該叫的時候閉嘴」。
# 後者跟前者一樣重要：天天誤叫的警報，三天後就會被人整條關掉。
import tempfile  # noqa: E402
from datetime import date as _date  # noqa: E402
from pathlib import Path  # noqa: E402

_ms = importlib.util.spec_from_file_location(
    "pulse_monitor", os.path.join(_HERE, "pulse-monitor.py"))
_mm = importlib.util.module_from_spec(_ms)
_ms.loader.exec_module(_mm)

_TODAY = _date(2026, 7, 25)
_ENT = {"companies": [
    {"id": "openai", "canonical": "OpenAI", "aliases": ["Open AI"]},
    {"id": "anthropic", "canonical": "Anthropic", "aliases": []},
    {"id": "meta", "canonical": "Meta", "aliases": []},
]}


def _vault(days):
    """days: {'2026-07-25': [corpus row, ...]} → 一個臨時 vault 路徑。"""
    root = Path(tempfile.mkdtemp())
    for d, rows in days.items():
        p = root / "_corpus" / d
        p.mkdir(parents=True)
        (p / "src-x.jsonl").write_text(
            "\n".join(_json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return root


_SRC_OK = {"official_sources": [{"id": "s-oa", "owner": "OpenAI", "lifecycle": "active"}]}


def _cov(watch, sources, days):
    cfg = dict(sources)
    cfg["coverage_watch"] = watch
    return _mm.coverage(_vault(days), _TODAY, cfg, _ENT)


_c1 = _cov({"window_days": 30, "max_silent_days": 14,
            "must_watch": [{"entity_id": "anthropic", "label": "Anthropic"}]},
           _SRC_OK, {"2026-07-25": [{"title": "hello", "summary": ""}]})
acase("覆蓋率：沒有任何來源指向該實體 → no_source，第一天就叫（Opus 5 那格）",
      (_c1["must_watch"][0]["reason"], _c1["must_watch"][0]["alerting"]),
      ("no_source", True))

_c2 = _cov({"window_days": 30, "max_silent_days": 14,
            "must_watch": [{"entity_id": "anthropic", "label": "Anthropic",
                            "pending": True}]},
           _SRC_OK, {"2026-07-25": [{"title": "hello", "summary": ""}]})
acase("覆蓋率：pending 仍列出破洞，但不觸警（天天紅的燈等於沒有燈）",
      (_c2["must_watch"][0]["reason"], _c2["must_watch"][0]["alerting"]),
      ("no_source", False))

_c3 = _cov({"window_days": 30, "max_silent_days": 14,
            "must_watch": [{"entity_id": "openai", "label": "OpenAI"}]},
           _SRC_OK, {"2026-07-25": [{"title": "unrelated", "summary": ""}]})
acase("覆蓋率：有來源但語料只有 1 天 → 不判 silent（新 vault 不該一開機就滿螢幕紅字）",
      (_c3["history_days"], _c3["must_watch"][0]["reason"]), (1, None))

_c4 = _cov({"window_days": 60, "max_silent_days": 14,
            "must_watch": [{"entity_id": "openai", "label": "OpenAI"}]},
           _SRC_OK, {"2026-06-01": [{"title": "old", "summary": ""}],
                     "2026-07-25": [{"title": "unrelated", "summary": ""}]})
acase("覆蓋率：語料期間夠長且該實體從未出現 → silent",
      _c4["must_watch"][0]["reason"], "silent")

# entity_hits 是 probe 用 entities.yaml 判的，跟聚類同一把尺；監看自己的 regex 只是退路。
_c5 = _cov({"window_days": 30, "max_silent_days": 14,
            "must_watch": [{"entity_id": "openai", "label": "OpenAI"}]},
           _SRC_OK,
           {"2026-07-25": [{"title": "OpenAI ships thing", "summary": "",
                            "entity_hits": ["meta"]}]})
acase("覆蓋率：有 entity_hits 時以它為準，不用自己的 regex 覆寫聚類的判定",
      _c5["must_watch"][0]["corpus_hits"], 0)

_c6 = _cov({"window_days": 30, "max_silent_days": 14,
            "must_watch": [{"entity_id": "meta", "label": "Meta"}]},
           {"official_sources": [{"id": "s-m", "owner": "Meta", "lifecycle": "active"}]},
           {"2026-07-25": [{"title": "metadata schema update", "summary": ""}]})
acase("覆蓋率：alias「Meta」不得命中 metadata（假陽性會讓看門狗在沒東西時安靜）",
      _c6["must_watch"][0]["corpus_hits"], 0)

_ent_ids = {i["id"] for sec in ("companies", "product_lines", "infrastructure")
            for i in (_yaml.safe_load(
                open(os.path.join(_HERE, "..", "_config", "entities.yaml"),
                     encoding="utf-8")).get(sec) or [])}
acase("設定一致性：coverage_watch 每個 entity_id 都在 entities.yaml 裡查得到"
      "（查不到會退化成用 label 當別名，看起來有在看其實在看空氣）",
      [w["entity_id"] for w in _cfg["coverage_watch"]["must_watch"]
       if w["entity_id"] not in _ent_ids], [])

print("offline self-test\n" + "-" * 70)
fails = 0
for ok, name, detail, reason in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n         {detail} | {reason}")
    fails += 0 if ok else 1
print("-" * 70)
print(f"{len(results) - fails}/{len(results)} passed")
raise SystemExit(1 if fails else 0)
