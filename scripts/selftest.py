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

# --------------------------------------- 當日 sticky 欄位（backfill / is_new）
# 為什麼補這批：`DAY_STICKY_FIELDS` 是 07-25「同日第二班把 backfill 全部翻成
# false」那個修正的全部實作，而它上線時**一條測試都沒有**（本檔 grep backfill
# 為 0）。這種東西沒測試特別危險，因為它的失效是靜默的——檔案還在、筆數一樣、
# 沒有任何錯誤，只有報告開頭那句警語安靜消失。
#
# 更麻煩的是它**很難靠真語料自然驗到**。要踩到這條路徑，得剛好有一條「當天
# 首抓（所以整批 backfill=True）」的來源「在同一天的後續班次又產出新料（所以
# 檔案被整包重寫）」。2026-07-26 實測：第一班 backfill=0，第二班唯一的 backfill
# 是新來源 src-amd-ir 的 10 筆，而它是最後一班才出現的，沒有後續班次碰過它。
# 也就是說修正上線一整天，那條路徑一次都沒被執行。等資料自己長出測試案例，
# 可能等好幾天、也可能永遠等不到——所以要用測試把它釘死，不是靠觀察。
import pathlib as _pathlib   # noqa: E402
import tempfile as _tempfile  # noqa: E402

_sticky_prior = [
    {"url_canonical": "https://ex.org/a", "backfill": True,  "is_new": True},
    {"url_canonical": "https://ex.org/b", "backfill": True,  "is_new": False},
    {"url": "https://ex.org/c", "backfill": False, "is_new": True},   # 只有 url
]
_sticky_dir = _tempfile.mkdtemp()
_sticky_path = _pathlib.Path(_sticky_dir) / "src-x.jsonl"
_sticky_path.write_text(
    "\n".join(_json.dumps(r, ensure_ascii=False) for r in _sticky_prior) + "\n"
    # 空行 + 壞掉的 JSON：保護性讀取，一行壞資料不該擋掉整班抓取。
    + "\n{not json at all\n", encoding="utf-8")
_prior = _pp.load_day_flags(_sticky_path)

acase("load_day_flags：壞行與空行跳過，好的三筆都讀到",
      sorted(_prior), ["https://ex.org/a", "https://ex.org/b", "https://ex.org/c"])
acase("load_day_flags：url_canonical 缺席時退回 url 當 key",
      _prior.get("https://ex.org/c"), {"backfill": False, "is_new": True})
acase("load_day_flags：檔案不存在 → 空 dict（首班不該爆）",
      _pp.load_day_flags(_pathlib.Path(_sticky_dir) / "nope.jsonl"), {})

# 這一條就是 07-25 的事故本體：第二班算出來的 backfill/is_new 一律是 False
# （first_fetch_at 已有值、seen.json 已收錄），若直接寫回檔案，早上標好的存量
# 標記就被抹掉。carry_day_flags 必須讓**當天第一次**的判定勝出。
_row_a = {"url_canonical": "https://ex.org/a", "backfill": False, "is_new": False}
acase("carry_day_flags：同日第二班的 False 不得覆蓋首班的 True（07-25 事故本體）",
      _pp.carry_day_flags(_row_a, _prior),
      {"url_canonical": "https://ex.org/a", "backfill": True, "is_new": True})
# 反方向也要守：sticky 是「沿用首班判定」，不是「一律 True」。首班判 False 的
# 就該維持 False，否則會把當期新訊號整批誤標成存量，lead_days 與熱度被錯誤排除。
_row_b = {"url_canonical": "https://ex.org/b", "backfill": False, "is_new": False}
acase("carry_day_flags：首班判 False 的也沿用 False（不是一律 True）",
      _pp.carry_day_flags(_row_b, _prior),
      {"url_canonical": "https://ex.org/b", "backfill": True, "is_new": False})
# 當日沒看過的項目維持本輪判定——那才是它第一次被看到。第二班抓到的新文章
# 不能因為「第二班了」就被當成存量。
_row_new = {"url_canonical": "https://ex.org/zzz", "backfill": False, "is_new": True}
acase("carry_day_flags：當日沒看過的維持本輪判定（第二班的新料仍算新）",
      _pp.carry_day_flags(_row_new, _prior),
      {"url_canonical": "https://ex.org/zzz", "backfill": False, "is_new": True})
