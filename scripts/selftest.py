#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline self-test for verify-policy-sources.py. No network."""
import importlib.util
import io
import urllib.error
import urllib.request

import os
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from lib.sources import SECTIONS as _SECTIONS  # noqa: E402  分節清單單一真相源

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

# ------------------------------------------- author 分類（5b 人物層的唯一原料）
# 這批 case 不是想像出來的，每一條都是 2026-07-26 拿 3 天 859 筆真語料回頭量到的
# 實例。分類器的錯有方向性：判成 person 的假陽性會讓「有多少自然人在講」虛胖，
# 而 person 是 5b 唯一乾淨的桶；判成 org / handle 的假陰性只是低估。所以下面
# 假陽性那幾條是紅線，假陰性那幾條是修正。
_acases = [
    # 假陽性（修正前是 person，實際是組織）。ORG_PAT 原本收 team/labs/staff，
    # 沒收 writers/community，兩個字都大寫開頭就直接落進 person。
    ("NVIDIA Writers", "org"),
    ("GeForce NOW Community", "org"),
    # 全大寫縮寫是機構，不是 login。修正前落在 handle，方向不算錯但桶子錯。
    ("NVIDIA", "org"),
    # 假陰性一：學位不是第二個人。修正前因為逗號被判 multi_person。
    ("Sebastian Raschka, PhD", "person"),
    ("Jane Doe, Ph.D.", "person"),
    ("John Smith Jr.", "person"),
    # 假陰性二：Substack 的 "(hidden)" 是平台註記不是姓名，剝掉就是單詞 login。
    ("karpathy (hidden)", "handle"),
    # 剝除必須守得住的邊界：真的共同作者串一個都不能被吃掉。
    ("Son Ho, Cédric Fournet, Antoine Delignat-Lavaud", "multi_person"),
    ("Jeremiah (Miah) Wander, Cas Simons", "multi_person"),   # 括號在中間，不剝
    ("Alice Chen and Bob Lee", "multi_person"),
    # 既有行為的回歸樁：這些在修正前後都必須一致。
    ("Ethan Mollick", "person"),
    ("khluu", "handle"),
    ("dependabot[bot]", "machine"),
    ("Microsoft Research Team", "org"),
    ("", "none"),
    (None, "none"),
    # 剝完只剩空字串（author 本身就是平台註記）→ none，不得變成 handle。
    ("(hidden)", "none"),
]
for _a, _want in _acases:
    acase(f"author 分類：{_a!r} → {_want}", _pp.classify_author(_a), _want)

