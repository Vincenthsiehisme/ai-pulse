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

# ── 零產出診斷：一條「200 / 0 筆」有四種成因，報告上以前只有一種形狀 ──
# 規格見 references/health-alarms.md〈零產出不是沉默〉。
# 這幾條全部不碰網路：判斷只讀 adapter 留下的計數，這正是設計成 diag 的理由。

_d_ok: dict = {}
_pp.adapt_sitemap({"url_prefix": "/news/", "quota_per_run": 10}, SITEMAP, _d_ok)
acase("零產出診斷：正常那班也要留中途數字（過濾前 3、過濾後 2）"
      "——只在出事那天才記錄的東西，出事那天才發現它沒在記錄",
      (_d_ok["kind"], _d_ok["urls_before_filter"], _d_ok["urls_after_filter"]),
      ("urlset", 3, 2))

_d_hint: dict = {}
_pp.adapt_sitemap({"url_prefix": "/news/"}, _IDX, _d_hint)
acase("零產出診斷：hints 一張都沒命中 → 是我們的設定對不上，不是站上沒東西",
      _pp.zero_yield_reason(_d_hint)[0], "hints_matched_nothing")
acase("零產出診斷：hints 沒命中時要記下 index 有幾張可選"
      "（沒有這個數字，人分不出「站上沒子 sitemap」跟「我們挑錯」）",
      (_d_hint["index_entries"], _d_hint["hint_matched"]), (1, 0))

_SM_NO_NEWS = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               '<url><loc>https://x.test/careers/a</loc></url>'
               '<url><loc>https://x.test/about/b</loc></url></urlset>')
_d_prefix: dict = {}
acase("零產出診斷：prefix 濾掉全部 → 回空清單（行為不變）",
      _pp.adapt_sitemap({"url_prefix": "/news/"}, _SM_NO_NEWS, _d_prefix), [])
acase("零產出診斷：抓到 URL 但 prefix 一條都不放行 → prefix_filtered_all"
      "（跟「站上沒東西」是相反的修法：一個改設定，一個什麼都不用做）",
      _pp.zero_yield_reason(_d_prefix)[0], "prefix_filtered_all")
acase("零產出診斷：prefix 濾光時要留過濾前的樣本 URL"
      "（過濾後的樣本回答不了「為什麼被濾掉」）",
      _d_prefix["sample_before_filter"],
      ["https://x.test/careers/a", "https://x.test/about/b"])

_d_empty: dict = {}
_pp.adapt_sitemap({"url_prefix": "/news/"},
                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>',
                  _d_empty)
acase("零產出診斷：入口通、裡面沒有 URL → source_empty（這一種才是站方那邊）",
      _pp.zero_yield_reason(_d_empty)[0], "source_empty")

acase("零產出診斷：沒有 diag 的 adapter 誠實回 no_diagnosis，不假裝判得出來（紅線 8）",
      _pp.zero_yield_reason({})[0], "no_diagnosis")

# 自己抓的 adapter：run_source 沒有送出請求，status 只能由 adapter 回報。
# 寫死 200 等於用「adapter 沒丟例外」代理「這一班真的成功」——GitHub API
# 額度用完的那天，報告會說 200 / 0 筆，跟「沒有新 release」印起來一樣。
_gh_diag: dict = {}
_gh_src = {"endpoint": "o/r", "adapter": "github-releases"}
_gh_saved = _pp.safe_fetch
try:
    _pp.safe_fetch = lambda *a, **k: (403, None, {})
    _pp.adapt_github_releases(_gh_src, "", _gh_diag)
finally:
    _pp.safe_fetch = _gh_saved
acase("自己抓的 adapter：把真實 status 回報給 run_source（不是讓它寫死 200）",
      _gh_diag.get("self_fetch_status"), 403)

# 上面那條只釘到 adapter 回報了；真正會騙人的是 run_source 讀不讀它。
# 走真的 run_source：SELF_FETCH 那條路不做 robots 檢查，所以只要換掉 safe_fetch。
_gh_saved2 = _pp.safe_fetch
try:
    _pp.safe_fetch = lambda *a, **k: (403, None, {})
    _gh_items, _gh_stat = _pp.run_source(
        {"id": "s-gh", "adapter": "github-releases", "endpoint": "o/r"},
        [], {}, {})
finally:
    _pp.safe_fetch = _gh_saved2
acase("自己抓的 adapter：run_source 的 status 跟著 adapter 走，不寫死 200"
      "（寫死 200 ＝ 用「adapter 沒丟例外」代理「這一班真的成功」，"
      "而那一班的報告會說 200 / 0 筆，跟「站上沒有新 release」印起來一樣）",
      [_gh_stat["status"], _gh_stat["items"], bool(_gh_stat["error"])],
      [403, 0, True])
_gh_saved3 = _pp.safe_fetch
try:
    _pp.safe_fetch = lambda *a, **k: (200, "[]", {})
    _pp.run_source({"id": "s-gh", "adapter": "github-releases",
                    "endpoint": "o/r"}, [], {}, {})
    _gh_ok = _pp.run_source({"id": "s-gh2", "adapter": "github-releases",
                             "endpoint": "o/r"}, [], {}, {})[1]
finally:
    _pp.safe_fetch = _gh_saved3
acase("自己抓的 adapter：真的成功那一班照樣是 200（反方向，確認上一條不是恆非 200）",
      [_gh_ok["status"], _gh_ok["error"]], [200, None])
acase("零產出診斷：github-releases 回 200 且有 body 但沒有 release → 站方那邊",
      _pp.zero_yield_reason({"adapter": "github-releases",
                             "self_fetch_status": 200,
                             "self_fetch_empty_body": False})[0], "source_empty")
acase("零產出診斷：github-releases 回 200 但 body 是空的 → 不是「沒有 release」",
      _pp.zero_yield_reason({"adapter": "github-releases",
                             "self_fetch_status": 200,
                             "self_fetch_empty_body": True})[0],
      "upstream_empty_body")
acase("零產出診斷：`upstream_empty_body` 不可以被歸到「我們」那一邊"
      "（回應本身不對，這端分不出是誰的問題——分不出就不要猜）",
      [l.split("|")[3].strip() for l in
       "\n".join(_pp.zero_yield_section(
           [{"id": "s-gh", "track": "official", "status": 200, "items": 0,
             "diag": {"adapter": "github-releases", "self_fetch_status": 200,
                      "self_fetch_empty_body": True}}])).split("\n")
       if l.startswith("| s-")], ["還不知道"])
acase("零產出診斷：diag 是 None 也走同一條路，不得爆炸",
      _pp.zero_yield_reason(None)[0], "no_diagnosis")

# adapter 的呼叫約定：run_source 一律傳三個位置參數。少收一個的 adapter 會在
# 那一班整條炸掉，而炸掉的訊息會指向 run_source，不指向漏改的那支。
acase("零產出診斷：每個 adapter 都收得下第三個參數（diag）",
      sorted(n for n, f in _pp.ADAPTERS.items()
             if f.__code__.co_argcount >= 3),
      ["atom", "github-releases", "json-api", "rss", "sitemap"])

# ── 渲染層：分得出來還要印得出來 ──
_ZSTATS = [
    {"id": "s-empty", "track": "official", "status": 200, "items": 0,
     "diag": dict(_d_empty)},
    {"id": "s-prefix", "track": "official", "status": 200, "items": 0,
     "diag": dict(_d_prefix)},
    {"id": "s-304", "track": "official", "status": 304, "items": 0, "diag": {}},
    {"id": "s-blocked", "track": "media", "status": "robots_disallow",
     "items": 0, "diag": {}},
    {"id": "s-fine", "track": "kol", "status": 200, "items": 7, "diag": {}},
]
_zsec = "\n".join(_pp.zero_yield_section(_ZSTATS))
acase("零產出診斷：只收 200 且 0 筆——304 是「內容沒變」，"
      "robots_disallow 根本沒抓，混進來會讓「零產出」同時指兩件事",
      [s in _zsec for s in ("s-empty", "s-prefix", "s-304", "s-blocked", "s-fine")],
      [True, True, False, False, False])
acase("零產出診斷：兩種成因在報告上要標成不同的「是誰那邊」"
      "（同一句話印給兩種成因，等於沒有印）",
      [l.split("|")[3].strip() for l in _zsec.split("\n")
       if l.startswith("| s-")], ["站方", "我們"])