acase("carry_day_flags：prior 為空時原樣返回（首班路徑）",
      _pp.carry_day_flags({"url": "https://ex.org/q", "backfill": True}, {}),
      {"url": "https://ex.org/q", "backfill": True})
# 欄位清單本身要釘住。多加一個欄位進去，看起來只是「順手也沿用一下」，
# 實際上會讓那個欄位在同日第二班之後永遠停在首班的值——包含 author_kind
# 這種會被分類器修正改動的欄位。少一個則是直接退回事故狀態。
acase("DAY_STICKY_FIELDS 維持 (backfill, is_new)：多一個或少一個都會靜默改變語意",
      list(_pp.DAY_STICKY_FIELDS), ["backfill", "is_new"])

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

# 抓取端的**標籤**也要分岔，不是只有重驗端。2026-07-26 實測：src-kol-thezvi 的
# robots.txt 回 401/403，重驗端正確判成 unknown_keep、沒寫回設定檔，但 run_source
# 只取布林值，報告印出 `robots_disallow`——量測失敗被印成站方政策。
# 危害不抽象：人看報告會以為對方拒絕，再拿「連三天零產出」去降級一條其實只是
# 被 WAF 擋住的來源。抓不抓的行為不變，但說法不可以說錯。
_ROBOTS_SRC = {"id": "s-r", "adapter": "rss", "endpoint": "https://e.test/feed",
               "track": "kol", "tier": 2}
_pp.safe_fetch = lambda u: (403, None, {})
_st403 = _pp.run_source(dict(_ROBOTS_SRC), None, {}, {})[1]
acase("run_source：robots 403 → status 是 robots_unknown，不是 robots_disallow",
      _st403["status"], "robots_unknown")
acase("run_source：403 的抓取決策不變（robots 欄仍是 False ＝ 今晚不抓）",
      _st403["robots"], False)
acase("run_source：reason code 有帶進 stat，報告才有辦法說對",
      _st403["robots_reason"], "unavailable_403")
_pp.safe_fetch = lambda u: (200, "User-agent: *\nDisallow: /\n", {})
_stdis = _pp.run_source(dict(_ROBOTS_SRC), None, {}, {})[1]
acase("run_source：200 + 明文 Disallow → 這個才可以叫 robots_disallow",
      (_stdis["status"], _stdis["robots_reason"]), ("robots_disallow", "disallow"))

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
import shutil  # noqa: E402
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

# ------------------------------------------- gate.yaml 未接線標記（2026-07-26）
# gate.yaml 原本有 13 個 key 沒有任何程式碼讀它。未接線不是 bug（好幾個是預留
# 規格），沒標出來才是：一個寫著正常數字的假欄位，會讓下一個人把它改掉、重跑、
# 看到行為沒變，然後去懷疑資料壞了。對照表在 references/gate-config-status.md。
#
# 2026-07-26：`stale_after_days` 從這張清單畢業（pulse-monitor 的 --write-health
# / --alert-stale 接上了）。**當初寫這條測試就是為了逼出這一刻**——接線的那個
# commit 會看到這裡變紅，被迫回頭把 gate.yaml 的標記跟 references/ 一起改掉。
_UNWIRED = [
    "freshness_full_hours", "freshness_zero_days",
    "minhash_jaccard", "ngram", "event_window_hours",
    "key_eligibility", "version_derivation", "unknown_entity", "cross_language",
    "need_tier1_primary", "need_independent_tier2", "translation_chain",
]
_scripts_blob = "\n".join(
    open(p, encoding="utf-8").read()
    for p in sorted(_glob.glob(os.path.join(_HERE, "**", "*.py"), recursive=True))
    if os.path.basename(p) != "selftest.py")
acase("gate.yaml：標成「未接線」的 key 必須真的沒有消費者"
      "（哪天有人去接線了，這條會紅，提醒他回來把標記跟 references/ 一起改掉）",
      [k for k in _UNWIRED if k in _scripts_blob], [])

_gate_txt = open(os.path.join(_HERE, "..", "_config", "gate.yaml"), encoding="utf-8").read()
_gate_lines = _gate_txt.splitlines()