# PERSON_KINDS 是 checklist 5b 的分母定義，這次刻意沒動。
# 寫成測試是因為它很容易被「順手」改掉：把 org 或 handle 加進去，5b 的分母
# 會一夜變大而報告上看不出任何異狀。
acase("PERSON_KINDS 維持 {person, multi_person}（本次修分類器，不動 5b 定義）",
      sorted(_pp.PERSON_KINDS), ["multi_person", "person"])

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
_ghosts = [s["id"] for k in _SECTIONS
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

# ------------------------------------------------------------ 媒體線（2026-07-26 開）
# 開線的理由是量出來的：48 個 Event，其中 47 個 independent_sources: 1。
# 因為 25 條來源裡 0 條媒體，而官方線在結構上不可能產生第二個獨立聲音——
# 一家公司只有一個 media_group，independent_voices 會把它們併成同一個元件。
# `evidence.need_independent_tier2: 2` 從上線到今天沒有一次有機會被滿足。
#
# 這一組測試釘的是「媒體補的是佐證，不是權威」。媒體線一旦被寫成 tier 1 或
# can_satisfy_primary: true，等於用設定檔宣告轉述是一手發布，紅線 2 就從內部被打開了。
acase("sources.yaml: 媒體線不是空的（空的話 need_independent_tier2 永遠沒有輸入）",
      len(_cfg.get("media_sources") or []) > 0, True)
acase("sources.yaml: 媒體各條 media_group 互不相同"
      "（Ars 與 Wired 同屬 Condé Nast，兩條都收就會塌成 1 個獨立聲音）",
      len({s["media_group"] for s in _cfg["media_sources"]}),
      len(_cfg["media_sources"]))
acase("sources.yaml: 媒體線一律 track media（掉回 official 會在評分層被當一手發布）",
      sorted({s["track"] for s in _cfg["media_sources"]}), ["media"])
acase("sources.yaml: 媒體線一律 tier 2（報導不是一手，tier 1 是唯一能滿足 primary 的門）",
      sorted({s["tier"] for s in _cfg["media_sources"]}), [2])
acase("sources.yaml: 媒體線一律 can_satisfy_primary: false",
      sorted({bool(s["can_satisfy_primary"]) for s in _cfg["media_sources"]}), [False])
acase("sources.yaml: 沒有任何媒體條目寫著未經證實的 robots_ok: false"
      "（本機 403 分不出 WAF 擋包與站方政策，寫 false 就是把量測失敗當判決）",
      [s["id"] for s in _cfg["media_sources"] if s.get("robots_ok") is False], [])

# can_satisfy_primary 在碼裡沒有任何消費者（grep scripts/*.py 是空的）——
# 真正把關的是 pulse-cluster.rescore() 裡的 `tier == 1 and role != "aggregator"`。
# 所以這個欄位目前只是宣告。這條測試把宣告與實際把關的那把尺綁在一起：
# 只要有人寫 can_satisfy_primary: false 卻給 tier 1，兩者就矛盾，紅。
acase("sources.yaml: 任何 can_satisfy_primary: false 的來源都不得是 tier 1"
      "（tier 1 才是 rescore() 實際認的 primary 資格，欄位不能跟它說反話）",
      sorted(s["id"] for k in _SECTIONS for s in (_cfg.get(k) or [])
             if s.get("can_satisfy_primary") is False and s.get("tier") == 1), [])

# 評分層的分岔。effective_role 少了 media 那一支，media 會一路掉到最下面的
# official 分支拿到 "primary"：_authority 多 3 分、_originality 直接給滿 15
# ——與官方公告同分。那是用評分把轉述包裝成第一手。
from lib.quality import _authority as _qa  # noqa: E402
from lib.quality import _originality as _qo  # noqa: E402
from lib.quality import effective_role as _er  # noqa: E402
acase("evaluate: track media → effective_role 'media'"
      "（回 'primary' 的話，報導的 originality 會跟官方公告同分）",
      _er("media", "media", "media"), "media")
acase("evaluate: 官方線不受影響，仍回 primary（這條擋的是「把 media 分岔寫在太前面」）",
      _er("official", "company", "announcement"), "primary")
acase("evaluate: media 的 originality 低於一手發布（7 vs 15，差距要留著）",
      (_qo("media", None), _qo("primary", None)), (7, 15))
acase("evaluate: media 拿不到 _authority 的一手加成（同 authority 分數下少 3）",
      _qa("primary", 90) - _qa("media", 90), 3)

# 分節清單單一真相源。這串 tuple 曾經被硬寫在六個腳本裡，加第四節要改九個地方，
# 漏掉任何一個都是靜默失效：漏 probe＝整條線不抓、漏 score＝抓到不評分、
# 漏 cluster＝tier 退回 3 把獨立性算錯、漏 robots-recheck＝403 假陰性永久化。
# 四種都不會讓任何東西變紅，跟 07-24 漏抓 Claude Opus 5 是同一個形態。
import glob as _glob  # noqa: E402
_hard = sorted(os.path.basename(p) for p in _glob.glob(os.path.join(_HERE, "**", "*.py"),
                                                       recursive=True)
               if os.path.basename(p) not in ("sources.py", "selftest.py")
               and "aggregator_sources" in open(p, encoding="utf-8").read())
acase("scripts/: 分節清單只准有一份（除 lib/sources.py 外不得再硬寫 'aggregator_sources'）",
      _hard, [])
acase("lib/sources.py: SECTIONS 四節齊全且官方線排第一"
      "（probe 照順序抓，一手先佔住 first_fetch_at，lead_days 才量得到正號差值）",
      list(_SECTIONS),
      ["official_sources", "media_sources", "kol_sources", "aggregator_sources"])

# 開媒體線**不會**讓熱度活過來，這條測試就是要讓那個誤會沒有生存空間。
# pulse-cluster.rescore() 呼叫 score_event 時 metrics=[]，於是 platforms=regions=0，
# heat 的可達上限＝min(獨立,5)*8 + freshness*0.08 ≦ 40 + 8 = 48。
# gate.yaml 的 heat_threshold: 70 因此結構上跨不過去，unsupported_heat 永遠不會觸發。
# 正確的做法是記錄這個上限並釘住它，不是把公式改大讓數字好看——那就是紅線 4
# 「禁止把手工分數包裝成已測量熱度」。
from lib import scoring as _sc  # noqa: E402
_heat_ceiling = max(_sc.score_event([90], 2, ind, metrics=[], age_hours=0)["heat"]
                    for ind in range(0, 9))
acase("heat 上限：metrics=[] 時 heat 到頂 48，遠低於 gate 的 70"
      "（媒體線只修 independent_sources 與 confidence，修不了熱度；"
      "要讓這條測試變綠必須先真的收集社群指標，不是調公式）",
      _heat_ceiling, 48)
acase("gate.yaml: heat_threshold 仍高於可達上限 → 這三個門檻目前是死設定，"
      "得標註為未消費而不是假裝生效",
      _yaml.safe_load(open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
                           encoding="utf-8"))["readiness"]["heat_threshold"] > _heat_ceiling,
      True)