acase("零產出診斷：這一區空的時候要印「本輪沒有」，不是整段不印"
      "（看不見的區塊有兩種意思：沒有零產出，或這段壞了）",
      "本輪沒有" in "\n".join(_pp.zero_yield_section(
          [{"id": "s", "status": 200, "items": 5, "diag": {}}])), True)

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
_REAL_SAFE_FETCH = _pp.safe_fetch   # 下面整段會 monkeypatch，測 safe_fetch 本人時要換回來
_rcases = [
    ("robots 403 → 抓取端仍拒絕，但原因是 unavailable_403（非政策）",
     403, None, (False, "unavailable_403")),
    ("robots 200 + Disallow: / → disallow，這才是站方政策",
     200, "User-agent: *\nDisallow: /\n", (False, "disallow")),
    ("robots 200 + 放行 → ok", 200, PERMISSIVE, (True, "ok")),
    ("robots 404 → no_robots，依慣例放行", 404, None, (True, "no_robots")),
    ("robots 503 → unreachable，不得變成放行", 503, None, (None, "unreachable")),
    # 429 是 4xx，但它說的是「你太快」，不是「這站沒有 robots.txt」。
    # 掉進 no_robots 等於把自己的節流讀成對方的放行。
    ("robots 429 → unreachable，不得掉進 no_robots", 429, None, (None, "unreachable")),
    # 200 不等於拿到 robots.txt。以下三種都是實際會遇到的 200-非-robots，
    # RobotFileParser 對它們一律解析出空規則 → can_fetch 恆 True。
    # 方向比 07-24 那個舊 bug 更壞：那個把放行寫成禁止，這個把禁止寫成放行。
    ("robots 200 但回 WAF 挑戰頁 → not_robots，不得讀成全站放行",
     200, "<!DOCTYPE html><html><body>Checking your browser…</body></html>",
     (None, "not_robots")),
    ("robots 200 但回 SSO 導頁 → not_robots",
     200, "<html><head><meta http-equiv=refresh content=0;url=/login></head></html>",
     (None, "not_robots")),
    ("robots 200 但回軟 404 文字頁 → not_robots",
     200, "Sorry, the page you requested could not be found.", (None, "not_robots")),
    # 反向：真的空 robots.txt 是 RFC 9309 明文的全站放行，不可以被這個防護誤殺。
    ("robots 200 空檔案 → 仍是 ok（RFC 9309 放行）", 200, "", (True, "ok")),
    ("robots 200 只有註解 → 仍是 ok", 200, "# nothing here\n\n# really\n",
     (True, "ok")),
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

# not_robots 走的必須是 unknown_keep 那條，不是 opened。
# 若不擋：arXiv 的 robots.txt 明文 `Disallow: /`，現在是 dormant；只要它哪天在
# --revive 那一班回一次 200 + 挑戰頁，就會被寫成 robots_ok: true 並升回 probing。
_rr._probe.safe_fetch = lambda u: (200, "<html><body>Access denied</body></html>", {})
_DOC2 = {"official_sources": [{"id": "s2", "lifecycle": "dormant",
                               "robots_ok": False, "endpoint": "https://e.test/f"}]}
acase("重驗：200 但不是 robots.txt → unknown_keep，不得判成 opened",
      _rr.check(_DOC2)[0]["verdict"], "unknown_keep")
acase("重驗：not_robots 不產生任何 robots_ok 異動",
      _rr.apply_changes(_DOC2, _rr.check(_DOC2)), [])
acase("重驗：not_robots 不得留下 robots_ok 被改掉的痕跡",
      _DOC2["official_sources"][0]["robots_ok"], False)

# robots_checked_at 的語意是「最後一次**驗到**」。量不到卻蓋時戳，是把失敗
# 記成一次成功的驗證（紅線 8），而且 --stale-days 回到 7 之後，這個時戳會讓
# check() 判 skip_fresh——一次 WAF 擋包換來七天連試都不試。
_DOC3 = {"official_sources": [{"id": "s3", "lifecycle": "probing",
                               "robots_ok": True, "endpoint": "https://e.test/f"}]}
_rr._probe.safe_fetch = lambda u: (403, None, {})
_rr.apply_changes(_DOC3, _rr.check(_DOC3))
acase("重驗：量不到（unknown_keep）不得蓋 robots_checked_at",
      "robots_checked_at" in _DOC3["official_sources"][0], False)
_rr._probe.safe_fetch = lambda u: (200, "User-agent: *\nDisallow: /\n", {})
_rr.apply_changes(_DOC3, _rr.check(_DOC3))
acase("重驗：真的驗到了才蓋 robots_checked_at",
      bool(_DOC3["official_sources"][0].get("robots_checked_at")), True)

# 入場券要跟著結論一起動。設定檔的全域不變式是「robots_ok: false 必須附
# robots_evidence: 200+disallow，而且這一欄只能出現在 false 上」——那兩條斷言
# 之前只釘住人手寫的設定檔，機器寫回去的那條路沒釘。
# 2026-07-26 首班 CI 就從那個缺口漏出去：recheck 把 src-media-theregister 寫成
# false 卻沒附券，兩條全域斷言當場紅，但 CI 不跑 selftest，那一班仍是綠的。
# closed 的唯一入口是 reason == "disallow"，所以這張券寫的是已經量到的事實。
_DOC4 = {"official_sources": [{"id": "s4", "lifecycle": "probing",
                               "robots_ok": True, "endpoint": "https://e.test/f"}]}
_rr._probe.safe_fetch = lambda u: (200, "User-agent: *\nDisallow: /\n", {})
_rr.apply_changes(_DOC4, _rr.check(_DOC4))
acase("重驗：機器寫 robots_ok: false 時必須同時交出 robots_evidence 入場券",
      (_DOC4["official_sources"][0]["robots_ok"],
       _DOC4["official_sources"][0].get("robots_evidence")),
      (False, "200+disallow"))
_rr._probe.safe_fetch = lambda u: (200, "User-agent: *\nAllow: /\n", {})
_rr.apply_changes(_DOC4, _rr.check(_DOC4))
acase("重驗：改判 true 時要撕掉舊入場券（不得拿舊證據替新結論背書）",
      (_DOC4["official_sources"][0]["robots_ok"],
       "robots_evidence" in _DOC4["official_sources"][0]),
      (True, False))

# _looks_like_robots：content-type 是 html 就直接否決，即使 body 湊得出指令字樣。
acase("robots：content-type html → 不當 robots.txt 看",
      _pp._looks_like_robots("User-agent: *\nDisallow: /admin\n",
                             {"Content-Type": "text/html; charset=utf-8"}), False)
acase("robots：content-type text/plain + 指令 → 是 robots.txt",
      _pp._looks_like_robots("User-agent: *\nDisallow: /admin\n",
                             {"Content-Type": "text/plain"}), True)

# safe_fetch：429 / 5xx 重試耗盡之後要把狀態碼**本人**還回去。
# 舊版在這裡什麼都不回，外圈 for _hop 拿同一個 URL 再跑一輪，一次 429 變成
# 18 個請求、最後丟 too many redirects。對方說「你太快了」，我們回他 18 個請求，
# 然後把自己的節流誤記成重導向迴圈——source-health 收到的永遠是 error（−15），
# NEUTRAL_STATUSES 裡那個 429 是永遠到不了的死碼。
import sys as _sysmod           # noqa: E402
import time as _timemod         # noqa: E402
import urllib.parse as _uparse  # noqa: E402


class _FakeResp:
    def __init__(self, status):
        self.status_code = status
        self.headers = {}


class _CountingRequests:
    compat = _uparse

    def __init__(self, status):
        self.status = status
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        return _FakeResp(self.status)


_real_sleep = _timemod.sleep
_timemod.sleep = lambda *a, **k: None
_pp.safe_fetch = _REAL_SAFE_FETCH          # 測的是 safe_fetch 本人，不是上面的替身
_real_assert = _pp.assert_public_url
_pp.assert_public_url = lambda u: None     # e.test 不存在，SSRF 檢查不是這條在測的東西
try:
    for _st in (429, 503):
        _fake = _CountingRequests(_st)
        _sysmod.modules["requests"] = _fake
        acase(f"safe_fetch：{_st} 重試耗盡 → 回報 {_st} 本人，不是 too many redirects",
              _pp.safe_fetch("https://e.test/f"), (_st, None, {}))
        acase(f"safe_fetch：{_st} 只重試 3 次就收手，不再乘上 redirect 跳數",
              _fake.calls, 3)
finally:
    _timemod.sleep = _real_sleep
    _pp.assert_public_url = _real_assert
    _sysmod.modules.pop("requests", None)

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
# 這條的名字一直寫著「**未經證實的** robots_ok: false」，判準卻是「有 false 就紅」——
# 名字比判準寬，而寬的那一半正是後來全域規則允許的情況（拿得出 200+disallow 入場券）。
# 寫的時候兩者不衝突，因為當時媒體線的 false 只可能來自本機 403 誤判。
# 2026-07-26 首班 CI 讓它們分岔：recheck 在真網路環境量到 src-media-theregister
# 是 200 且明文 Disallow——那是站方政策，全域規則允許，這條卻照紅。
# 判準對齊名字，不是放寬規則：媒體線一樣不准出現沒有入場券的 false。
acase("sources.yaml: 沒有任何媒體條目寫著未經證實的 robots_ok: false"
      "（403 分不出 WAF 擋包與站方政策，沒有 200+disallow 就是把量測失敗當判決）",
      [s["id"] for s in _cfg["media_sources"]
       if s.get("robots_ok") is False
       and s.get("robots_evidence") != "200+disallow"], [])

# 上面兩條只蓋 kol_sources 與 media_sources，官方線是漏的——2026-07-26 的 review
# 就在 official_sources 找到一條 `robots_ok: false  # …robots.txt 回 403…`，
# 逐字就是設定檔開頭禁止的那個寫法，而且它自我封印：dormant 不會被抓 → 403 判
# unknown_keep → 要 opened 才復活，於是永遠沒有人會發現。
#
# 全域規則改成正面表列：false 可以有，但必須拿得出「200 且明文 Disallow」這張入場券
# （arXiv 就是，它的 robots.txt 真的寫著 Disallow: /）。量不到的一律寫 null。
_bad_false = [(k, s["id"]) for k in _SECTIONS for s in (_cfg.get(k) or [])
              if s.get("robots_ok") is False
              and s.get("robots_evidence") != "200+disallow"]
acase("sources.yaml: 全域——robots_ok: false 必須附 robots_evidence: 200+disallow",
      _bad_false, [])
acase("sources.yaml: 全域——robots_evidence 只出現在 false 的條目上（不得拿來替 true 背書）",
      [(k, s["id"]) for k in _SECTIONS for s in (_cfg.get(k) or [])
       if s.get("robots_evidence") and s.get("robots_ok") is not False], [])

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

# heat 這一段釘的是 2026-07-26 的決定（規格：references/readiness-gate.md）。
#
# 舊狀態：pulse-cluster.rescore() 呼叫 score_event 時 metrics=[]，四項傳播輸入
# （作者/推文/平台/地區，合計 63 分權重）恆為 0，但 heat 照樣算得出 8–48 的數字。
# 那個數字名字叫「傳播熱度」，量到的卻是「獨立來源數＋新鮮度」——用一個比事實
# 寬鬆的代理指標去代表事實。敘述層已經拿它當論據寫過句子（_config/narratives.yaml）。
#
# 修法不是降門檻（會讓 unsupported_heat 開始有反應，但那個反應是假的，紅線 4），
# 也不是重算權重把值域填滿（0–100 的假數字比 8–32 的假數字更難被發現）。
# 修法是紅線 8：量不到就寫量不到——scoring.py 在源頭回 None。
from lib import scoring as _sc  # noqa: E402
_heat_none = [_sc.score_event([90], 2, ind, metrics=[], age_hours=0)["heat"]
              for ind in range(0, 9)]
acase("heat：metrics=[] 時不論獨立來源數多少都是 None，不是一個低分"
      "（「沒有任何傳播證據」算不出熱度，不是算出一個冷的熱度——"
      "這條要是變回數字，敘述層就又有東西可以拿來瞎推論了）",
      sorted(set(str(h) for h in _heat_none)), ["None"])
acase("heat：metrics=[] 時 propagationSignals 記 0"
      "（把「什麼都沒量到」寫成事實欄位，不要人從 heat 缺席去推論）",
      _sc.score_event([90], 2, 3, metrics=[], age_hours=0)["factors"]["propagationSignals"],
      0)
# 反方向：真的量到東西時 heat 必須是數字。只釘 None 那一邊的話，
# 「永遠 None」跟「量到才有值」在測試裡長得一模一樣。
_heat_live = _sc.score_event([90], 2, 3, metrics=[{"platforms": ["x", "y"]}], age_hours=0)
acase("heat：有一項傳播訊號就回數字，propagationSignals 跟著記 1"
      "（反方向；沒有這條，把 heat 寫死成 None 也會全綠）",
      [isinstance(_heat_live["heat"], int), _heat_live["factors"]["propagationSignals"]],
      [True, 1])
# value 的重新配權。heat 缺席時把它那 0.25 按比例分回還在的三項，而不是丟掉——
# 丟掉會讓 value 上限變成 75，跟遷移前的資料不可比。
_v = _sc.score_event([90], 2, 3, metrics=[], age_hours=0)
acase("value：heat 缺席時用 conf·0.40 + impact·0.40 + freshness·0.20"
      "（權重和仍是 1.0；值域不縮水，新舊資料才可比）",
      _v["value"],
      max(0, min(100, round(_v["confidence"] * 0.40 + _v["impact"] * 0.40
                            + _v["factors"]["freshness"] * 0.20))))
# 門檻**不動**的前提就是這一條：社群線接上以後 heat 真的到得了 70。
# 到不了的話「留著 unsupported_heat」就只是把死碼講成休眠碼（紅線 8）。
_heat_full = _sc.score_event(
    [90], 2, 5,
    metrics=[{"authors": 80, "tweets": 300,
              "platforms": ["x", "hn", "reddit", "yt"],
              "regions": ["us", "eu", "cn"]}], age_hours=0)["heat"]
acase("heat：四項傳播輸入都餵滿時跨得過 gate 的 70 → unsupported_heat 是休眠不是報廢"
      "（不動門檻的前提。這條紅了就表示門檻該重談，而不是繼續留著假裝有守）",
      _heat_full >= _yaml.safe_load(
          open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
               encoding="utf-8"))["readiness"]["heat_threshold"],
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


def _vault(days, first_fetch=None, runs=None):
    """days: {'2026-07-25': [corpus row, ...]} → 一個臨時 vault 路徑。

    first_fetch: {sid: 'YYYY-MM-DD...'} → 寫成 `_probe/state.json`
    runs:        [{'day': ..., 'sources': [{'id':..., 'status':...}]}]
                 → 寫成 `_probe/source-runs.jsonl`
    兩個都是 watch entry 觀察期的起算點來源，預設都不寫（＝這條線還沒被觀察過）。
    """
    root = Path(tempfile.mkdtemp())
    for d, rows in days.items():
        p = root / "_corpus" / d
        p.mkdir(parents=True)
        (p / "src-x.jsonl").write_text(
            "\n".join(_json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    if first_fetch or runs:
        (root / "_probe").mkdir(parents=True, exist_ok=True)
    if first_fetch:
        (root / "_probe" / "state.json").write_text(
            _json.dumps({k: {"first_fetch_at": v} for k, v in first_fetch.items()}),
            encoding="utf-8")
    if runs:
        (root / "_probe" / "source-runs.jsonl").write_text(
            "".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in runs),
            encoding="utf-8")
    return root


_SRC_OK = {"official_sources": [{"id": "s-oa", "owner": "OpenAI", "lifecycle": "active"}]}


def _cov(watch, sources, days, first_fetch=None, runs=None):
    cfg = dict(sources)
    cfg["coverage_watch"] = watch
    return _mm.coverage(_vault(days, first_fetch, runs), _TODAY, cfg, _ENT)


def _watch_oa(**kw):
    return {"window_days": 30, "max_silent_days": 14,
            "must_watch": [dict({"entity_id": "openai", "label": "OpenAI"}, **kw)]}


# 語料本身跟這幾條無關（誰都沒提到 OpenAI），變的只有觀察期的起算點。
_NO_HIT = {"2026-07-25": [{"title": "unrelated", "summary": ""}]}


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

_c3 = _cov(_watch_oa(), _SRC_OK, _NO_HIT,
           first_fetch={"s-oa": "2026-07-25T01:00:00+00:00"})
acase("覆蓋率：來源今天才第一次被觀察到 → 不判 silent"
      "（新 vault 不該一開機就滿螢幕紅字）",
      (_c3["must_watch"][0]["observed_days"], _c3["must_watch"][0]["reason"]),
      (1, None))

acase("觀察期：沉默過久但時鐘還沒到門檻的，報表要標記出來"
      "（一個沒有紅字的「從未」，人分不出是「還沒到時候」還是「判斷漏了」）",
      _c3["must_watch"][0]["silent_pending_clock"], True)

_c3b = _cov(_watch_oa(), _SRC_OK,
            {"2026-07-25": [{"title": "OpenAI ships thing", "summary": ""}]},
            first_fetch={"s-oa": "2026-07-25T01:00:00+00:00"})
acase("觀察期：今天才看見過的根本不算沉默，就不該掛「只差時鐘」的記號"
      "（這個記號說的是「只差時鐘」，不是「時鐘還年輕」——名字要跟判準一樣窄）",
      (_c3b["must_watch"][0]["corpus_hits"],
       _c3b["must_watch"][0]["silent_pending_clock"]), (1, False))

_c4 = _cov(_watch_oa(), _SRC_OK, _NO_HIT,
           first_fetch={"s-oa": "2026-06-01T01:00:00+00:00"})
acase("覆蓋率：來源被觀察夠久且該實體從未出現 → silent",
      (_c4["must_watch"][0]["observed_days"], _c4["must_watch"][0]["reason"]),
      (55, "silent"))

# ---- 觀察期要拿「這條線自己的時鐘」量，不是拿整個語料庫的長度 ----
# 舊護欄是 `history_days >= max_silent_days`：history_days 是**整個語料庫**的歷史
# 長度，max_silent_days 是**單一觀察對象**允許沉默的天數。兩個不同層級的數字放進
# 同一個不等式，同一個護欄在兩個方向上都會錯，而且錯法相反。下面兩條就是那兩個
# 方向，各自釘一個。只修其中一邊、或把門檻調高調低，都只會換一格錯。
acase("觀察期：語料庫才 1 天，但這條來源已經被觀察 55 天 → 該叫"
      "（舊護欄拿 history_days 量，這格會安靜——「該叫的不叫」）",
      (_c4["history_days"], _c4["must_watch"][0]["reason"]), (1, "silent"))

_c4b = _cov({"window_days": 400, "max_silent_days": 14,
             "must_watch": [{"entity_id": "openai", "label": "OpenAI"}]},
            _SRC_OK,
            {"2025-07-01": [{"title": "old", "summary": ""}],
             "2026-07-25": [{"title": "unrelated", "summary": ""}]},
            first_fetch={"s-oa": "2026-07-24T01:00:00+00:00"})
acase("觀察期：語料庫已經 390 天，但這條來源昨天才開始被觀察 → 不該叫"
      "（舊護欄拿 history_days 量，這格會誤叫——「不該叫的叫」）",
      (_c4b["history_days"], _c4b["must_watch"][0]["observed_days"],
       _c4b["must_watch"][0]["reason"]), (390, 2, None))

_c4c = _cov(_watch_oa(), _SRC_OK, _NO_HIT,
            first_fetch={"s-oa": "2026-07-24T01:00:00+00:00"},
            runs=[{"day": "2026-06-01",
                   "sources": [{"id": "s-oa", "status": 500}]}])
acase("觀察期：兩個檔案都問、取最早（state.json 說 07-24，班表說 06-01 就在試了）"
      "——「有沒有在看」問的是嘗試不是成功，試了很久才第一次成功，"
      "中間那段沉默是真的沉默",
      (_c4c["must_watch"][0]["observed_days"], _c4c["must_watch"][0]["reason"]),
      (55, "silent"))

_c4d = _cov(_watch_oa(), _SRC_OK, _NO_HIT,
            runs=[{"day": "2026-06-01",
                   "sources": [{"id": "s-oa", "status": 500}]}])
acase("觀察期：從沒成功抓過的來源也要有起算點（只信 first_fetch_at 的話，"
      "一條壞掉的來源會把它自己造成的沉默一起靜音掉——警報自己把自己關掉）",
      (_c4d["must_watch"][0]["observed_days"], _c4d["must_watch"][0]["reason"]),
      (55, "silent"))

_c4e = _cov(_watch_oa(), _SRC_OK, _NO_HIT,
            runs=[{"day": "2026-06-01",
                   "sources": [{"id": "s-oa", "status": "robots_disallow"}]},
                  {"day": "2026-06-02",
                   "sources": [{"id": "s-oa", "status": "robots_unknown"}]},
                  {"day": "2026-06-03",
                   "sources": [{"id": "s-oa", "status": "skipped_lifecycle"}]}])
acase("觀察期：三種 skip 不算嘗試（被 robots 擋住、或還在 dormant 的那些日子，"
      "我們並沒有在看那條線，不能拿來灌觀察期）",
      (_c4e["must_watch"][0]["observed_days"], _c4e["must_watch"][0]["reason"]),
      (0, None))

_c4f = _cov(_watch_oa(), _SRC_OK, _NO_HIT,
            first_fetch={"s-oa": "2026-08-30T01:00:00+00:00"})
acase("觀察期：未來日期的起算點不採計（時鐘壞了不代表我們從未來開始觀察）"
      "——這種狀況由 --alert-stale 的 clock_skew 判紅，訊息才會指向「日期壞了」",
      (_c4f["must_watch"][0]["observed_days"], _c4f["must_watch"][0]["reason"]),
      (0, None))

_c4g = _cov(_watch_oa(),
            {"official_sources": [
                {"id": "s-oa", "owner": "OpenAI", "lifecycle": "active"},
                {"id": "s-oa2", "owner": "OpenAI Newsroom", "lifecycle": "active"}]},
            _NO_HIT,
            first_fetch={"s-oa": "2026-07-24T01:00:00+00:00",
                         "s-oa2": "2026-06-01T01:00:00+00:00"})
acase("觀察期：多條來源取最早的那一條（有一條在看，這家就算被看著了）",
      (len(_c4g["must_watch"][0]["sources"]),
       _c4g["must_watch"][0]["observed_days"]), (2, 55))

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
# 這條的標題以前寫「不是升到 active——機器不發信任」，但 fixture 的 degraded_from
# 就是 probing，還到 active 這件事它**根本沒有能力測**。名字比判準寬，跟這個 repo
# 修過的其他幾條同病。標題改成它真的在測的東西，該測的另外補在下面。
acase("回復：機器自己降的級，連續 3 班成功後自己撤銷，還回降級前那一個狀態",
      [(c[1], c[2], c[3]) for c in _decide([200, 200, 200], _D_DEGRADED, _PRIOR_MACHINE)[0]],
      [("degraded", "probing", "health-recovered")])
acase("回復：連續 2 班成功還不夠（門檻是 3）",
      _decide([200, 200], _D_DEGRADED, _PRIOR_MACHINE)[0], [])
acase("回復：**人手**設的 degraded 機器不碰"
      "（沒有 degraded_by: health 記號＝那是判斷不是量測，不該被三班 200 推翻）",
      _decide([200] * 10, _D_DEGRADED, {})[0], [])

# 還原目標：不變式不是「機器只能寫 degraded」，是「不得把信任抬高到超過人設過的
# 那一級，但要把自己做過的降級**原樣**還回去」。degraded_from 是 active 就還 active
# ——那不是發信任，是還東西。反過來「一律還到 probing」才有害：probing → active
# 需要人跑 checklist，而那個 checklist 至今一次都沒跑過，等於機器可以靜靜收掉人給的
# 信任，而且沒有自癒路徑。（見 references/source-lifecycle.md）
acase("回復：機器把 active 降下來的，就要還回 active"
      "（還東西不是發信任；一律還到 probing ＝機器靜靜收掉人給的信任，而且收掉後"
      "沒有自癒路徑——probing → active 需要人跑 checklist，至今一次都沒跑過）",
      [c[2] for c in _decide([200] * 3, _D_DEGRADED,
                             {"s1": {"degraded_by": "health",
                                     "degraded_from": "active"}})[0]],
      ["active"])
# degraded_from 讀自 source-health.json，那是機器自己寫的檔。不信任它的內容，
# 只信任它的形狀：不在 RESTORABLE 裡的一律退回 probing。
for _bad in ("dormant", "draft", None, "", "active_", 123):
    acase(f"回復：degraded_from = {_bad!r} 不是合法的還原目標 → 退回 probing"
          "（這個值來自機器自己寫的檔案，護欄信任它的形狀不信任它的內容）",
          [c[2] for c in _decide([200] * 3, _D_DEGRADED,
                                 {"s1": {"degraded_by": "health",
                                         "degraded_from": _bad}})[0]],
          ["probing"])
acase("回復：RESTORABLE 的成員逐一釘住（放進 dormant 等於讓機器有一條寫 dormant 的路）",
      sorted(_sh.RESTORABLE), ["active", "probing"])

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

# ── 隔離候選：機器交棒給人的唯一介面 ────────────────────────────────────────
#
# dormant 只有人能寫，所以「哪幾條該停用」機器只能用說的。這份清單斷掉的時候
# **不會有任何東西變紅**：機器以為自己講了，人這邊沒收到。它以前就是斷的——
# quarantine_candidates 只放進 --json 的 stdout 字典，寫到磁碟的 snapshot 沒有這個
# key，於是 pulse-monitor 的 `hjson.get(...) or []` 永遠拿到空清單。
#
# 所以下面測的是**磁碟上的檔案**，不是 stdout：讀它的是別支程式，不是人的眼睛。
_SH_SRC = ("official_sources:\n"
           "  - id: s1\n    lifecycle: degraded\n    endpoint: https://e.test/f\n")


def _sh_vault(tmp, runs_statuses, history_lines=None, health_json=None):
    v = Path(tmp)
    (v / "_config").mkdir(parents=True)
    (v / "_probe").mkdir(parents=True)
    (v / "_config" / "sources.yaml").write_text(_SH_SRC, encoding="utf-8")
    (v / "_config" / "gate.yaml").write_text(
        open(os.path.join(_HERE, "..", "_config", "gate.yaml"), encoding="utf-8").read(),
        encoding="utf-8")
    for i, st in enumerate(runs_statuses):
        _pp.write_run_stats(v, "2026-07-%02d" % (i + 1),
                            [{"id": "s1", "status": st, "items": 0, "error": None}])
    if history_lines is not None:
        (v / "_probe" / "source-history.jsonl").write_text(
            "".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in history_lines),
            encoding="utf-8")
    if health_json is not None:
        (v / "_probe" / "source-health.json").write_text(
            _json.dumps(health_json, ensure_ascii=False), encoding="utf-8")
    return v


def _run_sh(vault, *argv):
    """在子行程跑 pulse-source-health.py，回傳 (returncode, stdout)。

    刻意走子行程而不是直接呼叫 main()：這幾條要測的正是「跑完之後磁碟上多了什麼」，
    而 main() 讀 os.environ["VAULT_DIR"]、還會 argparse sys.argv——在同一個行程裡
    模擬那兩件事，測到的就不再是真正會發生的那條路徑了。
    """
    env = dict(os.environ, VAULT_DIR=str(vault))
    p = _subprocess.run([sys.executable,
                         os.path.join(_HERE, "pulse-source-health.py"), *argv],
                        capture_output=True, text=True, env=env)
    return p.returncode, p.stdout


import subprocess as _subprocess  # noqa: E402

with _tf2.TemporaryDirectory() as _td3:
    # 連續 5 班 503 → 達到 quarantine_after_consecutive，而且來源已經是 degraded。
    _vq = _sh_vault(_td3, [503] * 5)
    _rc, _out = _run_sh(_vq, "--apply")
    _snap = _json.loads((_vq / "_probe" / "source-health.json").read_text("utf-8"))
    acase("隔離候選：寫進**磁碟上的** source-health.json，不是只印在 stdout"
          "（dormant 只有人能寫，這份清單是機器交棒給人的唯一介面；"
          "它斷掉的時候不會有任何東西變紅）",
          _snap.get("quarantine_candidates"), ["s1"])
    # 真正的消費者長什麼樣，照抄 pulse-monitor.py 那一行。
    acase("隔離候選：pulse-monitor 那一行讀得到它"
          "（測 stdout 會漏掉這個 bug——它以前就是 stdout 有、檔案沒有）",
          sorted(_snap.get("quarantine_candidates") or []), ["s1"])

with _tf2.TemporaryDirectory() as _td4:
    # 「只看」的跑法一個檔案都不該留下。以前 atomic_write_text 排在 --apply 的守衛
    # 之前，所以 debug 跑一次 --json，就把 degraded_by: "health" 寫進 state，而
    # sources.yaml 一個字沒動——兩個檔案從此互相矛盾，下一班會以為降級真的發生過。
    _vd = _sh_vault(_td4, [503] * 5)
    _before = sorted(p.name for p in (_vd / "_probe").iterdir())
    _rc, _out = _run_sh(_vd, "--json")
    acase("dry run：`--json` 跑完，_probe/ 一個新檔案都沒有"
          "（宣稱「只看」的旗標留下改動，咬到的是未來的自己）",
          sorted(p.name for p in (_vd / "_probe").iterdir()), _before)
    acase("dry run：`--json` 的 stdout 真的解得開"
          "（那句「加 --apply 才會寫回」以前無條件印在 JSON 後面）",
          sorted(_json.loads(_out)), ["changes", "prior_source",
                                      "quarantine_candidates", "runs", "sources"])
    _rc2, _out2 = _run_sh(_vd, )
    acase("dry run：不加旗標也一樣不寫",
          sorted(p.name for p in (_vd / "_probe").iterdir()), _before)

with _tf2.TemporaryDirectory() as _td5:
    # 刪掉 source-health.json 以前是一個**吸收態**：掉的不是分數（分數每班都從
    # source-runs.jsonl 完整重算），是 degraded_by / degraded_from。少了那兩個記號，
    # 機器降下去的來源跟人手設的 degraded 長得一模一樣，而人手設的機器不碰——
    # 那幾條就永遠停在 degraded。而且進去之後的樣子跟「一切正常」完全一樣，
    # 沒有任何一格會變紅。修法不是加警告，是讓它不再是吸收態。
    _hist = [{"at": "2026-07-01T00:00:00+00:00", "id": "s1", "field": "lifecycle",
              "from": "active", "to": "degraded", "reason": "health-degraded"}]
    _vr = _sh_vault(_td5, [200] * 3, history_lines=_hist)
    acase("吸收態：source-health.json 不見時，降級記號從 append-only 的歷史重建"
          "（不然機器自己降的級會跟人手設的長得一模一樣，永遠回不來，而且不會變紅）",
          _sh.rebuild_prior_from_history(_vr),
          {"s1": {"degraded_by": "health", "degraded_from": "active"}})
    _rc, _out = _run_sh(_vr, "--apply")
    _snap5 = _json.loads((_vr / "_probe" / "source-health.json").read_text("utf-8"))
    # 判準看的是 sources.yaml 真的被寫成什麼，不是 degraded_by 變成 None——
    # 沒重建成功時 degraded_by 本來就是 None，拿它當判準的話這條測試測不到東西。
    acase("吸收態：重建之後那條來源真的自己回到降級前的那個狀態（active）",
          [_yaml.safe_load((_vr / "_config" / "sources.yaml").read_text("utf-8"))
           ["official_sources"][0]["lifecycle"],
           _snap5["sources"]["s1"]["degraded_by"]], ["active", None])
    acase("吸收態：snapshot 記下記號是重建來的，讓「重建過」在檔案裡看得見"
          "（重建靠的是 --apply 有寫進歷史，那個假設哪天不成立時這一欄是唯一線索）",
          _snap5["prior_source"], "history")
    acase("吸收態：正常路徑的 prior_source 是 snapshot",
          _json.loads(_run_sh(_vr, "--json")[1])["prior_source"], "snapshot")

with _tf2.TemporaryDirectory() as _td6:
    _hist6 = [{"at": "2026-07-01T00:00:00+00:00", "id": "s1", "field": "lifecycle",
               "from": "active", "to": "degraded", "reason": "health-degraded"},
              {"at": "2026-07-02T00:00:00+00:00", "id": "s1", "field": "lifecycle",
               "from": "degraded", "to": "active", "reason": "health-recovered"}]
    acase("吸收態：已經還過的降級不會被重建成還沒還"
          "（歷史是 append-only，要照順序放完才是當下的狀態）",
          _sh.rebuild_prior_from_history(_sh_vault(_td6, [200], history_lines=_hist6)),
          {})

with _tf2.TemporaryDirectory() as _td7:
    _hist7 = [{"at": "2026-07-01T00:00:00+00:00", "id": "s1", "field": "robots_ok",
               "from": None, "to": False, "reason": "robots-recheck"}]
    acase("吸收態：歷史裡 robots 那些列不是 lifecycle 異動，重建時要跳過"
          "（兩支腳本共用同一個檔）",
          _sh.rebuild_prior_from_history(_sh_vault(_td7, [200], history_lines=_hist7)),
          {})

# ------------------------------------------- gate.yaml 標記涵蓋（2026-07-26 傍晚）
# 未接線不是 bug（好幾個是預留規格），沒標出來才是：一個寫著正常數字的假欄位，
# 會讓下一個人把它改掉、重跑、看到行為沒變，然後去懷疑資料壞了。
#
# 這一段本來是一份**手寫的** 12 個名字的清單，它只釘得住一個方向：「標了未接線、
# 後來卻接上了」。反方向——有人新增一個沒接線的 key 而忘了標——上一版誠實寫了
# 「測不到」，然後就沒有再管它。誠實地記下一個洞不會把洞補起來：機械列舉 55 個
# leaf 之後，當場掉出兩個從來沒進過那張清單的（quality.weights 整塊、
# readiness.require_primary_evidence）。
#
# 現在的規矩：**列舉是機械的，標記是人寫的，測試比對兩者。**
# 規格與這條檢查「不保證什麼」，見 references/gate-config-status.md。
from lib import gate_keys as _gk  # noqa: E402

_gate_txt = open(os.path.join(_HERE, "..", "_config", "gate.yaml"), encoding="utf-8").read()
_leaves = _gk.parse(_gate_txt)
_scripts_blob = "\n".join(
    open(p, encoding="utf-8").read()
    for p in sorted(_glob.glob(os.path.join(_HERE, "**", "*.py"), recursive=True))
    if os.path.basename(p) != "selftest.py")


def _read_repo_file(rel):
    p = os.path.join(_HERE, "..", rel)
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else None


# 機械列舉自己要先是活的：leaf 數掉到個位數（例如 regex 被改壞、只認得第一層）
# 時，下面三條會全部「通過」，因為沒有東西可以違規。
acase("gate.yaml：機械列舉真的掃到整個檔"
      "（列舉壞掉的時候底下每一條檢查都會變成空集合＝永遠綠）",
      len(_leaves) > 40, True)
acase("gate.yaml：每一個 leaf key 都要被標記涵蓋——"
      "「⚠ …未接線」或「消費者：<路徑>」，標在自己那一行或任何一層祖先上"
      "（這是舊版手寫清單量不到的那個方向：新增一個沒接線的 key 而忘了標）",
      _gk.unmarked(_leaves), [])
acase("gate.yaml：標成「未接線」的 key 必須真的沒有消費者"
      "（哪天有人去接線了，這條會紅，提醒他回來把標記跟 references/ 一起改掉）",
      _gk.wired_but_marked_unwired(_leaves, _scripts_blob), [])
acase("gate.yaml：標了「消費者：X」就要真的在 X 裡搜得到這個名字"
      "（消費者被刪掉或改名之後，標記會留在原地繼續說一件不成立的事）",
      _gk.consumer_missing(_leaves, _read_repo_file), [])

# 判準本身的單元測試。這幾條是在釘「檢查會不會誤放」，不是在釘 gate.yaml。
acase("gate_keys：註解裡出現的名字不算消費者"
      "（純子字串比對會把 lib/sources.py 那句註解讀成 require_primary_evidence 有人在用）",
      _gk.name_in_code("foo", "# foo 只是註解裡提到\nbar = 1"), False)
acase("gate_keys：字串常值出現才算消費者",
      _gk.name_in_code("foo", 'cfg.get("foo", 1)'), True)
acase("gate_keys：沒有 ⚠ 的「未接線」三個字不算標記"
      "（否則散文裡順口提一句就能把一個假欄位洗白；這裡要看的是 unwired 旗標，"
      "不是有沒有列舉到——只比對 path 的話這條會恆真）",
      [(e["path"], e["unwired"]) for e in _gk.parse("a:\n  # 這個之後未接線再說\n  b: 1\n")],
      [("a.b", False)])
acase("gate_keys：⚠ 標在祖先上，底下的 leaf 都算被標到",
      [(e["path"], e["unwired"]) for e in _gk.parse("# ⚠ 整塊未接線\na:\n  b: 1\n  c: 2\n")],
      [("a.b", True), ("a.c", True)])
acase("gate_keys：有子 key 的中間節點不算 leaf（只算最底下那一層）",
      [e["path"] for e in _gk.parse("a:  # 消費者：scripts/x.py\n  b:\n    c: 1\n")],
      ["a.b.c"])
_ck = _gk.parse("zzz_key:  # 消費者：scripts/x.py\n  b: 1\n")
acase("gate_keys：指名的消費者檔案不存在時要報出來，不是靜靜跳過"
      "（檔案被刪掉之後，標記會留在原地繼續說一件不成立的事）",
      _gk.consumer_missing(_ck, lambda p: None), ["zzz_key → scripts/x.py"])
acase("gate_keys：指名的檔案裡真的讀得到就放行（反方向，確認上一條不是恆紅）",
      _gk.consumer_missing(_ck, lambda p: 'cfg["zzz_key"]'), [])

acase("references/gate-config-status.md 存在（gate.yaml 的標記指向它）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "gate-config-status.md")),
      True)
acase("gate.yaml：heat 那三個標的是「接線了但走不到」而不是「未接線」"
      "（它們確實被 pulse-gate.py 讀到，病因不同，修法也不同——"
      "把 70 調小是紅線 4 禁止的那種修法）",
      "接線了但走不到" in _gate_txt and "M3" in _gate_txt, True)
acase("gate.yaml：heat 那段要寫著門檻刻意不動、以及 heat 現在會是 null"
      "（這段註解被改回「上限 48」那種描述＝又退回「有數字但數字是假的」的世界）",
      "unmeasured_heat" in _gate_txt and "null" in _gate_txt, True)
# 反方向：畢業的 key 不准悄悄退回未接線。把 --write-health 那段刪掉、
# 或把讀 gate.yaml 那兩行拿掉，都會在這裡紅。
_mon_txt = open(os.path.join(_HERE, "pulse-monitor.py"), encoding="utf-8").read()
acase("gate.yaml：monitor.stale_after_days 真的被 pulse-monitor.py 讀進去"
      "（畢業的 key 不准悄悄退回未接線）",
      "stale_after_days" in _mon_txt and 'gate.get("monitor")' in _mon_txt, True)
acase("gate.yaml：monitor.stale_after_days 旁邊不該再留「未接線」標記"
      "（標記留著＝文件說謊的另一個方向）",
      [e["path"] for e in _leaves if e["key"] == "stale_after_days" and e["unwired"]], [])
# require_primary_evidence 是「刻意不接」：它標著未接線，而那個標記必須留著。
# 有人把那一行接上去（讓 gate.yaml 可以關掉紅線 2 唯一的執法點），
# wired_but_marked_unwired 會紅；有人只是把標記拿掉，這一條會紅。
acase("gate.yaml：require_primary_evidence 必須維持「刻意不接」的標記"
      "（把它做成真開關＝紅線 2 多了一個設定檔層級的關閉鍵，而 selftest 全綠，"
      "因為每一條測試都是拿預設值跑的）",
      [(e["unwired"], "刻意" in _gate_txt.split("require_primary_evidence")[0][-900:])
       for e in _leaves if e["key"] == "require_primary_evidence"],
      [(True, True)])

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

# 上面那條只看**清單的名字**，不看 render() 有沒有照著清單走。
# `for k in FM_FROM_CONFIG:` 改成 `for k in src:` 的話，清單一個字都沒動，
# 上面那條照樣全綠，而整個 sources.yaml 條目——包含 api_key 與本機路徑——
# 會被倒進 vault 裡跟著 commit 上去。紅線 6 那條邊界要由行為來守，不是由名單。
_leaky = {"id": "s-leak", "owner": "Someone", "lifecycle": "active",
          "endpoint": "https://example.invalid/feed.xml",
          # 以下每一個都不在白名單裡，一個都不准出現在輸出中。
          "api_key": "sk-THIS-MUST-NOT-LEAK", "headers": {"Authorization": "Bearer x"},
          "local_path": "/home/someone/notes", "cookie": "sid=abc",
          "private_note": "內部備註：這條是老闆朋友介紹的"}
_leak_out = _sn.render(_leaky, 0, None, 0, 0, {}, {})
acase("來源頁：白名單以外的欄位真的進不去（紅線 6 的邊界由行為守，不是由名單守）"
      "——`for k in FM_FROM_CONFIG` 改成 `for k in src` 時上面那條不會紅",
      [k for k in ("api_key", "THIS-MUST-NOT-LEAK", "headers", "Authorization",
                   "local_path", "cookie", "private_note", "老闆")
       if k in _leak_out], [])

acase("來源頁：白名單內的公開欄位還是要進得去"
      "（不然把 render 改成什麼都不寫也會讓上面那條變綠）",
      [_s in _leak_out for _s in ('owner: "Someone"', 'lifecycle: "active"',
                                  'endpoint: "https://example.invalid/feed.xml"')],
      [True, True, True])

# ── 量不到 ≠ 量到 0（紅線 8），而且這個違規印在給人看的頁面上 ──────────────
# `items_observed: 0` 有兩個完全不同的意思：這條來源成功抓過、只是那陣子站上
# 沒東西（量到 0），跟它從來沒有成功抓過一次（量不到，我們一無所知）。
# 2026-07-26 首班之後有 3 條在 Sources/*.md 上印「已觀測 0 筆」，其中 2 條
# 從沒抓過——這正是「用空值代表兩種不同的事」，跟目錄名代表「那天有語料」同形態。
# 判準是 first_fetch_at 有沒有值，不是 state.json 裡有沒有這個條目：
# 失敗也會留下 etag / last_run，只有成功抓過一次才 setdefault 那個欄位。
_SRC_N = {"id": "s-never", "lifecycle": "probing", "endpoint": "https://e.test/f"}
_never = _sn.render(_SRC_N, 0, None, 0, 0, {"etag": "x", "last_run": "2026-07-26"}, None)
_measured = _sn.render(_SRC_N, 0, None, 0, 0, {"first_fetch_at": "2026-07-26"}, None)
acase("來源頁：從沒抓過的來源印「尚未抓取過」，不印「0 筆」（紅線 8）",
      ["尚未抓取過" in _never, "0 筆" in _never], [True, False])
acase("來源頁：從沒抓過時 items_observed 留空，不寫 0"
      "（0 是量到 0，空是量不到——寫 0 就是把量測失敗當成事實）",
      _re.search(r"^items_observed:\s*$", _never, _re.M) is not None, True)
acase("來源頁：抓過但相異數是 0 的來源照舊印「0 筆」（那是真的量到 0）",
      ["0 筆" in _measured, "尚未抓取過" in _measured], [True, False])
acase("來源頁：光有 state.json 條目不算抓過（失敗也會留下 etag / last_run）",
      "尚未抓取過" in _never, True)

# ── 「收錄」那格印事實，不印設定意圖 ────────────────────────────────────
# lifecycle 是設定意圖，last_status 是上一班的事實，兩者會分岔：一條
# lifecycle: probing 的來源如果每班都被 robots 擋掉，設定說「會被抓」，
# 事實是一次都沒抓。只印 lifecycle 就是拿比事實寬鬆的代理指標代表事實——
# 這一頁本來就是為了不讓那種事發生才存在的。
# 2026-07-26 實測：src-media-theregister 是 robots_disallow（站方政策），
# src-kol-thezvi 與 src-amd-ir 是 robots_unknown（robots.txt 取不到，保守跳過）。
# 三種都不是故障，但頁面不能說「會被抓」。
for _st, _want in (("robots_disallow", "Disallow"),
                   ("robots_unknown", "取不到"),
                   ("skipped_lifecycle", "不會被抓")):
    _pg = _sn.render(_SRC_N, 0, None, 0, 0, {}, {"last_status": _st})
    acase(f"來源頁：last_status = {_st} 時，「收錄」那格印被跳過的理由而不是「會被抓」",
          [_want in _pg, "| 會被抓 |" in _pg], [True, False])
_pg_ok = _sn.render(_SRC_N, 1, "2026-07-26", 0, 0,
                    {"first_fetch_at": "2026-07-26"}, {"last_status": 200})
acase("來源頁：真的抓得到的來源，「收錄」那格照舊印「會被抓」"
      "（判準對齊事實不是放寬規則，正常的路徑不能跟著變模糊）",
      "會被抓" in _pg_ok, True)

# 「已觀測」數的是相異項目，不是行數。`_corpus/<日>/` 是**當天看到的清單**不是
# 當天新增的清單：還掛在 feed 上的新聞每天都會再被寫一次。累計行數數的是
# 「項目 × 天」——2026-07-26 實測 956 行對 553 個相異項目，虛胖近一倍。
# 虛胖還不是最糟的，最糟的是它跟旁邊那格「有效產出」（刻意去重過的事件數）
# **不同單位**：兩個不同單位的數字並排比較，得到的印象一定是錯的。
#
# 這幾條刻意自己開一個 vault，不借用下面那個：下面那個的日曆是「07-03 有跑班、
# 語料只到 07-02」，是專門用來釘死人開關的形狀。往它的 _corpus/2026-07-03/ 塞
# 語料，會把那個形狀弄平，而且弄平的方式是讓紅燈測試變綠——測試 fixture 之間
# 互相把對方的警報關掉，也是「警報自己把自己關掉」。
with tempfile.TemporaryDirectory() as _dc:
    _vc = Path(_dc)
    for _day in ("2026-07-01", "2026-07-02", "2026-07-03"):
        (_vc / "_corpus" / _day).mkdir(parents=True)
        (_vc / "_corpus" / _day / "s2.jsonl").write_text(
            '{"url_canonical":"https://e.test/a"}\n'
            '{"url_canonical":"https://e.test/b"}\n', encoding="utf-8")
    (_vc / "_corpus" / "2026-07-03" / "s3.jsonl").write_text(
        '{"url":"https://e.test/x"}\n'
        '{"url":"https://e.test/x"}\n'
        '{"title":"沒有任何 url 的一列"}\n'
        '這一行不是 JSON\n', encoding="utf-8")
    _cntc, _lastc = _corpuslib.observed(_vc)
    acase("來源頁：已觀測數相異項目、不數行數"
          "（同兩則新聞連續掛三天＝6 行，但只有 2 個項目）",
          [_cntc["s2"], _lastc["s2"]], [2, "2026-07-03"])
    acase("來源頁：沒有 url_canonical 的舊列退回用 url；連 url 都沒有、或整行解不出來的"
          "各算一個（分不出是不是同一則就寧可高估，不要靜靜把資料吃掉）",
          _cntc["s3"], 3)

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
    # 被丟掉的事件不是「有效產出」。算進來的話，「抓到了但聚類沒綁上」跟
    # 「綁上了但被丟掉」在頁面上長得一模一樣。
    (_v3 / "Events" / "e3.md").write_text(
        "---\nid: e3\nstatus: dropped\nevidence:\n  - source_id: s1\n---\n\n內文\n",
        encoding="utf-8")
    _ev, _pub = _sn.bound(_v3)
    acase("來源頁：有效產出數的是**事件數**不是證據筆數"
          "（一則事件引同一條來源三次仍然只算一則）", [_ev["s1"], _pub["s1"]], [2, 1])
    acase("來源頁：有效產出不含 status: dropped 的事件"
          "（被丟掉的不是產出，算進來會讓「沒綁上」跟「綁上了但被丟」看起來一樣）",
          _ev["s1"], 2)

    # _corpus/ 的盤點單一真相源：兩天各一條，累計 3 筆，最後一天取較晚的那天。
    for _day, _n in (("2026-07-01", 1), ("2026-07-02", 2)):
        (_v3 / "_corpus" / _day).mkdir(parents=True)
        (_v3 / "_corpus" / _day / "s1.jsonl").write_text(
            "".join('{"url_canonical":"https://e.test/%d"}\n' % i
                    for i in range(_n)), encoding="utf-8")
    _cnt, _last = _corpuslib.observed(_v3)
    acase("來源頁：已觀測是跨日累計，最後一天取最晚的那天",
          [_cnt["s1"], _last["s1"]], [2, "2026-07-02"])

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

# 以下四條改成解析 YAML 結構來判，不再用字串位置。字串位置的問題是：
# 改個 step 名字就會紅，而真正該紅的（兩個指令被塞進同一個 run:）它看不見。
_wfdoc = _yaml.safe_load(_wf)
_steps = _wfdoc["jobs"]["refresh"]["steps"]


def _step_run(i):
    return str(_steps[i].get("run") or "")


def _step_with(needle):
    """→ 含這個字串的 step 索引清單。"""
    return [i for i in range(len(_steps)) if needle in _step_run(i)]


# bash -e：同一個 run: 底下，前面那行非零，後面那行根本不會執行。
# pulse-source-notes 與 --write-health 曾經同處一個 run:，後果很具體：
# state.json 被寫壞成非 dict → 筆記產生器炸掉 → health.md 停在昨天 →
# generated_day 不動 → 死人開關報「排程死了」。鏈是好的，死的是一支觀測腳本，
# 而假訊號指向錯的地方比沒有訊號更花時間。
acase("排程：source-notes 與 --write-health 不得共用同一個 run:"
      "（bash -e 會讓前者一炸就吃掉後者，health.md 停住＝偽造「排程死了」）",
      _step_with("pulse-source-notes.py") == _step_with("--write-health"), False)

# probe 的非零全部是致命的（2 = 環境不見了，3 = 0 個可跑來源的硬防護）。
# 單條來源抓失敗只寫進 stats，main() 照樣 return 0——也就是說 `|| ...` 沒有接住
# 任何「部分失敗」，只接住了兩種必須紅燈的狀況。實測：全部 lifecycle 改 draft，
# probe 回 3 被吞掉，後面照跑、網站照部署、job 全綠，只是再也不會更新。
_probe_lines = [ln.strip() for i in _step_with("pulse-probe.py")
                for ln in _step_run(i).splitlines()
                if "pulse-probe.py" in ln and not ln.strip().startswith("#")]
acase("排程：pulse-probe.py 的離開碼不得被 || 或 ; true 吞掉"
      "（它的非零全是致命的，硬防護寫了不接等於沒寫）",
      [ln for ln in _probe_lines if "||" in ln or "; true" in ln], [])

# 純顯示用的那次 robots 重驗如果不給 --stale-days，預設 0；而 check() 判的是
# `if stale_days and ...`，0 是 falsy＝一條都不跳，於是整份來源的 robots.txt
# 被再抓一次。加上 apply 那次、probe 抓每條來源那次，一班三抓。
_recheck_lines = [ln.strip() for i in _step_with("pulse-robots-recheck.py")
                  for ln in _step_run(i).splitlines()
                  if "pulse-robots-recheck.py" in ln and not ln.strip().startswith("#")]
acase("排程：每一次 pulse-robots-recheck 都要明示 --stale-days"
      "（省略＝預設 0＝一條都不跳＝每班把所有來源的 robots.txt 再抓一遍）",
      [ln for ln in _recheck_lines if "--stale-days" not in ln], [])

# 順序有兩個硬條件：在 Source health 之後（才讀得到這一班的分數）、
# 在 commit 之前（不然寫出來的檔案下一次 checkout 就被洗掉）。
acase("排程：vault 頁排在 Source health 之後、Commit 之前"
      "（排在 commit 之後＝每班寫完就被洗掉，等於整天沒產出）",
      (max(_step_with("pulse-source-health.py"))
       < min(_step_with("pulse-source-notes.py") + _step_with("--write-health"))
       <= max(_step_with("pulse-source-notes.py") + _step_with("--write-health"))
       < min(_step_with("git push"))), True)
acase("references/vault-pages.md 存在（這兩頁的規格書，紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "vault-pages.md")), True)

# ── 現況表改成每班重生成（references/vault-pages.md〈backlog-status.md〉）──
# BACKLOG.md 以前有一張手寫的現況表，寫下之後 3 小時就過期。第一次的修法是
# 「把量測時間寫進標題、請下一個人複量」——一個靠人記得的機制，而那份清單存在
# 的理由就是不要有那種機制。這幾條釘的是「數字真的搬出去了、而且搬到會動的地方」。
acase("排程：backlog-status 真的被排進 workflow"
      "（沒排進去就只是把「寫好了但沒人叫它」搬個地方）",
      bool(_step_with("pulse-backlog-status.py")), True)
acase("排程：backlog-status 不得跟另外兩頁共用同一個 run:"
      "（bash -e：它一炸就吃掉後面那支，而後面那支可能正是 health.md）",
      [_step_with("pulse-backlog-status.py") == _step_with("pulse-source-notes.py"),
       _step_with("pulse-backlog-status.py") == _step_with("--write-health")],
       [False, False])
acase("排程：backlog-status 也要排在 Source health 之後、Commit 之前",
      (max(_step_with("pulse-source-health.py"))
       < min(_step_with("pulse-backlog-status.py"))
       < min(_step_with("git push"))), True)

_bs_spec = importlib.util.spec_from_file_location(
    "pulse_backlog_status", os.path.join(_HERE, "pulse-backlog-status.py"))
_bs = importlib.util.module_from_spec(_bs_spec)
_bs_spec.loader.exec_module(_bs)

_bs_vault = Path(os.path.join(_HERE, ".."))
_bs_facts = _bs.collect(_bs_vault)
_bs_text = _bs.render(_bs_facts, "2026-07-27")

acase("backlog-status：真的量到這個 vault 的東西，不是一頁樣板"
      "（每一格都空的話，下面幾條都會「通過」，因為沒有東西可以錯）",
      [_bs_facts["events"]["total"] > 0, _bs_facts["corpus"]["days"] > 0,
       _bs_facts["sources"]["total"] > 0, _bs_facts["gate"]["leaves"] > 40], [True] * 4)
import ast as _ast  # noqa: E402


def _imported_modules(path):
    """這支腳本 import 了哪些頂層模組。走 AST 不走字串比對——"subprocess"
    這幾個字出現在 docstring 裡不算 import，而字串比對分不出來。"""
    tree = _ast.parse(open(path, encoding="utf-8").read())
    mods = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, _ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


acase("backlog-status：不碰網路、不跑子行程"
      "（加任何一項，這一頁在沒網路的環境就會長得不一樣，不能拿來對帳）",
      sorted(_imported_modules(os.path.join(_HERE, "pulse-backlog-status.py"))
             & {"subprocess", "requests", "urllib", "socket", "http", "feedparser"}),
      [])
acase("backlog-status：缺席的欄位印「量不到」，不印 0（紅線 8）",
      [_bs._n(None), _bs._n(0)], ["量不到", "0"])
acase("backlog-status：空 vault 也產得出頁面，而且每一格都說「量不到」"
      "（產不出來就等於這一頁在最需要它的那天不存在）",
      _bs.render({"events": {}, "corpus": {}, "sources": {}, "gate": {},
                  "last_run": {}}, "2026-07-27").count("量不到") >= 6, True)
acase("backlog-status：刻意不放 selftest 條數與變異結果"
      "（不是每班量得到的事實，放上來就是一個「上次不知道什麼時候量的」數字）",
      ["/360" in _bs_text, "47 條" in _bs_text], [False, False])
acase("backlog-status：零產出那一格只列 id，不重算屬於哪一種 0"
      "（重算就會有兩份判準，而兩份判準遲早會給出不同的答案）",
      [c in _bs_text for c in ("prefix_filtered_all", "source_empty",
                               "hints_matched_nothing")], [False] * 3)
acase("backlog-status：零產出那一格印的真的是 source id"
      "（只釘「不含判定字串」的話，把它改成印 status 也會通過——那條測試沒在測任何東西）",
      _bs.last_run_facts(_bs_vault)["zero_yield"],
      sorted(s["id"] for s in _json.loads(
          [l for l in open(os.path.join(_HERE, "..", "_probe", "source-runs.jsonl"),
                           encoding="utf-8").read().splitlines() if l.strip()][-1]
      )["sources"] if s.get("status") == 200 and not s.get("items")))

# 「內容沒變就不重寫」是共同規則（一天 12 班，12 個沒有資訊量的 diff 會把真正的
# 變化埋掉）。這條走真的 main()：只跑 render() 測不到寫檔那條路徑。
with tempfile.TemporaryDirectory() as _bstd:
    _bsv = Path(_bstd)
    (_bsv / "_config").mkdir()
    (_bsv / "_config" / "sources.yaml").write_text(
        "official_sources:\n  - id: s1\n    lifecycle: probing\n    language: en\n",
        encoding="utf-8")
    _bs_argv, _bs_env = sys.argv[:], os.environ.get("VAULT_DIR")
    sys.argv = ["pulse-backlog-status.py", "--quiet"]
    os.environ["VAULT_DIR"] = str(_bsv)
    try:
        _bs.main()
        _bs_page = _bsv / "_dashboards" / "backlog-status.md"
        _bs_existed = _bs_page.is_file()
        os.utime(_bs_page, (0, 0))          # 把 mtime 壓成 0，第二輪有沒有寫得出來
        _bs.main()
        _bs_untouched = _bs_page.stat().st_mtime == 0
    finally:
        sys.argv = _bs_argv
        if _bs_env is not None:
            os.environ["VAULT_DIR"] = _bs_env
acase("backlog-status：第一輪真的寫得出檔案，第二輪內容沒變就不重寫"
      "（只釘「沒重寫」的話，一支根本不寫檔的腳本也會通過）",
      [_bs_existed, _bs_untouched], [True, True])

# 真正的重點：BACKLOG.md 裡不可以再有手寫的現況表。
_backlog_txt = open(os.path.join(_HERE, "..", "BACKLOG.md"), encoding="utf-8").read()
_backlog_status_head = _backlog_txt.split("## 為什麼這裡沒有編號")[0]
acase("BACKLOG.md：〈現況〉那一段指向 _dashboards/backlog-status.md",
      "_dashboards/backlog-status.md" in _backlog_status_head, True)
acase("BACKLOG.md：〈現況〉那一段不再有手寫的量測表"
      "（留一張就夠了——會過期的正是那一張，不是旁邊的散文）",
      "| 量到什麼 | 值 |" in _backlog_status_head, False)

# ── Tracks/ 與 Actors/：關聯圖的另外兩維（references/obsidian-schema.md）──
from lib import tracks as _tk  # noqa: E402

_en_spec = importlib.util.spec_from_file_location(
    "pulse_entity_notes", os.path.join(_HERE, "pulse-entity-notes.py"))
_en = importlib.util.module_from_spec(_en_spec)
_en_spec.loader.exec_module(_en)

acase("references/obsidian-schema.md 存在（這兩層的規格書，紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "obsidian-schema.md")),
      True)
acase("排程：entity notes 真的被排進 workflow，且不跟別頁共用同一個 run:",
      [bool(_step_with("pulse-entity-notes.py")),
       _step_with("pulse-entity-notes.py") == _step_with("pulse-dictionary-gaps.py")],
      [True, False])
acase("排程：entity notes 也排在 Source health 之後、Commit 之前",
      (max(_step_with("pulse-source-health.py"))
       < min(_step_with("pulse-entity-notes.py"))
       < min(_step_with("git push"))), True)
acase("Tracks/ 與 Actors/ 要在資料 commit 白名單裡"
      "（不在的話，鏈每班寫出來、每班被 git add -A 之外的規矩擋掉，"
      "或更糟：寫了但沒人知道該不該推）",
      [d in _read_repo_file("AGENTS.md") and d in _read_repo_file("CONTRIBUTING.md")
       for d in ("Tracks/", "Actors/")], [True, True])

# 主線對照表只有一份：抄第二份的失敗形態這個 repo 量過四次。
acase("主線對照表：六條線，slug / 顯示名 / 顏色都在 lib/tracks.py",
      [len(_tk.TRACKS), len({s for s, _, _ in _tk.TRACKS}),
       len({n for _, n, _ in _tk.TRACKS})], [6, 6, 6])
acase("主線對照表：少一個空白的那種寫法要認得（庫裡真的有「Agent與軟體重構」）",
      [_tk.canonical_name("Agent與軟體重構"), _tk.slug_of("Agent與軟體重構")],
      ["Agent 與軟體重構", "agent-refactor"])
acase("主線對照表：認不出來回 None，**不猜**"
      "（猜一個最接近的，會把將來的新線靜靜併進舊線）",
      [_tk.canonical_name("不存在的線"), _tk.slug_of(""), _tk.slug_of(None)],
      [None, None, None])
acase("主線對照表：renderer 與 narrative-prep 都改讀 lib/tracks.py，不各留一份"
      "（兩份會在有人加一條線的那天分岔，而且不會有任何東西變紅）",
      sorted(n for n in ("pulse-render.py", "pulse-narrative-prep.py")
             if "tracks_lib" in open(os.path.join(_HERE, n), encoding="utf-8").read()),
      ["pulse-narrative-prep.py", "pulse-render.py"])

with tempfile.TemporaryDirectory() as _entd:
    _env2 = Path(_entd)
    (_env2 / "Events").mkdir()
    (_env2 / "_config").mkdir()
    (_env2 / "_config" / "entities.yaml").write_text(
        "companies:\n  - id: openai\n    canonical: OpenAI\n    term_type: company\n"
        "    aliases: [Open AI]\n  - id: meta\n    canonical: Meta\n"
        "    term_type: company\n", encoding="utf-8")
    (_env2 / "_config" / "narratives.yaml").write_text(
        "tracks:\n  infra-cost:\n    thesis: 這條線的主軸\n"
        "    now: 這段每夜重寫\n    next: 這段也是\n", encoding="utf-8")

    def _mkev(i, company, track, status="published", date="2026-07-2%d"):
        (_env2 / "Events" / f"evt-{i}.md").write_text(
            f"---\nid: evt-{i}\ntitle: T{i}\ndate: '2026-07-2{i}'\n"
            f"status: {status}\ncompany: {company}\ntrack: {track}\n---\n本文\n",
            encoding="utf-8")

    _mkev(1, "OpenAI", "基礎設施與成本")
    _mkev(2, "vLLM", "Agent與軟體重構")          # 字典沒有這家 + 少空白的別名
    _mkev(3, "industry", "不存在的線", "review")  # 泛稱兜底 + 認不出的主線
    _pages = _en.plan(_env2, "2026-07-27")

    acase("entity notes：六條主線各一頁，加一頁未歸類",
          sorted(p for p in _pages if p.startswith("Tracks/")),
          sorted([f"Tracks/{_en.safe_name(n)}.md" for n in _tk.NAMES]
                 + ["Tracks/_未歸類.md"]))
    acase("entity notes：Actor 名單是「字典 ∪ Event 出現過」的聯集"
          "（只取字典＝字典缺口永遠看不見；只取 Event＝字典收了卻沒新聞的看不見）",
          sorted(p for p in _pages if p.startswith("Actors/")),
          ["Actors/Meta.md", "Actors/OpenAI.md", "Actors/vLLM.md"])
    acase("entity notes：`industry` 不產 Actor 頁"
          "（那是 infer_company 認不出實體時的泛稱兜底，不是一家公司）",
          "Actors/industry.md" in _pages, False)
    acase("entity notes：字典裡沒有的公司要在頁面上講出來，不是安靜地產一頁",
          ["字典裡沒有這家公司" in _pages.get("Actors/vLLM.md", ""),
           "字典裡沒有這家公司" in _pages.get("Actors/OpenAI.md", "")], [True, False])
    acase("entity notes：字典收了卻一則事件都沒有 → 講清楚那不等於沒新聞",
          "一則事件都沒有" in _pages.get("Actors/Meta.md", ""), True)
    acase("entity notes：邊是「維度頁 → Event」，Event 檔一個字都沒動",
          ["[[Events/evt-1" in _pages.get("Tracks/基礎設施與成本.md", ""),
           (_env2 / "Events" / "evt-1.md").read_text("utf-8").count("[["), ],
          [True, 0])
    _left = _pages.get("Tracks/_未歸類.md", "")
    acase("entity notes：認不出主線、沒有歸屬到公司的事件要列出來，不得靜靜丟掉"
          "（少掉的那些如果沒地方列，「六條線加起來少於 Events 總數」沒人會發現）",
          ["evt-3" in _left, "不存在的線" in _left, "industry" in _left],
          [True, True, True])
    acase("entity notes：thesis 抄進來、`now` / `next` 刻意不抄"
          "（那兩段每夜重寫 → 六個檔每天一個沒有新資訊的 diff，"
          "還會出現兩份可能不一致的同一段話。比對的是**值**不是欄位名——"
          "比對欄位名的話，頁面上那句解釋自己就會讓測試通不過或恆通過）",
          ["這條線的主軸" in _pages.get("Tracks/基礎設施與成本.md", ""),
           "這段每夜重寫" in _pages.get("Tracks/基礎設施與成本.md", ""),
           "這段也是" in _pages.get("Tracks/基礎設施與成本.md", "")],
          [True, False, False])

# ── 字典補漏：report_to 指的那個檔案以前不存在（references/vault-pages.md）──
from lib import dictgaps as _dg  # noqa: E402

_dg_spec = importlib.util.spec_from_file_location(
    "pulse_dictionary_gaps", os.path.join(_HERE, "pulse-dictionary-gaps.py"))
_dgm = importlib.util.module_from_spec(_dg_spec)
_dg_spec.loader.exec_module(_dgm)

acase("排程：dictionary-gaps 真的被排進 workflow，且不跟別頁共用同一個 run:",
      [bool(_step_with("pulse-dictionary-gaps.py")),
       _step_with("pulse-dictionary-gaps.py") == _step_with("pulse-backlog-status.py")],
      [True, False])
acase("排程：dictionary-gaps 也排在 Source health 之後、Commit 之前",
      (max(_step_with("pulse-source-health.py"))
       < min(_step_with("pulse-dictionary-gaps.py"))
       < min(_step_with("git push"))), True)

acase("字典補漏：門檻讀 gate.yaml，不是硬寫在腳本裡",
      _dg.thresholds({"clustering": {"unknown_entity":
                                     {"promote_min_hits": 9,
                                      "promote_min_sources": 4}}}), (9, 4))
acase("字典補漏：門檻讀不到就退回預設 3 / 2，**不是 0**"
      "（0 會讓每個一次性雜訊都晉升——設定檔壞掉不可以讓門檻自己打開）",
      [_dg.thresholds({}), _dg.thresholds({"clustering": {"unknown_entity":
                                                          {"promote_min_hits": 0}}})],
      [(3, 2), (3, 2)])
acase("字典補漏：真實 gate.yaml 現在真的有這兩個門檻（不是只靠預設值活著）",
      _dg.thresholds(_yaml.safe_load(
          open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
               encoding="utf-8").read())), (3, 2))

_dg_rows = [{"source_id": "a", "candidates": ["Gemma", "June"]},
            {"source_id": "b", "candidates": ["Gemma"]},
            {"source_id": "a", "candidates": ["Gemma", "June"]},
            {"source_id": "a", "candidates": ["June"]}]
_dg_cnt, _dg_srcs = _dg.tally(_dg_rows)
acase("字典補漏：達標＝次數夠**而且**跨來源夠（兩個條件都要，少一個就變成雜訊清單）",
      _dg.promoted(_dg_cnt, _dg_srcs, 3, 2), [("Gemma", 3, 2)])
acase("字典補漏：次數夠但只有一個來源 → 進觀察區，不進晉升區",
      _dg.single_source(_dg_cnt, _dg_srcs, 3), [("June", 3, "a")])

with tempfile.TemporaryDirectory() as _dgtd:
    _dgv = Path(_dgtd)
    for _d in ("2026-07-24", "2026-07-25"):
        (_dgv / "_corpus" / _d).mkdir(parents=True)
        # **同一則新聞兩天都在 feed 上**——這正是「項目 × 天」那個坑。
        (_dgv / "_corpus" / _d / "s1.jsonl").write_text(_json.dumps({
            "source_id": "s1", "url_canonical": "https://x.test/a",
            "candidates": ["Gemma"]}) + "\n", encoding="utf-8")
    acase("字典補漏：跨天累積時同一則只算一次"
          "（直接加行數數到的是「項目 × 天」，items_observed 踩過同一個坑，虛胖一倍）",
          len(_dgm.corpus_rows(_dgv)), 1)
    acase("字典補漏：report_to 讀設定檔（這一行就是那個 key 的消費者）",
          _dgm.report_path(_dgv, {"clustering": {"unknown_entity":
                                                 {"report_to": "_dashboards/x.md"}}}),
          (_dgv / "_dashboards" / "x.md").resolve())
    acase("字典補漏：report_to 指到 vault 外面就退回預設，不是靜靜寫出去",
          _dgm.report_path(_dgv, {"clustering": {"unknown_entity":
                                                 {"report_to": "../../etc/x.md"}}}),
          (_dgv / "_dashboards" / "dictionary-gaps.md").resolve())

# 兩個消費者讀同一份門檻：改 gate.yaml 的值，probe 的當班區塊要跟著動。
# 只測 dictgaps 那一支的話，probe 裡再硬寫一次 `>= 3` 也不會被抓到。
with tempfile.TemporaryDirectory() as _dgtd2:
    _dgv2 = Path(_dgtd2)
    (_dgv2 / "_probe" / "2026-07-27").mkdir(parents=True)
    _dg_report = _pp.write_report(
        _dgv2, "2026-07-27",
        [{"source_id": "s1", "track": "official", "author": None,
          "author_kind": "none", "entity_hits": [], "entity_types": [],
          "candidates": ["Gemma"], "backfill": False}],
        [], False, {"clustering": {"unknown_entity": {"promote_min_hits": 9,
                                                      "promote_min_sources": 4}}})
    acase("字典補漏：probe 的當班區塊也讀 gate.yaml 的門檻"
          "（只測判準那一支的話，probe 裡再硬寫一次 3 / 2 不會被抓到）",
          "跨 ≥4 來源、≥9 次" in _dg_report.read_text("utf-8"), True)

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

# ─────────────── 死人開關的 exit code（規格 references/health-alarms.md）───────────────
#
# 上面那一條用 `inspect.getsource(_mm.main)` 比對原始碼字串。字串比對測得到
# 「有人寫了這一行」，測不到「這一行真的會讓 CI 紅」。2026-07-26 實測：把
# `main()` 結尾的 `return rc` 改成 `return 0`，整份 selftest 222/222 全過。
#
# CI 那一步是 `python scripts/pulse-monitor.py … > /dev/null`——**沒有人在讀那些
# 字**，整條鏈紅不紅只取決於 `sys.exit(main())` 交出去的數字。三個旗標的計算邏輯
# 都有測試，把計算結果轉成 exit code 的那一步一條都沒有。
#
# 所以下面每一條都走**真的子行程**：在同一個行程裡呼叫 main() 拿回傳值，量到的是
# main() 的 return，不是 CI 會看到的 exit code——`sys.exit(main())` 被改掉照樣全綠。
import subprocess as _subprocess  # noqa: E402
from datetime import datetime as _dtmod  # noqa: E402
from datetime import timedelta as _timedelta  # noqa: E402
from datetime import timezone as _tzmod  # noqa: E402

# main() 自己就是這樣算今天的，fixture 只能跟著它走（不能凍結子行程的時鐘）。
_MTODAY = _dtmod.now(_tzmod.utc).date()


def _mday(n):
    """n 天前的日期字串（n 可以是負的＝未來，用來造時鐘壞掉的語料目錄）。"""
    return (_MTODAY - _timedelta(days=n)).isoformat()


_MSEEN = [{"title": "OpenAI ships a thing", "summary": "", "entity_hits": ["openai"]}]
_MUNSEEN = [{"title": "unrelated", "summary": "", "entity_hits": []}]
_MWATCH = [{"entity_id": "openai", "label": "OpenAI"}]
_MSRC = [{"id": "s-oa", "owner": "OpenAI", "lifecycle": "active", "track": "t"}]


def _mvault(corpus=(0,), rows=None, watch=(), sources=(), events=(),
            stale_after=2, max_silent=2, first_fetch=None):
    """組一個 `pulse-monitor.py` 真的跑得動的 vault，回傳路徑。

    corpus:      幾天前有語料（0＝今天；負數＝未來日期的目錄）。() ＝一天都沒有。
    events:      [(進庫幾天前 or None, 是否未潤稿)]，一律 status: review。
    first_fetch: {sid: 幾天前第一次抓到} → `_probe/state.json`（觀察期的起算點）。

    每個有語料的日子同時寫一份 `_probe/<day>/report.md`——那是「這班跑過了」的
    判準，跟「這班抓到東西」是兩件事，健康頁兩個都要。
    """
    v = Path(tempfile.mkdtemp())
    (v / "Events").mkdir()
    (v / "_config").mkdir()
    (v / "_dashboards").mkdir()
    (v / "_probe").mkdir()
    for n in corpus:
        d = v / "_corpus" / _mday(n)
        d.mkdir(parents=True)
        (d / "src-x.jsonl").write_text(
            "".join(_json.dumps(r, ensure_ascii=False) + "\n"
                    for r in (rows if rows is not None else _MUNSEEN)), "utf-8")
        p = v / "_probe" / _mday(n)
        p.mkdir(parents=True, exist_ok=True)
        (p / "report.md").write_text("# run\n", "utf-8")
    (v / "_config" / "sources.yaml").write_text(_yaml.safe_dump(
        {"official_sources": list(sources),
         "coverage_watch": {"window_days": 30, "max_silent_days": max_silent,
                            "must_watch": list(watch)}}, allow_unicode=True), "utf-8")
    (v / "_config" / "entities.yaml").write_text(_yaml.safe_dump(
        {"companies": [{"id": "openai", "canonical": "OpenAI", "aliases": []}]},
        allow_unicode=True), "utf-8")
    (v / "_config" / "gate.yaml").write_text(_yaml.safe_dump(
        {"monitor": {"stale_after_days": stale_after}}), "utf-8")
    if first_fetch:
        (v / "_probe" / "state.json").write_text(_json.dumps(
            {k: {"first_fetch_at": _mday(n) + "T00:00:00+00:00"}
             for k, n in first_fetch.items()}), "utf-8")
    for i, (ing, unenriched) in enumerate(events):
        ingline = (f"ingested_at: '{_mday(ing)}T00:00:00+00:00'\n"
                   if ing is not None else "")
        (v / "Events" / f"evt-{i}.md").write_text(_EVT_FM.format(
            i=f"evt-{i}", d=_mday(0), h=_mday(0), ing=ingline,
            body="待編輯：一句話" if unenriched else "這則已經潤過稿了。"), "utf-8")
    return v


def _mrc(vault, *argv):
    """子行程跑 pulse-monitor.py → (returncode, stderr)。"""
    p = _subprocess.run(
        [sys.executable, os.path.join(_HERE, "pulse-monitor.py"), *argv],
        capture_output=True, text=True, env=dict(os.environ, VAULT_DIR=str(vault)))
    return p.returncode, p.stderr


_ALL_FLAGS = ("--alert-stale", "--alert-coverage",
              "--alert-unenriched-days", "2", "--alert-days", "2")

# 乾淨的 vault：今天有語料、必盯實體今天被看見、佇列是空的。四個旗標全開要回 0。
# 這條釘的是反方向——只釘「該叫的會叫」的話，把 rc 寫死成 1 也會全過，
# 而一個天天紅的 CI 跟一個永遠綠的 CI 一樣沒有資訊。
_mv_ok = _mvault(rows=_MSEEN, watch=_MWATCH, sources=_MSRC,
                 first_fetch={"s-oa": 10})
acase("死人開關 exit code：一切正常時四個旗標全開要 exit 0"
      "（只釘「該叫的會叫」的話，rc 寫死成 1 也會全過）",
      _mrc(_mv_ok, *_ALL_FLAGS)[0], 0)

# --alert-stale：10 天沒抓到任何東西。
_mv_stale = _mvault(corpus=(10,), rows=_MSEEN, watch=_MWATCH, sources=_MSRC,
                    first_fetch={"s-oa": 10})
_rc_stale, _err_stale = _mrc(_mv_stale, "--alert-stale")
acase("死人開關 exit code：10 天沒抓到東西 → --alert-stale exit 1"
      "（CI 那一步是 `> /dev/null`，訊息沒人讀，只有這個數字算數）",
      [_rc_stale, "[alert]" in _err_stale], [1, True])

acase("死人開關 exit code：同一個壞掉的 vault，沒開旗標就不准叫"
      "（旗標要真的是開關，不是裝飾）", _mrc(_mv_stale)[0], 0)

# 未來日期的語料目錄：lag 是負數。`-3 >= 2` 為假 → 舊碼綠燈，而且時間往前走
# 只會更綠，這個洞不會自癒（health-alarms.md 第 3 條）。
_rc_skew, _err_skew = _mrc(_mvault(corpus=(-3,), rows=_MSEEN, watch=_MWATCH,
                                   sources=_MSRC, first_fetch={"s-oa": 10}),
                           "--alert-stale")
acase("死人開關 exit code：未來日期的語料目錄 → exit 1，且訊息指向「日期壞了」"
      "而不是「來源死了」（成因不同，共用訊息會讓人往錯方向找一整晚）",
      [_rc_skew, "未來日期" in _err_skew], [1, True])

# --alert-coverage 的兩種成因分開釘：結構破洞 vs 有來源卻沉默。
acase("死人開關 exit code：必盯實體沒有任何來源在看 → --alert-coverage exit 1"
      "（2026-07-24 漏抓 Opus 5 就是這一格）",
      _mrc(_mvault(rows=_MSEEN, watch=_MWATCH, sources=()),
           "--alert-coverage")[0], 1)

# 語料橫跨 11 天、來源也被觀察了 11 天，都超過 max_silent_days=2，
# 所以新舊兩種護欄（history_days / observed_days）下都該判 silent。
_mv_silent = _mvault(corpus=(10, 0), rows=_MUNSEEN, watch=_MWATCH,
                     sources=_MSRC, first_fetch={"s-oa": 10})
_rc_silent, _err_silent = _mrc(_mv_silent, "--alert-coverage")
acase("死人開關 exit code：有來源卻長期沒看見這家 → --alert-coverage exit 1",
      [_rc_silent, "沉默" in _err_silent], [1, True])

# pending＝設定檔白紙黑字承認「這家還沒補來源」。天天紅的燈等於沒有燈，
# 所以 --alert-coverage 不叫；要把待辦逼到零時另外開 --alert-no-source。
_mv_pending = _mvault(rows=_MSEEN,
                      watch=[{"entity_id": "openai", "label": "OpenAI",
                              "pending": True}], sources=())
acase("死人開關 exit code：pending 的結構缺口不觸 --alert-coverage，"
      "但 --alert-no-source 要抓得到（兩個旗標的界線在 exit code 上分得開）",
      [_mrc(_mv_pending, "--alert-coverage")[0],
       _mrc(_mv_pending, "--alert-no-source")[0]], [0, 1])

# --alert-unenriched-days 的兩個觸發條件，各走一次真的 exit code。
_mv_unenr = _mvault(rows=_MSEEN, watch=_MWATCH, sources=_MSRC,
                    first_fetch={"s-oa": 10}, events=[(5, True)])
acase("死人開關 exit code：未潤稿放了 5 天、門檻 2 天 → exit 1",
      _mrc(_mv_unenr, "--alert-unenriched-days", "2")[0], 1)

acase("死人開關 exit code：未潤稿放了 5 天、門檻 9 天 → exit 0"
      "（門檻的方向也要釘，只釘一邊的話 >= 改成 <= 只有一半會紅）",
      _mrc(_mv_unenr, "--alert-unenriched-days", "9")[0], 0)

_mv_undated = _mvault(rows=_MSEEN, watch=_MWATCH, sources=_MSRC,
                      first_fetch={"s-oa": 10}, events=[(None, True)])
_rc_und, _err_und = _mrc(_mv_undated, "--alert-unenriched-days", "9")
acase("死人開關 exit code：未潤稿又缺 ingested_at → 就算門檻是 9 天也要 exit 1"
      "（量不到不等於放了 0 天，紅線 8——這是上面那條算式釘子的端到端版本）",
      [_rc_und, "量不到" in _err_und], [1, True])

# --alert-days：卡在 review 的天數。
_mv_stuck = _mvault(rows=_MSEEN, watch=_MWATCH, sources=_MSRC,
                    first_fetch={"s-oa": 10}, events=[(5, False)])
acase("死人開關 exit code：卡在 review 5 天、門檻 2 天 → exit 1；門檻 9 天 → exit 0",
      [_mrc(_mv_stuck, "--alert-days", "2")[0],
       _mrc(_mv_stuck, "--alert-days", "9")[0]], [1, 0])

# 輸出模式不准吞掉 exit code：這兩條路徑在 main() 裡都有自己的 return 點可以寫歪。
acase("死人開關 exit code：--json 一樣要回非零（輸出模式不准吞掉警報）",
      _mrc(_mv_stale, "--json", "--alert-stale")[0], 1)

_rc_wh, _ = _mrc(_mv_stale, "--write-health", "--alert-stale")
acase("死人開關 exit code：--write-health 寫完檔照樣要回非零，且檔真的寫出來了"
      "（看板自己就是死人開關，寫檔那條路徑不能順便把 rc 吃掉）",
      [_rc_wh, (_mv_stale / "_dashboards" / "health.md").exists()], [1, True])

# ingested_at 必須黏住：event_markdown() 會整份重寫 frontmatter，沒被明確帶過去的
# 欄位會被抹掉——fix/backfill-flag-erased-by-second-run 修的就是這個坑。
_cs = importlib.util.spec_from_file_location(
    "pulse_cluster", os.path.join(_HERE, "pulse-cluster.py"))
_cm = importlib.util.module_from_spec(_cs)
_cs.loader.exec_module(_cm)

_e = _cm.Event("evt-x", "x", "T", "2026-07-22T00:00:00+00:00")
_e.ingested_at = "2026-07-26T06:41:46+00:00"
_e.scores = {"tier_evidence": 1, "independent_sources": 1, "primary_evidence": 1,
             "suspected_reposts": 0,
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

# 黏性：event_markdown() 會整份重寫 frontmatter，沒被明確帶過去的欄位會被抹掉。
# 這一條以前是比對原始碼字串（`'ev.ingested_at = fm.get("ingested_at")' in ...`），
# 字串比對測得到「有人寫了這一行」，測不到「重寫一輪之後值還在」——而那正是
# fix/backfill-flag-erased-by-second-run 真正修的東西。改成跑第二輪。
#
# 第二輪的訊號**必須是新的 url**：同一筆訊號再跑一次會被 add_evidence 去重、
# Event 不 dirty、檔案根本不會被重寫，那樣這條就是在斷言一個恆真的條件
# ——一顆永遠綠的燈。所以下面連「真的被重寫了」也一起釘。
(_cvault / "_probe" / "2026-07-26" / "signals-scored.jsonl").write_text(
    "".join(_json.dumps({
        "source_id": "src-openai-blog", "effective_role": "primary",
        "title": "OpenAI announces a thing that does not exist",
        "url": u, "published": "2026-07-22T00:00:00+00:00",
        "first_observed_at": "2026-07-28T09:00:00+00:00", "total": 90,
        "entity_hits": ["openai"], "facet": "product", "fingerprint": "openai|thing",
    }) + "\n" for u in ("https://example.invalid/a", "https://example.invalid/b")),
    "utf-8")
_argv, _env = sys.argv[:], os.environ.get("VAULT_DIR")
sys.argv = ["pulse-cluster.py"]
os.environ["VAULT_DIR"] = str(_cvault)
try:
    _cm.main()
finally:
    sys.argv = _argv
    if _env is not None:
        os.environ["VAULT_DIR"] = _env
_txt2 = _made[0].read_text("utf-8") if _made else ""
acase("pulse-cluster 跑第二輪：整份重寫 frontmatter 之後 ingested_at 還在"
      "（沒讀回物件的話會被寫成 null，佇列年紀從此量不到）",
      ["ingested_at: '2026-07-26T06:41:46+00:00'" in _txt2,
       "ingested_at: null" in _txt2], [True, False])

# ── 證據記錄要留下判斷用的欄位（references/evidence-tiers.md）──
# 第二輪走的正是「從磁碟讀回來、再重寫一次」那條路，所以這幾條釘的是真的
# round-trip，不是 event_markdown() 單獨產出的字串。
_fm2 = _yaml.safe_load(_txt2.split("---")[1])
_evs2 = _fm2.get("evidence") or []
acase("證據記錄：欄位白名單與順序固定"
      "（順序每跑一次換一次的話，git diff 上每則 Event 都像被改過）",
      [list(e) for e in _evs2],
      [["source_id", "url", "title", "relevance", "published",
        "suspected_repost"]] * len(_evs2))
acase("證據記錄：跨日讀回來之後 title 還是標題，不是網址"
      "（舊版 reload 填的是 e.get(\"url\")：拿它去比實體重疊，比出來的相似度是假的）",
      sorted({e.get("title") for e in _evs2}),
      ["OpenAI announces a thing that does not exist"])
acase("證據記錄：published 也要活過 round-trip（轉載鏈要問「差幾小時」）",
      sorted({e.get("published") for e in _evs2}), ["2026-07-22T00:00:00+00:00"])
acase("證據記錄：body 的證據清單不把網址印成標題",
      "（標題未留存）" in _txt2, False)

# 舊格式（2026-07-27 之前寫下的 Event）沒有這兩個欄位。缺就是缺——
# 補一個看起來像值的東西，比空著更難發現。
_old_fmt = _cm.evidence_from_frontmatter(
    [{"source_id": "s1", "url": "https://x.test/a", "relevance": 88}])
acase("證據記錄：舊格式缺 title → 填 None，不拿 url 頂替（紅線 8）",
      [_old_fmt[0]["title"], _old_fmt[0]["published"], _old_fmt[0]["relevance"]],
      [None, None, 88])
acase("證據記錄：title 缺席那一行印「標題未留存」，不把網址印成標題",
      _cm.evidence_line(_old_fmt[0]),
      "- [[Sources/s1|s1]] — （標題未留存）https://x.test/a")
acase("證據記錄：title 剛好等於 url 也算沒有標題"
      "（舊檔重寫過一輪之後，磁碟上真的會有 title == url 的紀錄）",
      _cm.evidence_line({"source_id": "s1", "url": "https://x.test/a",
                         "title": "https://x.test/a"}),
      "- [[Sources/s1|s1]] — （標題未留存）https://x.test/a")
acase("證據記錄：有標題就正常印（反方向，確認上兩條不是恆真）",
      _cm.evidence_line({"source_id": "s1", "url": "https://x.test/a",
                         "title": "真的標題"}),
      "- [[Sources/s1|s1]] — 真的標題（https://x.test/a）")

# ── 轉載鏈：一篇改寫不是第二個聲音（references/evidence-tiers.md）──
# 這條規則今天不會被任何真語料走到（沒有中文來源），所以它只能靠測試證明自己
# 是對的。兩個方向都釘：該判的判、不該判的不判。
from lib import cluster as _cl, entities as _ent  # noqa: E402
from datetime import timezone as _tz  # noqa: E402
_ENT_TABLE = _ent.build_matcher(_yaml.safe_load(
    open(os.path.join(_HERE, "..", "_config", "entities.yaml"), encoding="utf-8")))
_TC = {"enabled": True, "entity_overlap_min": 0.80, "window_hours": 48,
       "excluded_from": ["independent_sources", "heat"]}


def _tcrow(lang, title, hour, tier=2, day=27):
    from datetime import datetime as _dt
    return {"lang": lang, "tier": tier,
            "published": _dt(2026, 7, day, hour, tzinfo=_tz.utc),
            "entities": _ent.entity_ids(title, _ENT_TABLE),
            "fingerprint": _cl.event_fingerprint(title)}


_tc_en = _tcrow("en", "OpenAI launches GPT-5.2 for everyone", 0, tier=1)
_tc_zh = _tcrow("zh", "OpenAI 发布 GPT-5.2，向所有人开放", 3)

acase("轉載鏈：跨語言、同版本、48 小時內、實體集合一樣 → 後發的那條判成轉載"
      "（用 token 交集做不到這件事：中英文標題的 token 交集趨近於零，"
      "這裡走的是命名實體字典）",
      _cl.suspected_reposts([_tc_en, _tc_zh], _TC), {1})
acase("轉載鏈：一原文兩改寫 → 兩條都標，只留一條原文",
      _cl.suspected_reposts(
          [_tc_en, _tc_zh, _tcrow("zh", "OpenAI 发布 GPT-5.2 的完整解读", 5)], _TC),
      {1, 2})
acase("轉載鏈：同語言不判（兩家英文媒體各自報導是兩個真的聲音，"
      "判成轉載等於把獨立性做假到反方向）",
      _cl.suspected_reposts(
          [_tc_en, _tcrow("en", "OpenAI ships GPT-5.2 today", 3)], _TC), set())
acase("轉載鏈：超出 window_hours 不判（門檻真的被讀，不是裝飾）",
      _cl.suspected_reposts(
          [_tc_en, _tcrow("zh", "OpenAI 发布 GPT-5.2，向所有人开放", 0, day=31)],
          _TC), set())
acase("轉載鏈：fingerprint 不同直接否決（GPT-5.1 不可能是 GPT-5.2 的翻譯）",
      _cl.suspected_reposts([_tc_en, _tcrow("zh", "OpenAI 发布 GPT-5.1", 3)], _TC),
      set())
acase("轉載鏈：實體集合不重疊不判",
      _cl.suspected_reposts([_tc_en, _tcrow("zh", "英伟达发布新一代 GPU", 3)], _TC),
      set())
acase("轉載鏈：entity_overlap_min 真的被讀（門檻拉到 1.01 就沒有任何一對過得了）",
      _cl.suspected_reposts([_tc_en, _tc_zh], {**_TC, "entity_overlap_min": 1.01}),
      set())
acase("轉載鏈：enabled: false 是真的關掉（完全不判、不標記）",
      _cl.suspected_reposts([_tc_en, _tc_zh], {**_TC, "enabled": False}), set())
acase("轉載鏈：設定讀不到時不判——設定檔壞掉不可以讓一條規則反而更積極扣分",
      [_cl.suspected_reposts([_tc_en, _tc_zh], {}),
       _cl.suspected_reposts([_tc_en, _tc_zh], None)], [set(), set()])
acase("轉載鏈：缺 published 不判（證明不了在窗內，就不能宣稱在窗內）",
      _cl.suspected_reposts([_tc_en, {**_tc_zh, "published": None}], _TC), set())
acase("轉載鏈：缺 language 不判（舊來源沒填 language 時，維持原本的獨立性算法）",
      _cl.suspected_reposts([_tc_en, {**_tc_zh, "lang": None}], _TC), set())
acase("轉載鏈：標題實體集合是空的不判"
      "（字典沒收到的公司，不可以因為「兩邊都是空集合」就算高度重疊）",
      _cl.suspected_reposts(
          [{**_tc_en, "entities": frozenset()}, {**_tc_zh, "entities": frozenset()}],
          _TC), set())
acase("轉載鏈：同時間發布時留 tier 小的那條（挑原文三段都確定性，沒有任意 tie-break）",
      _cl.suspected_reposts(
          [_tcrow("zh", "OpenAI 发布 GPT-5.2，向所有人开放", 0, tier=2),
           _tcrow("en", "OpenAI launches GPT-5.2 for everyone", 0, tier=1)], _TC),
      {0})

# 走 rescore 那一端：判得出來還要真的扣得到分。
_TCSRC = {
    "src-en": {"tier": 1, "language": "en", "media_group": "openai",
               "role": "primary"},
    "src-zh": {"tier": 2, "language": "zh", "media_group": "zh-media"},
}


def _tc_event():
    e = _cm.Event("evt-tc", "tc", "OpenAI launches GPT-5.2 for everyone",
                  "2026-07-27T00:00:00+00:00")
    e.add_evidence("src-en", "https://a.test/en",
                   "OpenAI launches GPT-5.2 for everyone", 100,
                   "2026-07-27T00:00:00+00:00")
    e.add_evidence("src-zh", "https://b.test/zh",
                   "OpenAI 发布 GPT-5.2，向所有人开放", 40,
                   "2026-07-27T03:00:00+00:00")
    return e


_tc_ev = _tc_event()
_cm.rescore(_tc_ev, _TCSRC, None, _TC, _ENT_TABLE)
acase("轉載鏈：走 rescore 之後，改寫那條不計入 independent_sources"
      "（判得出來還要真的扣得到分——中間漏接一段，規則就只是一個註解）",
      [_tc_ev.scores["independent_sources"], _tc_ev.scores["suspected_reposts"],
       [e["suspected_repost"] for e in _tc_ev.evidence]],
      [1, 0 + 1, [False, True]])
acase("轉載鏈：authority 與 primary_evidence 照算"
      "（excluded_from 沒有列它們；翻譯的權威性由它自己的 tier 表達）",
      _tc_ev.scores["primary_evidence"], 1)

_tc_ev2 = _tc_event()
_cm.rescore(_tc_ev2, _TCSRC, None, {**_TC, "enabled": False}, _ENT_TABLE)
acase("轉載鏈：關掉之後獨立性回到 2 （反方向，確認上面那條不是恆為 1）",
      [_tc_ev2.scores["independent_sources"], _tc_ev2.scores["suspected_reposts"]],
      [2, 0])

_tc_ev3 = _tc_event()
_cm.rescore(_tc_ev3, _TCSRC, None, {**_TC, "excluded_from": ["heat"]}, _ENT_TABLE)
acase("轉載鏈：excluded_from 真的被讀——沒列 independent_sources 就照樣算 2，"
      "但標記仍在（一個改了沒效果的清單就是假旋鈕）",
      [_tc_ev3.scores["independent_sources"],
       [e["suspected_repost"] for e in _tc_ev3.evidence]],
      [2, [False, True]])

acase("pulse-cluster 跑第二輪：這一輪真的重寫了那個檔"
      "（沒重寫的話上一條在斷言一個恆真的條件——測試自己變成一顆永遠綠的燈）",
      [_txt2 != _txt, "example.invalid/b" in _txt, "example.invalid/b" in _txt2],
      [True, False, True])

acase("pulse-cluster：第二輪不拿新訊號的 first_observed_at 蓋掉舊的 ingested_at"
      "（進庫時刻是「我們第一次看到」，不是「最後一次看到」）",
      "2026-07-28" in _txt2, False)

acase("references/event-timestamps.md 存在（紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "event-timestamps.md")), True)

# ── 原子寫入：規格 references/atomic-writes.md ───────────────────────────────
# 這一區釘的不是「檔案不會壞」，是「壞掉的檔案不會被當成好的讀回去」。
# 實測過的最壞情況：y.dump 寫 sources.yaml 到第 0.012 秒被 SIGKILL，留下 17,777
# bytes 的**合法 YAML**，四個 *_sources: 分節整段不見，safe_load 不報錯，
# continue-on-error 讓 job 照樣 exit 0，git add -A 把它 commit 上去。
import shutil as _shutil_aw  # noqa: E402
import tempfile as _tf_aw  # noqa: E402

sys.path.insert(0, _HERE)
from lib.atomicwrite import atomic_write_text, atomic_write_with  # noqa: E402

_awdir = _tf_aw.mkdtemp(prefix="aw-")
_awp = os.path.join(_awdir, "sources.yaml")
with open(_awp, "w", encoding="utf-8") as _f:
    _f.write("official_sources:\n  - id: src-a\n")
_orig_aw = open(_awp, encoding="utf-8").read()


def _half_then_die(fh):
    fh.write("official_sources:\n")   # 半份：合法 YAML，但來源全沒了
    raise RuntimeError("SIGKILL 的替身")


try:
    atomic_write_with(_awp, _half_then_die)
except RuntimeError:
    pass
_after_aw = open(_awp, encoding="utf-8").read()
_leftovers = [n for n in os.listdir(_awdir) if n != "sources.yaml"]

acase("atomicwrite：寫到一半炸掉 → 目標檔一個位元組都沒動"
      "（舊寫法會留下一份讀得起來、但四個分節都不見的合法 YAML）",
      [_after_aw == _orig_aw, "official_sources:\n  - id: src-a\n" == _after_aw],
      [True, True])
acase("atomicwrite：失敗路徑不留暫存檔（留著的話 git add -A 會把半份 commit 上去）",
      _leftovers, [])

atomic_write_text(_awp, "official_sources:\n  - id: src-b\n")
acase("atomicwrite：正常路徑真的寫進去了",
      open(_awp, encoding="utf-8").read(), "official_sources:\n  - id: src-b\n")

_awnest = os.path.join(_awdir, "a", "b", "c.json")
atomic_write_text(_awnest, "{}")
acase("atomicwrite：目標目錄不存在時會自己建（取代了呼叫端原本的 mkdir）",
      [os.path.isfile(_awnest), open(_awnest, encoding="utf-8").read()], [True, "{}"])

# 暫存檔必須跟目標同目錄：os.replace() 只有在同一個檔案系統上才是原子的。
# 丟去 /tmp 再搬過來就退化成「複製＋截斷」，等於這一整層白做。
_seen_dirs = []
_real_replace_aw = os.replace


def _spy_replace(a, b):
    _seen_dirs.append((os.path.dirname(str(a)), os.path.dirname(str(b))))
    return _real_replace_aw(a, b)


os.replace = _spy_replace
try:
    atomic_write_text(_awp, "official_sources: []\n")
finally:
    os.replace = _real_replace_aw
acase("atomicwrite：暫存檔與目標同目錄（跨檔案系統的 rename 不是原子的）",
      [d[0] == d[1] for d in _seen_dirs], [True])
_shutil_aw.rmtree(_awdir, ignore_errors=True)

# 回歸釘：這六個檔是「下一班會讀回來」的狀態檔，任何一個退回直接寫都要紅。
# 判準寫在 references/atomic-writes.md：不是重不重要，是壞掉之後會不會被當成
# 事實讀回去。dist/ 與 _probe/<day>/report.md 刻意不在此列。
_aw_pins = [
    ("pulse-source-health.py", "atomic_write_with(spath", "_config/sources.yaml"),
    ("pulse-source-health.py", "atomic_write_text(hpath", "_probe/source-health.json"),
    ("pulse-robots-recheck.py", "atomic_write_with(path", "_config/sources.yaml"),
    ("pulse-probe.py", "atomic_write_text(state_path", "_probe/state.json"),
    ("pulse-probe.py", "atomic_write_text(seen_path", "_probe/seen.json"),
    ("pulse-probe.py", "atomic_write_text(hb,", "heartbeat.json"),
    ("pulse-monitor.py", "atomic_write_text(p, body)", "_dashboards/health.md"),
]
for _fn, _needle, _target in _aw_pins:
    _src_aw = open(os.path.join(_HERE, _fn), encoding="utf-8").read()
    acase(f"{_fn} 寫 {_target} 走原子寫（退回直接寫 = 半份狀態檔被 commit）",
          _needle in _src_aw, True)

acase(".gitignore 蓋得住原子寫的暫存檔（runner 被砍時它會留在原地）",
      ".*.tmp.*" in open(os.path.join(_HERE, "..", ".gitignore"), encoding="utf-8").read(),
      True)

acase("references/atomic-writes.md 存在（紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "atomic-writes.md")), True)

# ── 變異盤點清單的鮮度：規格 references/mutation-inventory.md ────────────────
# 這一區**不跑變異**。跑一輪要幾十次 selftest，掛在每次 push 上太慢——那是
# scripts/mutate.py 與 .github/workflows/mutation.yml 的事。這裡只釘一件
# 0.5 秒內查得完、而且錯了最貴的事：**清單自己過期了**。
# 針腳在目標檔案裡不是剛好出現一次，注入就會改到隔壁那一處，於是那一條會
# 假裝成「存活」——又一顆永遠綠的燈（規格：坑一）。
_mut = _yaml.safe_load(
    open(os.path.join(_HERE, "mutations.yaml"), encoding="utf-8"))["mutations"]
_MUT_REQ = ("id", "file", "find", "replace", "why", "survives")
acase("mutations.yaml 讀得進來，且 id 不重複",
      [len(_mut) > 0, len({m["id"] for m in _mut}) == len(_mut)], [True, True])
acase("mutations.yaml 每一條的必填欄位都在",
      sorted(m.get("id", "?") for m in _mut
             if any(k not in m for k in _MUT_REQ)), [])

# mutate.py 跑到某一條時，那一條的針腳**正被它自己換掉**，這裡當然數到 0。
# 不排除的話，這條會在每一次注入都紅——於是每一條變異都「被殺」，kill 訊號
# 變成常數，整個變異盤點就只是在量「這條檢查還在不在」。第一次跑就踩到了：
# M01/M02/M03/M11 四條已知的存活者全部被誤判成 killed。
# MUTATE_IN_FLIGHT 只由 scripts/mutate.py 在注入期間設，一次一個 id；CI 不設。
_inflight = os.environ.get("MUTATE_IN_FLIGHT", "").strip()
_mut_stale = []
for _m in _mut:
    if _m["id"] == _inflight:
        continue
    _mp = os.path.join(_HERE, _m["file"])
    _mn = open(_mp, encoding="utf-8").read().count(_m["find"]) if os.path.isfile(_mp) else -1
    if _mn != 1:
        _mut_stale.append(f"{_m['id']}:{_m['file']}×{_mn}")
acase("mutations.yaml 每個 find 在目標檔案裡剛好出現一次"
      "（不是 1 就會改到隔壁那一處，然後假裝成「存活」）"
      + (f"｜注入中，略過 {_inflight}" if _inflight else ""), _mut_stale, [])
acase("MUTATE_IN_FLIGHT 只認得清單裡的 id（打錯字就等於憑空關掉一條檢查）",
      not _inflight or _inflight in {m["id"] for m in _mut}, True)

acase("mutations.yaml 記 survives: true 的都寫了 why"
      "（已知的缺口掛著是誠實，沒有理由的存活是掩蓋）",
      sorted(m["id"] for m in _mut
             if m.get("survives") and not str(m.get("why") or "").strip()), [])

acase("references/mutation-inventory.md 存在（紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references", "mutation-inventory.md")),
      True)

# ── 變異盤點第一輪抓到的五個沒人守的地方 ────────────────────────────────────
# 2026-07-26，mutate.py 第一次跑就把碼改壞，而 224 條測試一條都沒紅。以下五條
# 不是為了讓數字好看，是把那五個洞補起來——掛著不補就是紅線 8 講的那件事。
# 對應 mutations.yaml 的 M09 / M14 / M15 / M19 / M20。

# M14 / M15：pulse-gate.py 是**唯一**決定發不發的地方（紅線 1：判斷走規則不走 LLM），
# 而在此之前 selftest 從來沒有 import 過它。把 `blockers.append(...)` 那兩行刪掉，
# 沒有一條測試會紅——門禁形同虛設而看板一片綠。
_gs = importlib.util.spec_from_file_location(
    "pulse_gate", os.path.join(_HERE, "pulse-gate.py"))
_gm = importlib.util.module_from_spec(_gs)
_gs.loader.exec_module(_gm)

_GATE_T = {"readiness": {"min_confidence": 60, "thin_fact_min_chars": 20,
                         "heat_threshold": 70, "heat_min_independent_sources": 2,
                         "heat_min_platform_breadth": 2}}
_GBODY = ("## 事實\nOpenAI 在官方部落格宣布了一項新的模型定價方案，生效日為下月一日。\n\n"
          "## 證據\n- 官方部落格\n\n## 脈絡\n這是今年第三次調整。\n")


def _gfm(**kw):
    # 基準線的 heat 是 None：2026-07-26 起這才是「沒量到傳播訊號」的正常長相。
    # 不要為了方便把它改回一個數字——那會讓下面 unmeasured_heat 的基準線失效。
    d = {"summary": "OpenAI 宣布新的模型定價方案，下月一日生效。", "category": "product",
         "company": "OpenAI", "keywords": ["openai"], "track": "模型能力",
         "evidence": [{"source_id": "src-openai-blog"}], "primary_evidence": 1,
         "confidence": 70, "heat": None,
         "score_factors": {"propagationSignals": 0}, "independent_sources": 2}
    d.update(kw)
    return d


acase("pulse-gate：一則各項都合格的 Event 沒有任何 blocker"
      "（基準線；沒有這條，下面幾條可能是被別的 blocker 擋住而不是被守住）",
      _gm.evaluate(_gfm(), _GBODY, _GATE_T)[0], [])
acase("pulse-gate：沒有一手證據 → missing_primary_evidence（紅線 2 的執法點）",
      _gm.evaluate(_gfm(primary_evidence=0), _GBODY, _GATE_T)[0],
      ["missing_primary_evidence"])
# unmeasured_heat：有 heat 數字但一項傳播訊號都沒量到 → 擋。這是 scoring.py 回 None
# 的執法點，守的是「手改 frontmatter / 遷移腳本寫壞 / 有人把無條件計算加回去」這三種
# 走回頭路的方式。規格見 references/readiness-gate.md。
acase("pulse-gate：heat 有數字但 propagationSignals=0 → unmeasured_heat"
      "（紅線 8：量不到就寫量不到，不是編一個低分出來）",
      _gm.evaluate(_gfm(heat=12), _GBODY, _GATE_T)[0], ["unmeasured_heat"])
acase("pulse-gate：heat 是 None 時不擋（反方向；缺席是合法狀態，不是錯誤狀態）",
      _gm.evaluate(_gfm(heat=None), _GBODY, _GATE_T)[0], [])
acase("pulse-gate：heat 有數字且真的量到傳播訊號 → 不擋 unmeasured_heat"
      "（第二個反方向：擋的是「沒證據卻有數字」，不是「有數字」）",
      _gm.evaluate(_gfm(heat=30, score_factors={"propagationSignals": 2,
                                                "independentSources": 2,
                                                "platformBreadth": 2}),
                   _GBODY, _GATE_T)[0], [])
acase("pulse-gate：heat 過門檻但獨立來源/平台廣度撐不住 → unsupported_heat"
      "（紅線 4：禁止把手工分數包裝成已測量熱度。這條現在要靠社群線接上才走得到，"
      "但語意正確且正反兩面都釘住，那天它會是活的碼）",
      _gm.evaluate(_gfm(heat=75, score_factors={"propagationSignals": 1,
                                                "independentSources": 1,
                                                "platformBreadth": 1}),
                   _GBODY, _GATE_T)[0], ["unsupported_heat"])
acase("pulse-gate：heat 高但證據撐得住就不擋（反方向；只釘一邊的話"
      "「永遠擋」跟「永遠不擋」一樣沒有資訊）",
      _gm.evaluate(_gfm(heat=75, score_factors={"propagationSignals": 3,
                                                "independentSources": 2,
                                                "platformBreadth": 2}),
                   _GBODY, _GATE_T)[0], [])

# 缺席要一路走到前台。heat=None 在後端誠實、在畫面上印成 0 的話，讀的人看到的
# 還是「量過了，很冷」——那是這次要修掉的那個謊，只是換一層出現。
_rs = importlib.util.spec_from_file_location(
    "pulse_render", os.path.join(_HERE, "pulse-render.py"))
_rmod = importlib.util.module_from_spec(_rs)
_rs.loader.exec_module(_rmod)
acase("pulse-render.heat_text：None → 「未量測」，不是 0"
      "（0 會被讀成「量過了，很冷」，比不印更糟）",
      [_rmod.heat_text(None), _rmod.heat_text(0), _rmod.heat_text(42)],
      ["未量測", 0, 42])
# 這條是文字釘（該邏輯寫在 pulse-narrative-prep.py 的 dict 字面值裡，抽不出函式）。
# 守的是紅線 2 與 8：送 0 給敘述層，LLM 就會寫出「熱度低、還沒共振」這種
# 拿沒量過的東西當論據的句子——_config/narratives.yaml 裡曾經有兩句這樣寫成的
# 句子（2026-07-26 已改掉，見 references/narrative-layer.md）。
_np_txt = open(os.path.join(_HERE, "pulse-narrative-prep.py"), encoding="utf-8").read()
acase("pulse-narrative-prep：heat 沒量到時送「未量測」給敘述層，不送 0",
      '"未量測" if fm.get("heat") is None' in _np_txt, True)

# ── 敘述層的量化熱度宣稱（references/narrative-layer.md）─────────────────
# 上面那條守的是**入口**：以後不要再寫出這種句子。它擋不住已經寫出來的那兩句，
# 而那兩句待的是 lenses——夜間鏈永遠不會重寫的那一格。堵住上游只擋得住新的謊。
from lib import narrative_guard as _ng  # noqa: E402

acase("narrative_guard：把沒量到的熱度講成數字 → 命中",
      [bool(_ng.find_heat_claims("四則皆單源、heat 偏低（8–14），還沒跨來源共振。")),
       bool(_ng.find_heat_claims("目前只有官方發布、無採用數字，heat 8–10 偏低。")),
       bool(_ng.find_heat_claims("熱度 70 以上才算共振。"))],
      [True, True, True])
# 反方向。一條會誤傷誠實句子的檢查會被改寫繞過去，繞過去之後它就是一顆永遠綠的燈。
acase("narrative_guard：講「量不到」而且旁邊剛好有數字 → 不命中（否定詞豁免）",
      [_ng.find_heat_claims("傳播熱度量不到（社群訊號沒接線），12 則全部單源。"),
       _ng.find_heat_claims("所有事件的 heat 都是未量測，12 則單源。"),
       _ng.find_heat_claims("12 則單源，還沒有第二個獨立聲音。"),
       _ng.find_heat_claims("這批訊號沒有人轉述。")],
      [[], [], [], []])

# 檔案本身要乾淨——包含 thesis 與 lenses。apply 只看得到當班寫入的東西。
_narr_doc = _yaml.safe_load(
    open(os.path.join(_HERE, "..", "_config", "narratives.yaml"), encoding="utf-8"))


def _narr_heat_hits(node, path=""):
    if isinstance(node, dict):
        return [h for k, v in node.items() for h in _narr_heat_hits(v, f"{path}.{k}")]
    if isinstance(node, list):
        return [h for i, v in enumerate(node) for h in _narr_heat_hits(v, f"{path}[{i}]")]
    if isinstance(node, str):
        return [f"{path}: {x}" for x in _ng.find_heat_claims(node)]
    return []


_VAULT_ROOT = Path(os.path.join(_HERE, ".."))
acase("vault 目前沒有任何量到的 heat（這條垮了代表社群線接上了，下一條要跟著改）",
      _ng.vault_has_measured_heat(_VAULT_ROOT), False)
acase("narratives.yaml 全檔（含 thesis / lenses）沒有量化熱度宣稱",
      _narr_heat_hits(_narr_doc), [])

# 反方向：vault 真的量到 heat 之後，這種句子是引用而不是編造，不該再擋。
with _tf2.TemporaryDirectory() as _tdh:
    _hvault = Path(_tdh)
    (_hvault / "Events").mkdir()
    (_hvault / "Events" / "a.md").write_text(
        "---\nid: e1\nheat: null\n---\n本文\n", "utf-8")
    acase("vault_has_measured_heat：heat 全是 null → False",
          _ng.vault_has_measured_heat(_hvault), False)
    (_hvault / "Events" / "b.md").write_text(
        "---\nid: e2\nheat: 74\n---\n本文\n", "utf-8")
    acase("vault_has_measured_heat：有一則量到就 True（反方向，確認上一條不是恆假）",
          _ng.vault_has_measured_heat(_hvault), True)


# 走真的子行程：這條要測的是「那一班紅不紅、磁碟上寫了什麼」，
# 在同一個行程裡呼叫 main() 測到的就不是真正會發生的那條路徑。
def _run_narr_apply(vault, result):
    (vault / "result.json").write_text(_json.dumps(result, ensure_ascii=False), "utf-8")
    p = _subprocess.run(
        [sys.executable, os.path.join(_HERE, "pulse-narrative-apply.py"),
         "--in", str(vault / "result.json")],
        capture_output=True, text=True, env=dict(os.environ, VAULT_DIR=str(vault)))
    doc = _yaml.safe_load((vault / "_config" / "narratives.yaml").read_text("utf-8"))
    return p.returncode, doc["tracks"]


def _narr_vault(td, heat="null"):
    v = Path(td)
    (v / "_config").mkdir(parents=True, exist_ok=True)
    (v / "_probe").mkdir(parents=True, exist_ok=True)
    (v / "Events").mkdir(parents=True, exist_ok=True)
    (v / "Events" / "a.md").write_text(f"---\nid: e1\nheat: {heat}\n---\n本文\n", "utf-8")
    (v / "_config" / "narratives.yaml").write_text(
        "version: 1\nupdated: '2026-07-26'\ntracks:\n"
        "  infra-cost:\n    thesis: 原本的\n    now: 原本的 now\n    next: 原本的 next\n",
        "utf-8")
    return v


with _tf2.TemporaryDirectory() as _td_n1:
    _nv = _narr_vault(_td_n1)
    _rc_n, _tr_n = _run_narr_apply(_nv, {"infra-cost": {
        "now": "這輪 heat 8–10 偏低，還沒共振。",
        "next": "看第二個獨立來源會不會出現。"}})
    acase("narrative-apply：LLM 寫回量化熱度宣稱 → 拒收該欄位、原文不動、"
          "乾淨的那欄照寫、整班回非零",
          [_rc_n, _tr_n["infra-cost"]["now"], _tr_n["infra-cost"]["next"]],
          [1, "原本的 now", "看第二個獨立來源會不會出現。"])

with _tf2.TemporaryDirectory() as _td_n2:
    _nv2 = _narr_vault(_td_n2)
    _rc_n2, _tr_n2 = _run_narr_apply(_nv2, {"infra-cost": {
        "now": "傳播熱度量不到，12 則全部單源。"}})
    acase("narrative-apply：誠實句子照寫、exit 0（反方向，確認上一條不是恆擋）",
          [_rc_n2, _tr_n2["infra-cost"]["now"]],
          [0, "傳播熱度量不到，12 則全部單源。"])

with _tf2.TemporaryDirectory() as _td_n3:
    _nv3 = _narr_vault(_td_n3, heat="74")
    _rc_n3, _tr_n3 = _run_narr_apply(_nv3, {"infra-cost": {
        "now": "這輪 heat 8–10 偏低，還沒共振。"}})
    acase("narrative-apply：vault 真的量到 heat 時不擋（那時它是引用，不是編造）",
          [_rc_n3, _tr_n3["infra-cost"]["now"]],
          [0, "這輪 heat 8–10 偏低，還沒共振。"])

# M09：從來沒抓到過（item_lag is None）必須判紅。改成 `is not None and ...` 的話，
# 一個**完全空的 vault** 會顯示綠燈——死人開關在最該叫的那一天最安靜。
import datetime as _dt_m  # noqa: E402

_hv = Path(tempfile.mkdtemp(prefix="health-"))
acase("pulse-monitor.health()：一次都沒抓到過 → 紅燈，不是綠燈"
      "（量不到不等於沒事，紅線 8）",
      [_mm.health(_hv, _dt_m.date(2026, 7, 26), {}, 2)[_k]
       for _k in ("probe_lag_days", "last_success", "status")],
      [None, None, "red"])
(_hv / "_corpus" / "2026-07-26").mkdir(parents=True)
(_hv / "_corpus" / "2026-07-26" / "a.jsonl").write_text('{"title": "x"}\n', "utf-8")
acase("pulse-monitor.health()：今天有語料 → 綠燈（反方向，確認上一條不是恆紅）",
      _mm.health(_hv, _dt_m.date(2026, 7, 26), {}, 2)["status"], "green")
shutil.rmtree(_hv, ignore_errors=True)

# M19：聚類的 96 小時窗口。拿掉它，兩則標題相近但隔了兩週的新聞會被併成同一則
# 事件——去AI化聚類的地基就是這個窗口，它壞掉不會有任何東西看起來不對。
_C19A = "Nvidia unveils Rubin platform at its annual developer conference"
_C19B = "Nvidia unveils Rubin platform at annual developer conference recap"
_c19 = _dt_m.datetime(2026, 7, 1, tzinfo=_dt_m.timezone.utc)
acase("lib.cluster.belongs_to_event：標題再像，隔 120 小時就不是同一則事件"
      "（沒有 fingerprint 時全靠這個 96 小時窗口）",
      [_cm.cluster.belongs_to_event(
          _C19A, (_c19 + _dt_m.timedelta(hours=_h)).isoformat(),
          _C19B, _c19.isoformat()) for _h in (48, 120)],
      [True, False])

# M20：關鍵詞的順序。`list(title_tokens(t))[:8]` 走的是 set，CPython 每個行程重新
# 隨機化字串雜湊 → 同一個標題每跑一次換一組關鍵詞。理由與實測見 lib/cluster.py。
# 這條比對的是上面那輪真的 main() 產出的 frontmatter，不是原始碼字串。
acase("pulse-cluster 跑完一輪：keywords 照標題原順序、濾過虛詞"
      "（退回 list(set) 的話這裡會變成 7 個亂序的詞）",
      _cm.parse_frontmatter(_txt)[0].get("keywords"),
      ["openai", "thing", "exist"])

print("offline self-test\n" + "-" * 70)
fails = 0
for ok, name, detail, reason in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n         {detail} | {reason}")
    fails += 0 if ok else 1
print("-" * 70)
print(f"{len(results) - fails}/{len(results)} passed")
raise SystemExit(1 if fails else 0)