def _marked(key):
    """key 那一行本身、或它上面連續的註解區塊裡，要看得到「⚠ …未接線」。

    接受「⚠ 未接線」與「⚠ 整塊未接線」兩種寫法：整塊標一次比每個 key 重複標
    好讀，但兩者都必須帶著那個 ⚠，不能只在散文裡順口提到未接線。
    """
    for i, ln in enumerate(_gate_lines):
        if not ln.lstrip().startswith(key):
            continue
        if "⚠" in ln and "未接線" in ln:
            return True
        j = i - 1
        while j >= 0 and _gate_lines[j].lstrip().startswith("#"):
            if "⚠" in _gate_lines[j] and "未接線" in _gate_lines[j]:
                return True
            j -= 1
    return False


acase("gate.yaml：每個未接線的 key 旁邊都要留著「⚠ …未接線」標記"
      "（標記被刪掉＝那個假欄位又變回看起來很正常的樣子）",
      [k for k in _UNWIRED if not _marked(k)], [])
acase("gate.yaml：heat 那三個標的是「接線了但走不到」而不是「未接線」"
      "（它們確實被 pulse-gate.py 讀到，病因不同，修法也不同——"
      "把 70 調小是紅線 4 禁止的那種修法）",
      "接線了但走不到" in _gate_txt and "heat 上限 48" in _gate_txt, True)
acase("references/gate-config-status.md 存在（gate.yaml 的標記指向它）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "gate-config-status.md")),
      True)
# 反方向：畢業的 key 不准悄悄退回未接線。把 --write-health 那段刪掉、
# 或把讀 gate.yaml 那兩行拿掉，都會在這裡紅。
_mon_txt = open(os.path.join(_HERE, "pulse-monitor.py"), encoding="utf-8").read()
acase("gate.yaml：monitor.stale_after_days 真的被 pulse-monitor.py 讀進去"
      "（畢業的 key 不准悄悄退回未接線）",
      "stale_after_days" in _mon_txt and 'gate.get("monitor")' in _mon_txt, True)
acase("gate.yaml：monitor.stale_after_days 旁邊不該再留「未接線」標記"
      "（標記留著＝文件說謊的另一個方向）",
      _marked("stale_after_days"), False)

# ------------------------------------------- 機器產生的 vault 頁（2026-07-26）
# Sources/*.md 被每一則 Event 連著，卻沒有任何腳本產生它 —— 全部是紅色斷鏈。
# _dashboards/health.md 被部署規格講了一整個月，檔案從來沒存在過。
# 規格：references/vault-pages.md。
import re as _re  # noqa: E402

from lib import corpus as _corpuslib  # noqa: E402

_sns = importlib.util.spec_from_file_location(
    "pulse_source_notes", os.path.join(_HERE, "pulse-source-notes.py"))
_sn = importlib.util.module_from_spec(_sns)
_sns.loader.exec_module(_sn)

# 紅線 6：vault 只放 allowlist frontmatter。這條把「哪天有人為了 debug 方便，
# 把整個 sources.yaml 條目倒進 frontmatter」擋在門外。
acase("來源頁：frontmatter 白名單裡沒有非公開欄位（紅線 6）",
      [k for k in _sn.FM_FROM_CONFIG
       if any(bad in k for bad in ("token", "key", "secret", "header",
                                   "auth", "path", "cookie"))], [])