# ---------------------------------------------- 人物層：獨立性 + 參照完整性
# 獨立性語意（框架規則第 5 條：source + author + media group）。
# 2026-07-26 之前只做了 media group 那一半，同一個人在兩個站台發表會被算成
# 兩個獨立來源——「heat ≥70 需 ≥2 獨立來源」這道門會被自己的設定檔開掉。
import sys as _sys  # noqa: E402
_sys.path.insert(0, _HERE)
from lib.cluster import independent_voices as _iv  # noqa: E402

acase("獨立性：person_id 全空時，結果與舊版 distinct media_group 完全相同"
      "（這條性質是本次改動可以安全上線的依據，不准回歸）",
      _iv([("a", {"media_group": "X"}), ("b", {"media_group": "Y"}),
           ("c", {"media_group": "X"})]), 2)
acase("獨立性：同一個人在兩個站台發表 → 1（一個人不會因為換平台變成兩個聲音）",
      _iv([("a", {"media_group": "Blog", "person_id": "p1"}),
           ("b", {"media_group": "YouTube", "person_id": "p1"})]), 1)
acase("獨立性：同一刊物的兩位作者 → 1（同一個編輯台不是兩個獨立聲音；"
      "這條擋的是「把 key 從 media_group 換成 person_id」那種錯誤修法）",
      _iv([("a", {"media_group": "Interconnects", "person_id": "p1"}),
           ("b", {"media_group": "Interconnects", "person_id": "p2"})]), 1)
acase("獨立性：不同人不同刊物 → 2（合併只在該合併時發生，不能一路塌到 1）",
      _iv([("a", {"media_group": "M1", "person_id": "p1"}),
           ("b", {"media_group": "M2", "person_id": "p2"})]), 2)
acase("獨立性：遞移刻意成立且只往保守倒——A 在 X/Y 發表、B 也在 Y 發表 → 1",
      _iv([("a", {"media_group": "X", "person_id": "pA"}),
           ("b", {"media_group": "Y", "person_id": "pA"}),
           ("c", {"media_group": "Y", "person_id": "pB"})]), 1)
acase("獨立性：兩個欄位都空 → 退回 source_id，維持舊行為",
      _iv([("s1", {}), ("s2", {})]), 2)
acase("獨立性：來源查不到（cfg 為 None）不得爆炸",
      _iv([("s1", None), ("s1", None)]), 1)

# 參照完整性。person_id 這個欄位在 2026-07-26 之前是純裝飾——範本寫著「必填，
# 對應 people.yaml」，而 people.yaml 根本不存在。這兩條測試的用意是讓那種狀態
# 不可能再次悄悄發生：id 指向空氣會紅，人物沒有來源支撐也會紅。
_ppl = _yaml.safe_load(
    open(os.path.join(_HERE, "..", "_config", "people.yaml"), encoding="utf-8"))
_people_ids = {p["id"] for p in (_ppl.get("people") or [])}
_used = {s["person_id"] for k in _SECTIONS
         for s in (_cfg.get(k) or []) if s.get("person_id")}
acase("people.yaml: sources.yaml 用到的 person_id 都查得到（不准指向空氣）",
      sorted(_used - _people_ids), [])
acase("people.yaml: 每個人都至少對到一條來源"
      "（這個檔是「已經有來源的人」的登錄表，不是 AI 名人清單）",
      sorted(_people_ids - _used), [])