with tempfile.TemporaryDirectory() as _d3:
    _v3 = Path(_d3)
    (_v3 / "Events").mkdir(parents=True)
    # 同一則事件引同一條來源三次 —— 對「這條來源有沒有促成一則事件」來說是一次。
    (_v3 / "Events" / "e1.md").write_text(
        "---\nid: e1\nstatus: published\nevidence:\n"
        "  - source_id: s1\n  - source_id: s1\n  - source_id: s1\n---\n\n內文\n",
        encoding="utf-8")
    (_v3 / "Events" / "e2.md").write_text(
        "---\nid: e2\nstatus: review\nevidence:\n  - source_id: s1\n---\n\n內文\n",
        encoding="utf-8")
    _ev, _pub = _sn.bound(_v3)
    acase("來源頁：有效產出數的是**事件數**不是證據筆數"
          "（一則事件引同一條來源三次仍然只算一則）", [_ev["s1"], _pub["s1"]], [2, 1])

    # _corpus/ 的盤點單一真相源：兩天各一條，累計 3 筆，最後一天取較晚的那天。
    for _day, _n in (("2026-07-01", 1), ("2026-07-02", 2)):
        (_v3 / "_corpus" / _day).mkdir(parents=True)
        (_v3 / "_corpus" / _day / "s1.jsonl").write_text(
            "".join('{"a":1}\n' for _ in range(_n)), encoding="utf-8")
    _cnt, _last = _corpuslib.observed(_v3)
    acase("來源頁：已觀測是跨日累計，最後一天取最晚的那天",
          [_cnt["s1"], _last["s1"]], [3, "2026-07-02"])

    # 兩條時間軸：跑了班但沒抓到東西的那天，只會出現在 _probe/ 不會出現在 _corpus/。
    # report.md 是「這班真的跑完了」的判準（見 references/health-alarms.md）——
    # 光有目錄不算，目錄是開跑前就建好的。
    for _day in ("2026-07-01", "2026-07-02", "2026-07-03"):
        (_v3 / "_probe" / _day).mkdir(parents=True)
        (_v3 / "_probe" / _day / "report.md").write_text("# x\n", encoding="utf-8")
    acase("健康頁：跑班日曆與語料日曆分開數"
          "（07-03 有跑班但零產出——只看 _corpus/ 會把它誤判成鏈死了）",
          [_corpuslib.run_days(_v3)[-1], _corpuslib.corpus_days(_v3)[-1]],
          ["2026-07-03", "2026-07-02"])

    _r3 = {"date": "2026-07-03", "coverage": {"runnable_sources": 1, "sources": [],
                                              "must_watch": [], "window_days": 30,
                                              "history_days": 2},
           "review_total": 1, "published_total": 1, "dropped_total": 0,
           "review_actionable": 1, "review_terminal": 0, "review_unenriched": 0,
           "oldest_unenriched_days": 0, "oldest_stuck_days": 0, "blocker_hist": {}}
    _today3 = _date(2026, 7, 3)
    _h_green = _mm.health(_v3, _today3, _r3, 2)
    _h_red = _mm.health(_v3, _today3, _r3, 1)
    acase("健康頁：紅燈綁在「幾天沒抓到東西」，不是「幾天沒跑班」"
          "（07-03 有跑班、語料停在 07-02：門檻 2 天還是綠，門檻 1 天就紅）",
          [_h_green["status"], _h_red["status"], _h_green["run_lag_days"]],
          ["green", "red", 0])
    acase("健康頁：last_success 就是部署規格裡講的那個欄位（_corpus/ 的最後一天）",
          _h_green["last_success"], "2026-07-02")

    _md = _mm.render_health(_r3, _h_green)
    acase("健康頁：頁面自己不寫比「日」更細的時間"
          "（一天 12 班，帶時分秒＝每兩小時一次沒有資訊量的假 diff）",
          bool(_re.search(r"\d{2}:\d{2}", _md)), False)
    acase("健康頁：門檻值印在頁面上，讀的人不必回去翻 gate.yaml",
          "stale_after_days: 2" in _md, True)

# ───────────── 警報自己把自己關掉（2026-07-26 code review）─────────────
# 規格：references/health-alarms.md。這一組全部是「代理指標比事實寬鬆」的形態：
# 目錄名代理「那天有語料」。三種情況真相都是「6 天沒抓到任何東西」，修之前全是綠燈，
# 其中未來日期那個還**永遠**是綠的（lag 越來越負，`>= 門檻` 永遠為假），不會自癒。
with tempfile.TemporaryDirectory() as _d4:
    _T4 = _date(2026, 7, 26)
    _R4 = {"date": "2026-07-26"}

    def _v4(days, _root=_d4):
        v = Path(_root) / f"v{len(list(Path(_root).iterdir()))}"
        (v / "_probe" / "2026-07-20").mkdir(parents=True)
        (v / "_probe" / "2026-07-20" / "report.md").write_text("# x\n", "utf-8")
        for _name, _body in days.items():
            (v / "_corpus" / _name).mkdir(parents=True)
            if _body is not None:
                (v / "_corpus" / _name / "src-a.jsonl").write_text(_body, "utf-8")
        return v

    _GOOD = '{"a":1}\n'
    _h_empty = _mm.health(_v4({"2026-07-20": _GOOD, "2026-07-26": None}), _T4, _R4, 2)
    acase("死人開關：空的 _corpus/<今天>/ 不算「今天有語料」"
          "（目錄是開跑前就建的，建了目錄卻沒寫進東西＝那天什麼都沒抓到）",
          [_h_empty["last_success"], _h_empty["probe_lag_days"], _h_empty["status"]],
          ["2026-07-20", 6, "red"])
    _h_blank = _mm.health(_v4({"2026-07-20": _GOOD, "2026-07-26": "\n  \n"}), _T4, _R4, 2)
    acase("死人開關：只有空白行的 jsonl 不算語料（跟 observed() 用同一把尺）",
          [_h_blank["last_success"], _h_blank["status"]], ["2026-07-20", "red"])
    _h_fake = _mm.health(_v4({"2026-07-20": _GOOD, "2026-13-99": _GOOD}), _T4, _R4, 2)
    acase("死人開關：`2026-13-99` 不是日期，不能當成語料日曆的最後一天"
          "（舊判準只看長度 10＋第 5 字是 `-`，假日期會被印到健康頁上）",
          [_h_fake["last_success"], _h_fake["status"]], ["2026-07-20", "red"])
    _h_fut = _mm.health(_v4({"2026-07-20": _GOOD, "2026-07-30": _GOOD}), _T4, _R4, 2)
    acase("死人開關：未來日期的語料目錄判紅、而且跟「太久沒抓到」分開報"
          "（`-4 >= 2` 為假＝綠燈，時間往前走只會更綠，這個洞不會自癒）",
          [_h_fut["probe_lag_days"], _h_fut["status"], _h_fut["clock_skew"]],
          [-4, "red", True])
    acase("死人開關：正常的 lag 不會被誤判成時鐘壞掉",
          _h_empty["clock_skew"], False)

    _v_norep = Path(_d4) / "norep"
    (_v_norep / "_probe" / "2026-07-26").mkdir(parents=True)
    (_v_norep / "_corpus").mkdir(parents=True)
    acase("死人開關：沒寫出 report.md 的 _probe/<day>/ 不算跑過班"
          "（判準是報告寫出來了，不是目錄建起來了）",
          _corpuslib.run_days(_v_norep), [])

# 時區：兩個不同時區的日期相減可以差一天，而一天在 stale_after_days: 2 上
# 就是叫與不叫的差別。today 一律是 UTC，所以 _as_date 也必須歸零到 UTC。
acase("時區：帶偏移量的時間先歸零到 UTC 再取日期"
      "（+08:00 的 02:00 其實是前一天的 UTC；不歸零＝新鮮度差一天）",
      [_mm._as_date("2026-07-22T02:00:00+08:00").isoformat(),
       _mm._as_date("2026-07-21T20:00:00-08:00").isoformat()],
      ["2026-07-21", "2026-07-22"])
acase("時區：沒有偏移量的值維持既有語意（視為 UTC，不做任何位移）",
      [_mm._as_date("2026-07-22").isoformat(),
       _mm._as_date("2026-07-22T02:00:00Z").isoformat(),
       _mm._as_date("2026-07-22T02:00:00").isoformat()],
      ["2026-07-22", "2026-07-22", "2026-07-22"])