acase("people.yaml: sources 反向索引與 sources.yaml 一致",
      sorted(pid for p in (_ppl.get("people") or []) for pid in [p["id"]]
             if {s["id"] for k in _SECTIONS
                 for s in (_cfg.get(k) or []) if s.get("person_id") == p["id"]}
             != set(p.get("sources") or [])), [])
acase("people.yaml: KOL 線每一條都填了 person_id（漏填會高估獨立性，方向是危險的那邊）",
      [s["id"] for s in _cfg["kol_sources"] if not s.get("person_id")], [])
acase("people.yaml: 沒有 affiliation 欄位（任職會過期又無合規自動來源，"
      "一旦存在就會有人拿它參與判斷；要加得先有驗證程序）",
      [p["id"] for p in (_ppl.get("people") or []) if "affiliation" in p], [])

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

# 反向的那一半（2026-07-26 新增）。上面那條擋的是「清單列了字典沒有的」，
# 擋不到真正發生過的那種漏：**字典有、清單沒有**。2026-07-26 實測時
# entities.yaml 有 32 家 status: active 的公司，coverage_watch 只列 12 家，
# 其餘 20 家在覆蓋率報表上連一格都不會出現——沒有來源，也沒有承認沒有來源，
# 所以那一格永遠不會紅。這正是 07-24 漏抓 Claude Opus 5 的同一種形狀：
# 不是燈亮紅色沒人看，是根本沒有那盞燈。
#
# 只查 companies，且只查 status: active：
#   product_lines / infrastructure 是「東西」不是「發布主體」，沒有官方線可對應；
#   status 不是 active 的（已併購 / 已停運）本來就不該逼人補來源。
# 要豁免某一家時，做法是去 must_watch 加一行並掛 pending: true——也就是**白紙黑字
# 寫下「這家我們還沒在看」**，而不是讓它繼續從清單上消失。這條測試的用意就是
# 把「不看」從預設值變成一個要動手寫下來的決定。
_active_companies = {
    c["id"] for c in (_yaml.safe_load(
        open(os.path.join(_HERE, "..", "_config", "entities.yaml"),
             encoding="utf-8")).get("companies") or [])
    if c.get("status", "active") == "active"}
_watched_ids = {w["entity_id"] for w in _cfg["coverage_watch"]["must_watch"]}
acase("設定一致性：entities.yaml 每家 active 公司都要在 coverage_watch 出現"
      "（沒列＝沒有來源也沒承認沒來源，那一格永遠不會紅）",
      sorted(_active_companies - _watched_ids), [])

# ------------------------------------------------- 星速榜中文描述（ghdesc）
# 這一層唯一會出事的地方是「譯文跟原文脫鉤」：上游改了 description，榜上還掛著
# 一句在講舊版本的漂亮中文。所以測的重點不是翻得好不好（那是潤稿端的事），
# 是**綁定失效時會不會誠實地退回英文**，以及退件會不會被靜靜吞掉。
import sys as _sys  # noqa: E402

_sys.path.insert(0, _HERE)
from lib import ghdesc as _gd  # noqa: E402

_da = importlib.util.spec_from_file_location(
    "gh_desc_apply", os.path.join(_HERE, "pulse-github-desc-apply.py"))
_dam = importlib.util.module_from_spec(_da)
_da.loader.exec_module(_dam)

_EN = "A toolkit for building agents"
_ZH = "拿來組 agent 的工具包"


def _repos(desc):
    return [{"full_name": "acme/kit", "desc": desc, "language": "Python",
             "topics": ["llm"], "stars": 1200, "url": "https://x/acme/kit"}]


_store_ok = {"acme/kit": {"zh": _ZH, "src_hash": _gd.src_hash(_EN), "at": "t"}}

acase("ghdesc：src_hash 對得上 → 中文掛上去",
      _gd.attach(_repos(_EN), _store_ok)[0]["desc_zh"], _ZH)
acase("ghdesc：上游改了 description（雜湊對不上）→ 中文作廢退回英文，"
      "寧可空著也不掛一句在講舊版本的中文",
      _gd.attach(_repos(_EN + " and tools"), _store_ok)[0]["desc_zh"], "")
acase("ghdesc：有效譯文不進待譯清單",
      _gd.pending(_repos(_EN), _store_ok), [])
_p = _gd.pending(_repos(_EN + " and tools"), _store_ok)
acase("ghdesc：描述改過的 repo 自動重排進待譯清單",
      [t["full_name"] for t in _p], ["acme/kit"])
acase("ghdesc：重譯的條目附上舊譯文，潤稿端才知道這不是全新的 repo",
      _p[0]["stale_zh"], _ZH)
acase("ghdesc：從沒譯過的 repo，stale_zh 是 None（跟「重譯」區分得開）",
      _gd.pending(_repos(_EN), {})[0]["stale_zh"], None)

acase("apply：乾淨的一行過關，並吃掉句尾句號（榜是一行字不是句子）",
      _dam.validate("acme/kit", "拿來組 agent 的工具包。", _EN)[:2], (_ZH, None))
acase("apply：英文原樣貼回來不算翻譯 → 退件",
      _dam.validate("acme/kit", _EN, _EN)[1],
      "沒有任何中文字（英文原樣貼回來不算翻譯）")
acase("apply：空白 → 退件",
      _dam.validate("acme/kit", "   ", _EN)[1], "空白")
acase(f"apply：超過 {_dam.MAX_LEN} 字 → 退件（版面是一行）",
      _dam.validate("acme/kit", "工" * (_dam.MAX_LEN + 1), _EN)[1],
      f"超過 {_dam.MAX_LEN} 字（榜是一行字的版面）")
acase("apply：AI 腔套話 → 退件",
      _dam.validate("acme/kit", "值得關注的 agent 工具包", _EN)[1],
      "含 AI 腔套話：值得關注")
acase("apply：不在當下榜單上的 repo → 退件（榜換過了，別亂寫進去）",
      _dam.validate("ghost/repo", _ZH, None)[1],
      "不在目前榜單上（榜換過了，下次 prep 會再排進來）")
# voice_clean.clean 回的是 tuple。這條同時測「中國用語有換掉」與「apply 有把
# tuple 拆開」——沒拆的話 zh 會變成一整串 tuple 的字串，長度爆表、CJK 也還在，
# 前四關全部放行，最後是榜上掛一句 "('...', [...])"。這種錯只有測得到才看得到。
_v_cn = _dam.validate("acme/kit", "短視頻的推薦引擎工具包", _EN)
acase("apply：中國用語走 voice_clean 後洗（跟 enrich 同一支後洗）",
      _v_cn[0], "短影音的推薦引擎工具包")
acase("apply：後洗改了什麼要帶回來（不能只有機器自己知道）",
      [c[1] for c in _v_cn[2]], ["短視頻"])

# ------------------------------------------- 來源層健康分（2026-07-26 接上）
# 規格：references/source-lifecycle.md。這一組測試的重心不在「會不會降級」，
# 而在**不會亂降級**。自動降級是這個 vault 最危險的一種自動化：漏抓一條壞掉的
# 來源只是晚幾天發現，自動關掉一條好來源則沒有自癒路徑——07-24 漏抓
# Claude Opus 5 就是後者。所以下面「不記分 / 不降級」那幾條是紅線，
# 「會降級」那幾條反而只是功能確認。
_hs = importlib.util.spec_from_file_location(
    "pulse_source_health", os.path.join(_HERE, "pulse-source-health.py"))
_sh = importlib.util.module_from_spec(_hs)
_hs.loader.exec_module(_sh)

_TH = _yaml.safe_load(open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
                          encoding="utf-8"))["source_health"]

acase("健康分：gate.yaml 的 source_health 現在真的有消費者（門檻全讀得到）",
      sorted(k for k in ("success_gain", "not_modified_gain", "failure_penalty",
                         "severe_failure_penalty", "degrade_after_consecutive",
                         "quarantine_after_consecutive", "recover_after_consecutive")
             if k not in _TH), [])

acase("健康分：200 → success", _sh.classify(200), "success")
acase("健康分：304 → not_modified", _sh.classify(304), "not_modified")
acase("健康分：503 → failure", _sh.classify(503), "failure")
acase("健康分：抓取例外 → failure", _sh.classify("error"), "failure")
acase("健康分：404 → severe_failure（端點不在了，唯一明確是來源那邊變了的訊號）",
      _sh.classify(404), "severe_failure")