acase("references/health-alarms.md 存在（這一層的規格書，紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "health-alarms.md")), True)

# 兩支都必須真的被排進 workflow，否則只是把「寫好了但沒人叫它」搬個地方。
acase("排程：data-refresh.yml 真的會跑 pulse-source-notes.py 與 --write-health",
      ["pulse-source-notes.py" in _wf, "--write-health" in _wf], [True, True])
# 順序有兩個硬條件：在 Source health 之後（才讀得到這一班的分數）、
# 在 commit 之前（不然寫出來的檔案下一次 checkout 就被洗掉）。
acase("排程：vault 頁排在 Source health 之後、Commit 之前"
      "（排在 commit 之後＝每班寫完就被洗掉，等於整天沒產出）",
      _wf.index("Source health (0 LLM)") < _wf.index("Vault pages (0 LLM)")
      < _wf.index("Commit & push data changes"), True)
acase("references/vault-pages.md 存在（這兩頁的規格書，紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "vault-pages.md")), True)

# ─────────── 佇列年紀只能看 ingested_at（2026-07-26 誤報事故的回歸測試）───────────
# 那天 CI 每兩小時紅一次，訊息是「有事件未 enrich 已放 4 天」。三則事件全是當天
# 早上 06:41 才進 vault 的——夜間潤稿鏈前一晚根本碰不到它們。原因是年紀算的是
# happened_at（新聞發布日）。也就是說**每新增一條會補歷史的來源，CI 就立刻紅，
# 而且沒有自癒路徑**。事故與欄位規格見 references/event-timestamps.md。
_EVT_FM = ("---\nid: {i}\ntitle: t\ndate: '{d}'\nhappened_at: '{h}T00:00:00+00:00'\n"
           "{ing}status: review\nblockers: []\ntags: [event]\n---\n\n## 事實\n{body}\n")


def _qvault(events):
    d = tempfile.mkdtemp()
    v = Path(d)
    (v / "Events").mkdir()
    (v / "_corpus" / "2026-07-26").mkdir(parents=True)
    (v / "_corpus" / "2026-07-26" / "src-x.jsonl").write_text('{"a":1}\n', "utf-8")
    for i, (hap, ing, body) in enumerate(events):
        ingline = f"ingested_at: '{ing}T00:00:00+00:00'\n" if ing else ""
        (v / "Events" / f"evt-{i}.md").write_text(
            _EVT_FM.format(i=f"evt-{i}", d=hap, h=hap, ing=ingline, body=body), "utf-8")
    return v


_OLD_NEWS = ("2026-07-22", "2026-07-26", "待編輯：一句話")   # 4 天前的新聞，今天才進庫
_REAL_LAG = ("2026-07-26", "2026-07-22", "待編輯：一句話")   # 今天的新聞，庫裡放了 4 天
_TODAY26 = _date(2026, 7, 26)

_r_old = _mm.scan(_qvault([_OLD_NEWS]), _TODAY26)
acase("佇列年紀：4 天前的舊聞今天才進庫 → 0 天"
      "（新增一條補歷史的來源不該讓死人開關立刻叫）",
      _r_old["oldest_unenriched_days"], 0)

_r_lag = _mm.scan(_qvault([_REAL_LAG]), _TODAY26)
acase("佇列年紀：今天的新聞在庫裡放了 4 天沒潤 → 4 天（該叫的還是要叫）",
      _r_lag["oldest_unenriched_days"], 4)

acase("佇列年紀：卡在 review 的天數也吃 ingested_at，不是 happened_at",
      [_r_old["oldest_stuck_days"], _r_lag["oldest_stuck_days"]], [0, 4])

# 缺值＝量不到。紅線 8：不拿 happened_at 頂替（那正是要修掉的東西），
# 但要有數字，否則「回填漏了一半」跟「真的沒有卡件」在報告上長得一模一樣。
_r_none = _mm.scan(_qvault([("2026-07-01", None, "待編輯：一句話")]), _TODAY26)
acase("佇列年紀：沒有 ingested_at 的 Event 不拿 happened_at 頂替，年紀留 0，但要被數出來",
      [_r_none["oldest_unenriched_days"], _r_none["undated_review"]], [0, 1])
# ……而「年紀留 0」不可以連帶把警報也關掉。全部未潤稿的都缺 ingested_at 時，
# oldest_unenriched_days 的 max() 沒東西可算會回退成 0，0 低於任何門檻＝安靜。
# 這一格就是 2026-07-26 review 抓到的「警報自己把自己關掉」，見 health-alarms.md。
import inspect as _inspect  # noqa: E402
acase("死人開關：未潤稿又量不到年紀的 Event 自己就是一則警報"
      "（不是「放了 0 天」——量不到不等於沒事，紅線 8）",
      _r_none["unenriched_undated"], 1)
acase("死人開關：量得到年紀的未潤稿 Event 不會被重複算進「量不到」那一格",
      [_r_lag["unenriched_undated"], _r_lag["oldest_unenriched_days"]], [0, 4])
acase("死人開關：--alert-unenriched-days 的觸發條件同時吃兩個數字"
      "（只看 oldest_unenriched_days 的話，缺 ingested_at 就等於靜音）",
      [_s in _inspect.getsource(_mm.main) for _s in
       ('r["oldest_unenriched_days"] >= args.alert_unenriched_days',
        'r.get("unenriched_undated")')],
      [True, True])

acase("pulse-monitor.scan() 不再從 happened_at / date 算佇列年紀"
      "（改回去的話上面兩條會紅，這條是講清楚改哪裡）",
      [_s in _inspect.getsource(_mm.scan) for _s in
       ('_as_date(fm.get("happened_at"))', '_as_date(fm.get("ingested_at"))')],
      [False, True])

# ingested_at 必須黏住：event_markdown() 會整份重寫 frontmatter，沒被明確帶過去的
# 欄位會被抹掉——fix/backfill-flag-erased-by-second-run 修的就是這個坑。
_cs = importlib.util.spec_from_file_location(
    "pulse_cluster", os.path.join(_HERE, "pulse-cluster.py"))
_cm = importlib.util.module_from_spec(_cs)
_cs.loader.exec_module(_cm)

_e = _cm.Event("evt-x", "x", "T", "2026-07-22T00:00:00+00:00")
_e.ingested_at = "2026-07-26T06:41:46+00:00"
_e.scores = {"tier_evidence": 1, "independent_sources": 1, "primary_evidence": 1,
             "confidence": 70, "heat": 10, "impact": 50, "value": 40, "factors": {}}
_out = _cm.event_markdown(_e)
acase("pulse-cluster：新 Event 的 frontmatter 有 ingested_at，且與 happened_at 不同值",
      ["ingested_at: '2026-07-26T06:41:46+00:00'" in _out,
       "happened_at: '2026-07-22T00:00:00+00:00'" in _out], [True, True])

_e2 = _cm.Event("evt-x", "x", "T", "2026-07-22T00:00:00+00:00")
_e2.ingested_at = None
acase("pulse-cluster：ingested_at 沒帶值時寫成空，不會偷偷填成今天",
      "ingested_at: null" in _cm.event_markdown(
          type("E", (), {**{k: getattr(_e, k) for k in
                           ("id", "slug", "title", "happened_at", "fingerprint",
                            "facet", "company", "keywords", "evidence", "scores")},
                         "ingested_at": None})()), True)

# M6：只釘寫檔那一端不夠。**建立時忘了塞值**是最惡劣的失敗——每則新 Event 都會
# 生成 ingested_at: null，警報從此永遠閉嘴，而且看起來一切正常（一個被靜靜關掉的
# 死人開關比沒有開關更糟）。所以這條走真的 main()，不看原始碼字串。
_cvault = Path(tempfile.mkdtemp())
(_cvault / "Events").mkdir()
(_cvault / "_probe" / "2026-07-26").mkdir(parents=True)
shutil.copytree(os.path.join(_HERE, "..", "_config"), _cvault / "_config")
(_cvault / "_probe" / "2026-07-26" / "signals-scored.jsonl").write_text(_json.dumps({
    "source_id": "src-openai-blog", "effective_role": "primary",
    "title": "OpenAI announces a thing that does not exist",
    "url": "https://example.invalid/a", "published": "2026-07-22T00:00:00+00:00",
    # 這則的重點就在這兩個時間差 4 天：新聞是 07-22 發的，我們 07-26 才看到。
    "first_observed_at": "2026-07-26T06:41:46+00:00", "total": 90,
    "entity_hits": ["openai"], "facet": "product", "fingerprint": "openai|thing",
}) + "\n", "utf-8")
_argv, _env = sys.argv[:], os.environ.get("VAULT_DIR")
sys.argv = ["pulse-cluster.py"]
os.environ["VAULT_DIR"] = str(_cvault)
try:
    _cm.main()
finally:
    sys.argv = _argv
    if _env is not None:
        os.environ["VAULT_DIR"] = _env
_made = sorted((_cvault / "Events").glob("*.md"))
_txt = _made[0].read_text("utf-8") if _made else ""
acase("pulse-cluster 跑完一輪：新建的 Event 真的帶著 probe 第一次看到的時刻"
      "（忘了塞值＝每則新 Event 都是 null＝死人開關被靜靜關掉）",
      [len(_made), "ingested_at: '2026-07-26T06:41:46+00:00'" in _txt,
       "happened_at: '2026-07-22T00:00:00+00:00'" in _txt], [1, True, True])

acase("pulse-cluster：reload 既有 note 時把 ingested_at 讀回物件"
      "（不讀回去的話，下一次 rescore 整份重寫就抹掉了）",
      'ev.ingested_at = fm.get("ingested_at")' in open(
          os.path.join(_HERE, "pulse-cluster.py"), encoding="utf-8").read(), True)

acase("references/event-timestamps.md 存在（紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "event-timestamps.md")), True)

print("offline self-test\n" + "-" * 70)
fails = 0
for ok, name, detail, reason in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n         {detail} | {reason}")
    fails += 0 if ok else 1
print("-" * 70)
print(f"{len(results) - fails}/{len(results)} passed")
raise SystemExit(1 if fails else 0)