# 下面五條是紅線。任何一條變成 failure，這支腳本就會開始把量測失敗當成來源壞掉。
acase("健康分：403 不記分（WAF 擋容器 IP／路徑錯／真要登入，這端分不出來）",
      _sh.classify(403), "neutral")
acase("健康分：401 不記分", _sh.classify(401), "neutral")
acase("健康分：429 不記分（那是站方說我們太快，該調的是 quota_per_run）",
      _sh.classify(429), "neutral")
acase("健康分：robots_disallow / robots_unknown 不記分"
      "（robots 是合規政策不是健康度，混在一起會讓一次 robots 假陰性同時觸發降級）",
      [_sh.classify("robots_disallow"), _sh.classify("robots_unknown")],
      ["neutral", "neutral"])
acase("健康分：沒見過的狀態不記分（誤差方向要是「沒罰到」而不是「錯殺」）",
      _sh.classify("something_new_in_2027"), "neutral")
acase("健康分：沒見過的 4xx 也走 catch-all 不記分（不准出現「未知 4xx 一律算失敗」）",
      _sh.classify(418), "neutral")
# NEUTRAL_STATUSES 目前刪掉行為不會變（catch-all 也回 neutral），所以它需要一條
# 測試才不是裝飾品：這條釘住成員名單。哪天有人把 catch-all 改成「未知 4xx 算失敗」，
# 401/403 靠的就是留在這個集合裡，而不是靠沒人動到 catch-all。
acase("健康分：NEUTRAL_STATUSES 的成員逐一釘住"
      "（這個集合是「已知且刻意不記分」，跟 catch-all 的「不知道就不判」意思不同）",
      sorted(_sh.NEUTRAL_STATUSES, key=lambda x: (isinstance(x, str), str(x))),
      [401, 403, 429, "robots_disallow", "robots_unknown",
       "skipped_lifecycle", "unsupported_adapter"])

_SRC1 = {"s1": {"id": "s1", "lifecycle": "probing"}}


def _runs(*statuses):
    return [{"at": f"t{i}", "day": "2026-07-26",
             "sources": [{"id": "s1", "status": s, "items": 0, "error": None}]}
            for i, s in enumerate(statuses)]


acase("健康分：200 但 0 筆仍是成功（安靜的 feed 是健康的 feed，"
      "src-mistral-news 連兩天 200／0 筆——罰它等於逼系統偏好吵的來源）",
      _sh.tally(_runs(200, 200, 200), _TH, _SRC1)["s1"]["consecutive_failures"], 0)
acase("健康分：滿分不會超過 100（連續成功不得讓分數無限膨脹）",
      _sh.tally(_runs(*([200] * 30)), _TH, _SRC1)["s1"]["score"], 100)
acase("健康分：分數下限 0（連續失敗不得掉成負數）",
      _sh.tally(_runs(*([404] * 30)), _TH, _SRC1)["s1"]["score"], 0)
acase("健康分：中性不歸零連續失敗數"
      "（否則一條每班在 404 與 403 之間輪流的來源永遠湊不滿門檻，會一直假裝健康）",
      _sh.tally(_runs(404, 403, 404), _TH, _SRC1)["s1"]["consecutive_failures"], 2)
acase("健康分：成功會歸零連續失敗數（自癒要算得出來）",
      _sh.tally(_runs(404, 404, 200), _TH, _SRC1)["s1"]["consecutive_failures"], 0)
acase("健康分：設定檔裡已經不存在的來源不進健康表（移除過的來源留在歷史就好）",
      list(_sh.tally(_runs(200), _TH, {})), [])

_D_PROBING = {"s1": {"id": "s1", "lifecycle": "probing"}}
_D_DEGRADED = {"s1": {"id": "s1", "lifecycle": "degraded"}}
_D_DORMANT = {"s1": {"id": "s1", "lifecycle": "dormant"}}


def _decide(statuses, srcs, prior=None):
    h = _sh.tally(_runs(*statuses), _TH, srcs)
    return _sh.decide(h, srcs, prior or {}, _TH)


acase("降級：連續 2 班失敗 → probing 降 degraded（degraded 仍然會被抓，能自癒）",
      [(c[1], c[2]) for c in _decide([503, 503], _D_PROBING)[0]],
      [("probing", "degraded")])
acase("降級：只失敗 1 班不動（門檻是連續 2）",
      _decide([503], _D_PROBING)[0], [])
# 這條是整組測試裡最重要的一條。
acase("降級：連續失敗 10 班也**不會**自動寫 dormant，只列隔離候選"
      "（不抓的來源沒有自癒路徑，自動關掉就是把 07-24 的死法做成常設機制）",
      (_decide([503] * 10, _D_DEGRADED)[0],
       [q[0] for q in _decide([503] * 10, _D_DEGRADED)[1]]),
      ([], ["s1"]))
acase("降級：403 連續 10 班不降級（量不到不等於壞掉）",
      _decide([403] * 10, _D_PROBING)[0], [])
acase("降級：robots_disallow 連續 10 班不降級（那是 robots 重驗的職責範圍）",
      _decide(["robots_disallow"] * 10, _D_PROBING)[0], [])
acase("降級：dormant 不在自動降級範圍（根本沒有觀測）",
      _decide([503] * 10, _D_DORMANT)[0], [])

_PRIOR_MACHINE = {"s1": {"degraded_by": "health", "degraded_from": "probing"}}
acase("回復：機器自己降的級，連續 3 班成功後自己撤銷，且回到原本那個狀態"
      "（不是升到 active——機器不發信任）",
      [(c[1], c[2], c[3]) for c in _decide([200, 200, 200], _D_DEGRADED, _PRIOR_MACHINE)[0]],
      [("degraded", "probing", "health-recovered")])
acase("回復：連續 2 班成功還不夠（門檻是 3）",
      _decide([200, 200], _D_DEGRADED, _PRIOR_MACHINE)[0], [])
acase("回復：**人手**設的 degraded 機器不碰"
      "（沒有 degraded_by: health 記號＝那是判斷不是量測，不該被三班 200 推翻）",
      _decide([200] * 10, _D_DEGRADED, {})[0], [])

# 管線那一端：健康分的輸入本來不存在。stats 只餵給 markdown 報告，
# 所以 gate.yaml 的 source_health 躺了一整個月沒有消費者——不是評分邏輯沒寫，
# 是評分沒有輸入。下面四條釘住那條管線與它的欄位白名單。
import tempfile as _tf2  # noqa: E402
with _tf2.TemporaryDirectory() as _td:
    _v2 = Path(_td)
    _st2 = [{"id": "s1", "track": "official", "tier": 1, "status": 200,
             "items": 3, "error": None, "robots": True, "backfill": False, "new": 3}]
    _pp.write_run_stats(_v2, "2026-07-26", _st2)
    _pp.write_run_stats(_v2, "2026-07-26", _st2)
    _lines2 = (_v2 / "_probe" / "source-runs.jsonl").read_text("utf-8").strip().split("\n")
    acase("管線：每班 append 一行，不是覆寫（覆寫的話「連續第幾次」永遠算不出來）",
          len(_lines2), 2)
    acase("管線：一班一個物件（不是一條來源一行——一天 12 班攤平成每條一行，"
          "一年會長到十萬行以上）",
          sorted(_json.loads(_lines2[0])), ["at", "day", "sources"])
    acase("管線：只寫 allowlist 欄位，原始內容不進 vault（紅線 6）",
          sorted(_json.loads(_lines2[0])["sources"][0]),
          ["error", "id", "items", "status"])
    acase("管線：健康分吃得到 probe 剛寫下去的東西（兩端的欄位名對得上）",
          _sh.tally(_sh.load_runs(_v2), _TH, _SRC1)["s1"]["consecutive_successes"], 2)

# 這整個 PR 修的就是「寫好了但沒有人叫它」。如果健康分自己也沒被排進 workflow，
# 那只是把同一個病從 gate.yaml 搬到 scripts/ 而已。
_wf = open(os.path.join(_HERE, "..", ".github", "workflows", "data-refresh.yml"),
           encoding="utf-8").read()
acase("排程：data-refresh.yml 真的會跑 pulse-source-health.py"
      "（沒排進去的話這支腳本就是下一塊沒有消費者的東西）",
      "pulse-source-health.py" in _wf, True)

print("offline self-test\n" + "-" * 70)
fails = 0
for ok, name, detail, reason in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n         {detail} | {reason}")
    fails += 0 if ok else 1
print("-" * 70)
print(f"{len(results) - fails}/{len(results)} passed")
raise SystemExit(1 if fails else 0)
