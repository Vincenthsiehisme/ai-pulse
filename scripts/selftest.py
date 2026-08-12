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
from lib import sources as _smod  # noqa: E402  詞彙表與 lifecycle 單一真相源

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


from lib import scoring as _scoring  # noqa: E402


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
      (_d_hint.get("index_entries"), _d_hint.get("hint_matched")), (1, 0))
acase("零產出診斷：hints 沒命中時要印出候選的網址"
      "（2026-07-27 首班實測：判定對了、下一步還是查不下去，因為那張的網址沒印。"
      "說得出「你設錯了」卻說不出「那是什麼」的診斷，只把人從「不知道哪裡錯」"
      "推到「知道哪裡錯但不知道要改成什麼」）",
      [_d_hint.get("index_sample"),
       "https://x.test/sitemap-pages.xml" in _pp.zero_yield_reason(_d_hint)[1]],
      [["https://x.test/sitemap-pages.xml"], True])
acase("零產出診斷：候選清單有上限，不把整份 index 倒進報告",
      len(_pp.adapt_sitemap(
          {"url_prefix": "/news/"},
          '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<sitemap><loc>https://x.test/s{i}.xml</loc></sitemap>"
                    for i in range(9))
          + "</sitemapindex>", _d_many := {})[0:0] or _d_many["index_sample"]), 5)

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

_NOTE_B = _dam.MISSING_NOTE["board"]

acase("apply：乾淨的一行過關，並吃掉句尾句號（榜是一行字不是句子）",
      _dam.validate("拿來組 agent 的工具包。", _EN, _NOTE_B)[:2], (_ZH, None))
acase("apply：英文原樣貼回來不算翻譯 → 退件",
      _dam.validate(_EN, _EN, _NOTE_B)[1],
      "沒有任何中文字（英文原樣貼回來不算翻譯）")
acase("apply：空白 → 退件",
      _dam.validate("   ", _EN, _NOTE_B)[1], "空白")
acase(f"apply：超過 {_dam.MAX_LEN} 字 → 退件（版面是一行）",
      _dam.validate("工" * (_dam.MAX_LEN + 1), _EN, _NOTE_B)[1],
      f"超過 {_dam.MAX_LEN} 字（榜是一行字的版面）")
acase("apply：AI 腔套話 → 退件",
      _dam.validate("值得關注的 agent 工具包", _EN, _NOTE_B)[1],
      "含 AI 腔套話：值得關注")
acase("apply：不在當下榜單上的 repo → 退件（榜換過了，別亂寫進去）",
      _dam.validate(_ZH, None, _NOTE_B)[1],
      "不在目前榜單上（榜換過了，下次 prep 會再排進來）")
# voice_clean.clean 回的是 tuple。這條同時測「中國用語有換掉」與「apply 有把
# tuple 拆開」——沒拆的話 zh 會變成一整串 tuple 的字串，長度爆表、CJK 也還在，
# 前四關全部放行，最後是榜上掛一句 "('...', [...])"。這種錯只有測得到才看得到。
_v_cn = _dam.validate("短視頻的推薦引擎工具包", _EN, _NOTE_B)
acase("apply：中國用語走 voice_clean 後洗（跟 enrich 同一支後洗）",
      _v_cn[0], "短影音的推薦引擎工具包")
acase("apply：後洗改了什麼要帶回來（不能只有機器自己知道）",
      [c[1] for c in _v_cn[2]], ["短視頻"])

# --- 英文原文從哪來：這一組要打在 main() 上，不能只打 validate() -----------
# 2026-07-28 實測（乾淨 clone origin/main、沒有 dist/，因為 .gitignore 第 12 行）：
# 3 條完全合格的譯文 3/3 退件、離開碼 0、理由印「不在目前榜單上（榜換過了）」，
# 而榜一次都沒換——是 main() 讀不到榜、用 `else {"repos": []}` 把「我讀不到」
# 代理成「榜上沒有這條」。
#
# 舊測試只打 validate("ghost/repo", _ZH, None)，而 validate() 只拿得到一個 bool，
# 本來就分不出「榜上沒有」跟「讀不到榜」——那條測試永遠不會為了這個 bug 變紅。
# 這是空測試的第三種形狀：**斷言只碰到被改壞那段程式的外圍**。
import contextlib as _c2  # noqa: E402
import json as _js2  # noqa: E402
import tempfile as _tf8  # noqa: E402
from pathlib import Path as _P2  # noqa: E402

_BOARD = {"repos": [{"full_name": "acme/kit", "desc": _EN}]}
_WORK = [{"full_name": "acme/kit", "desc": _EN, "stale_zh": None}]

acase("apply：榜讀得到 → 原文用榜的",
      _dam.english_source(_BOARD, None), ({"acme/kit": _EN}, "board"))
acase("apply：榜讀不到（潤稿端的常態）→ 退回 worklist 的原文，不是把榜當成空的",
      _dam.english_source(None, _WORK), ({"acme/kit": _EN}, "worklist"))
acase("apply：那一班沒抓到榜（measured: false）不算「榜讀得到」——"
      "跟 prep 同一個判準",
      _dam.english_source({"repos": [], "measured": False}, _WORK)[1], "worklist")
acase("apply：兩邊都讀不到 → 回 None，讓呼叫端非零離開（量不到 ≠ 沒東西要翻）",
      _dam.english_source(None, None), (None, "none"))
acase("apply：榜是空的但真的量到了（0 條上榜）仍算榜讀得到",
      _dam.english_source({"repos": []}, _WORK)[1], "board")
acase("apply：全數退件的離開碼跟「今晚沒東西要翻」分得開",
      [_dam.exit_code(3, 0), _dam.exit_code(3, 1), _dam.exit_code(0, 0)], [3, 0, 0])


def _run_apply(vault, result, board=None, worklist=None):
    """在一個真的 vault 上跑一次 main()。→ (離開碼, stdout+stderr)"""
    v = _P2(vault)
    (v / "_probe").mkdir(parents=True, exist_ok=True)
    if board is not None:
        (v / "dist" / "data").mkdir(parents=True, exist_ok=True)
        (v / "dist" / "data" / "github.json").write_text(
            _js2.dumps(board), encoding="utf-8")
    if worklist is not None:
        (v / "_probe" / "github-desc-worklist.json").write_text(
            _js2.dumps(worklist), encoding="utf-8")
    rp = v / "result.json"
    rp.write_text(_js2.dumps(result, ensure_ascii=False), encoding="utf-8")
    buf = io.StringIO()
    old_argv, old_vault = sys.argv, os.environ.get("VAULT_DIR")
    sys.argv, os.environ["VAULT_DIR"] = ["apply", "--in", str(rp)], str(v)
    try:
        with _c2.redirect_stdout(buf), _c2.redirect_stderr(buf):
            code = _dam.main()
    finally:
        sys.argv = old_argv
        if old_vault is None:
            os.environ.pop("VAULT_DIR", None)
        else:
            os.environ["VAULT_DIR"] = old_vault
    return code, buf.getvalue()


with _tf8.TemporaryDirectory() as _av:
    _code, _out = _run_apply(_av, {"acme/kit": _ZH}, board=None, worklist=_WORK)
    acase("apply（實跑）：沒有 dist/ 的乾淨 clone 上，合格譯文要過關——"
          "這正是 2026-07-28 3/3 退件的那一種 vault",
          (_code, "[退件]" in _out), (0, False))
    acase("apply（實跑）：譯文真的寫進 _github/desc-zh.json",
          _gd.load(_P2(_av)).get("acme/kit", {}).get("zh"), _ZH)
    acase("apply（實跑）：雜湊綁的是 worklist 那句英文，所以下一班 attach() 掛得回去",
          _gd.attach([{"full_name": "acme/kit", "desc": _EN}],
                     _gd.load(_P2(_av)))[0]["desc_zh"], _ZH)
    acase("apply（實跑）：榜讀不到就**不生一份假的**——"
          "落一個 {repos: []} 下去，prep 下次會印「今晚沒有東西要翻」",
          (_P2(_av) / "dist" / "data" / "github.json").exists(), False)

with _tf8.TemporaryDirectory() as _av2:
    _code2, _out2 = _run_apply(_av2, {"ghost/repo": _ZH}, board=_BOARD, worklist=_WORK)
    acase("apply（實跑）：榜讀得到而 repo 不在榜上 → 這時候「榜換過了」才是實話",
          (_code2, _dam.MISSING_NOTE["board"] in _out2), (3, True))

with _tf8.TemporaryDirectory() as _av4:
    # 兩句退件訊息不能講同一件事。講同一句的話，讀訊息的人會去查 GitHub 榜單，
    # 而榜單完全沒有問題——2026-07-28 那次就是這樣被指向錯的地方。
    _code4, _out4 = _run_apply(_av4, {"ghost/repo": _ZH}, board=None, worklist=_WORK)
    acase("apply（實跑）：榜讀不到而 repo 也不在 worklist 上 → 退件理由要說榜讀不到，"
          "不能說「榜換過了」（榜沒換，是沒讀到）",
          (_code4, _dam.MISSING_NOTE["worklist"] in _out4,
           _dam.MISSING_NOTE["board"] in _out4), (3, True, False))

with _tf8.TemporaryDirectory() as _av3:
    _code3, _out3 = _run_apply(_av3, {"acme/kit": _ZH}, board=None, worklist=None)
    acase("apply（實跑）：榜與 worklist 都讀不到 → 離開碼 2，不是把每一條靜靜退掉",
          (_code3, "[退件]" in _out3), (2, False))

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
    """在子行程跑 pulse-source-health.py，回傳 (returncode, stdout, **stderr**)。

    刻意走子行程而不是直接呼叫 main()：這幾條要測的正是「跑完之後磁碟上多了什麼」，
    而 main() 讀 os.environ["VAULT_DIR"]、還會 argparse sys.argv——在同一個行程裡
    模擬那兩件事，測到的就不再是真正會發生的那條路徑了。

    ## 為什麼 stderr 要帶回來

    2026-08-11 實測過丟掉它的代價：`--apply` 因為缺 `ruamel.yaml` 回了 exit 2、
    stderr 白紙黑字寫著要裝什麼，而這裡只回 `(rc, stdout)`。於是下一行
    `json.loads(路徑.read_text())` 丟出 `FileNotFoundError`——一個「缺套件」的錯誤
    在畫面上長成「檔案不見了」，排查方向被帶去猜 Python 版本，花掉一整輪。

    子行程已經把原因說得很清楚了，是判準沒有聽。這是這個 repo 反覆在抓的形狀的
    又一種：**拿到了資訊卻把它丟掉**。
    """
    env = dict(os.environ, VAULT_DIR=str(vault))
    p = _subprocess.run([sys.executable,
                         os.path.join(_HERE, "pulse-source-health.py"), *argv],
                        capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, (p.stderr or "")


def _sh_ran(rc, err, what):
    """子行程有沒有跑起來。跑不起來就把 stderr 當成判準的 got 值印出來。

    這一條**不是**在測 pulse-source-health 的行為，是在測「下面那幾條有沒有
    真的跑到」。少了它，一個掛掉的子行程會讓下游的斷言以一個對不上的例外收場，
    而例外不會紅、會 crash——crash 的判準在 mutate.py 眼裡「不算數」。
    """
    acase(f"子行程跑得起來：{what}（跑不起來時把 stderr 印出來，"
          "不要讓下游長成一個對不上的 FileNotFoundError）",
          [rc, err.strip()[:200]], [0, ""])


import subprocess as _subprocess  # noqa: E402

with _tf2.TemporaryDirectory() as _td3:
    # 連續 5 班 503 → 達到 quarantine_after_consecutive，而且來源已經是 degraded。
    _vq = _sh_vault(_td3, [503] * 5)
    # 先驗這條管線本身：拿一個不存在的旗標當探針，argparse 會回非零、
    # 而訊息**只在 stderr**。這一條守的是「判準聽得見子行程」，
    # 不是 source-health 的行為——成功路徑上 stderr 本來就是空的，
    # 只用成功路徑測，把 stderr 丟掉這件事永遠不會紅。
    _rc_probe, _, _err_probe = _run_sh(_vq, "--no-such-flag-exists")
    acase("子行程的 stderr 真的帶得回來（丟掉它的代價實測過：一個「缺 ruamel.yaml」"
          "的錯誤在下游長成 FileNotFoundError，排查方向被帶去猜 Python 版本）",
          [_rc_probe != 0, bool(_err_probe.strip())], [True, True])
    _rc, _out, _err = _run_sh(_vq, "--apply")
    _sh_ran(_rc, _err, "source-health --apply（隔離候選那一組）")
    _snap_p = _vq / "_probe" / "source-health.json"
    # 檔案不在就給空 dict：下面那幾條要**紅**，不要 crash。
    _snap = _json.loads(_snap_p.read_text("utf-8")) if _snap_p.exists() else {}
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
    _rc, _out, _err = _run_sh(_vd, "--json")
    _sh_ran(_rc, _err, "source-health --json（dry run 那一組）")
    acase("dry run：`--json` 跑完，_probe/ 一個新檔案都沒有"
          "（宣稱「只看」的旗標留下改動，咬到的是未來的自己）",
          sorted(p.name for p in (_vd / "_probe").iterdir()), _before)
    acase("dry run：`--json` 的 stdout 真的解得開"
          "（那句「加 --apply 才會寫回」以前無條件印在 JSON 後面）",
          sorted(_json.loads(_out)), ["changes", "prior_source",
                                      "quarantine_candidates", "runs", "sources"])
    _rc2, _out2, _err2 = _run_sh(_vd, )
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
    _rc, _out, _err = _run_sh(_vr, "--apply")
    _sh_ran(_rc, _err, "source-health --apply（吸收態那一組）")
    _snap5_p = _vr / "_probe" / "source-health.json"
    _snap5 = _json.loads(_snap5_p.read_text("utf-8")) if _snap5_p.exists() else {
        "sources": {"s1": {}}, "prior_source": None}
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

# 相依套件缺了要**紅**，不要跳過。跳過會讓「這幾條測過了」跟「這幾條沒跑」
# 在畫面上長得一樣，而那正是這個 repo 花最多力氣在防的東西（紅線 8）。
# CI 的 mutation.yml 有裝 ruamel.yaml，所以這一條在 CI 恆綠；它紅的時候
# 講的是**你這台機器**測不到那幾條，一行指令就能修。
# ── sources.yaml 必須是 ruamel round-trip 的不動點 ──
# 2026-08-11 實際踩到：capabilities 那 97 行我手寫成 4 空格縮排，而 ruamel 吐出來的
# 是 2 空格（跟這個檔其他序列一致）。機器第一次 `--apply` 就把整份重排，
# 而 M226/M227 兩條變異的針腳指著 4 空格的字串——當晚夜班直接紅。
#
# 這一條守的不是縮排好不好看，是**「人手寫的格式」與「機器會吐的格式」必須一致**。
# 不一致的時候，第一個踩到的不是格式，是所有依賴那段文字的東西：變異針腳、
# diff 的可讀性、以及任何拿字串去比對這個檔的判準。
#
# 它在 CI 上的成本是一次 round-trip（毫秒級），換到的是「手寫 YAML 的那一刻就知道」。
def _ok(fn):
    """跑得起來回 True，丟 SystemExit 回 False。用來測「壞輸入要拒跑」。"""
    try:
        fn()
        return True
    except SystemExit:
        return False


def _rt_fixed_point():
    try:
        from ruamel.yaml import YAML
    except ImportError:
        return None
    import io as _io2
    src = open(os.path.join(_HERE, "..", "_config", "sources.yaml"),
               encoding="utf-8").read()
    # 這兩行要跟 pulse-source-health.py / pulse-robots-recheck.py 的 writer 一致。
    # 不一致的話這條測的就不是真的會被寫回去的那個格式。
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    buf = _io2.StringIO()
    y.dump(y.load(src), buf)
    return buf.getvalue() == src


# ── 變異分片必須是一個分割（不重不漏）──
# 一條變異因為切片邏輯而從來沒被跑過，是這支腳本最糟的失敗方式：清單看起來很完整，
# 而其中一格從來沒有人驗過。而且它不會紅——沒跑到的那一條當然不會回報失敗。
_MT = importlib.util.spec_from_file_location(
    "mutate_mod", os.path.join(_HERE, "mutate.py"))
_MTM = importlib.util.module_from_spec(_MT)
_MT.loader.exec_module(_MTM)
_MUT_WF = _yaml.safe_load(open(os.path.join(
    _HERE, "..", ".github", "workflows", "mutation.yml"), encoding="utf-8"))
_MUT_N = len(_MUT_WF["jobs"]["mutate"]["strategy"]["matrix"]["shard"])
_MUT_ALL = _MTM.load_inventory()
_MUT_PARTS = [{x["id"] for x in _MTM.shard(_MUT_ALL, k, _MUT_N)}
              for k in range(1, _MUT_N + 1)]
acase("變異分片：n 片合起來剛好是全部，而且兩兩不相交"
      "（漏掉一條不會有任何東西變紅——沒跑到的那一條當然不會回報失敗）",
      [set().union(*_MUT_PARTS) == {x["id"] for x in _MUT_ALL},
       sum(len(p) for p in _MUT_PARTS) == len(_MUT_ALL)],
      [True, True])
acase("變異分片：workflow 的 matrix 片數與 --shard 的分母一致"
      "（兩個數字寫在不同地方，對不上的時候會靜靜地少跑或重跑一整片）",
      f"--shard ${{{{ matrix.shard }}}}/{_MUT_N}" in open(os.path.join(
          _HERE, "..", ".github", "workflows", "mutation.yml"),
          encoding="utf-8").read(),
      True)
acase("變異分片：壞掉的規格一律拒跑，不猜"
      "（猜的話最糟是「只跑了一部分卻報成全部跑過」）",
      [_ok(lambda: _MTM.parse_shard("2/4")), _ok(lambda: _MTM.parse_shard("5/4")),
       _ok(lambda: _MTM.parse_shard("abc")), _ok(lambda: _MTM.parse_shard("0/4"))],
      [True, False, False, False])

acase("sources.yaml：是 ruamel round-trip 的不動點"
      "（人手寫的格式要跟機器會吐的格式一致——不一致的話，機器第一次 --apply 就會"
      "把整份重排，而所有拿字串比對這個檔的東西會在那一晚同時失效）",
      _rt_fixed_point(), True)

acase("環境：`--apply` 那幾條需要 ruamel.yaml——缺了是「測不到」，不是「測過了」"
      "（pip install ruamel.yaml）",
      importlib.util.find_spec("ruamel.yaml") is not None, True)

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

# ------------------------------------------- 文件裡的死引用（2026-07-27 清根目錄）
# 起因：把兩個事件紀錄搬進 incidents/ 的時候，順手發現有兩處 docstring 指著不存在
# 的檔案，其中一處已經錯了很久。docstring 不會被執行，所以永遠不會有人「踩到」——
# 只會有下一個人照著它去找，找不到，然後以為東西被刪了。
#
# 形狀跟 gate_keys 一樣：**列舉是機械的，判準是人寫的，測試比對兩者。**
# 判準與它「不保證什麼」寫在 lib/deadrefs.py 的 docstring 裡。
from lib import deadrefs as _dr  # noqa: E402

_REPO = os.path.normpath(os.path.join(_HERE, ".."))
_dr_files = _dr.scan_files(_REPO)

# 掃描器自己要先是活的：regex 被改壞、或走目錄的地方被剪掉時，下面那條
# 「沒有死引用」會自動變成綠的，因為沒有東西可以違規。
acase("deadrefs：真的走到整個 repo（檔案數掉到個位數＝下一條變成恆綠）",
      len(_dr_files) > 30, True)
acase("deadrefs：候選路徑真的抽得出來（regex 壞掉時這裡先紅）",
      len({p for f in _dr_files[:400]
           for p in _dr.extract(open(os.path.join(_REPO, f), encoding="utf-8").read())})
      > 30, True)
acase("repo 裡沒有指向不存在檔案的路徑引用"
      "（檔案搬家、改名、或從一開始就寫錯——三種都在這裡紅）",
      _dr.dead(_REPO, _dr_files), [])

# 判準本身的單元測試：釘的是「會不會誤放、會不會誤抓」，不是 repo 現況。
acase("deadrefs：產物目錄不算斷鏈（乾淨的 clone 裡本來就沒有 _probe/ 的東西）",
      _dr.is_artifact("_probe/title-zh-worklist.json"), True)
acase("deadrefs：references/ 不是產物目錄（反方向，確認上一條不是恆真）",
      _dr.is_artifact("references/vault-pages.md"), False)
acase("deadrefs：單字母檔名是格式示例，不是引用"
      "（`消費者：scripts/x.py` 那種）",
      [_dr.is_placeholder("scripts/x.py"), _dr.is_placeholder("scripts/mutate.py")],
      [True, False])
acase("deadrefs：第一段不是 repo 頂層的東西就不管它"
      "（`openai.com/robots.txt` 是網址、`assets/app.css` 是 dist/ 底下的相對連結，"
      "都不是在指本 repo）",
      [_dr.resolves(_REPO, "AGENTS.md", "openai.com/robots.txt"),
       _dr.resolves(_REPO, "AGENTS.md", "assets/app.css")],
      [True, True])
acase("deadrefs：路徑也試著相對於「寫它的那個檔案」解析一次"
      "（scripts/*.py 裡寫 lib/sources.py 是對的，不是斷鏈）",
      _dr.resolves(_REPO, "scripts/pulse-probe.py", "lib/sources.py"), True)

# 判準 5：還沒動工的提案。加這條之前，提案得把它要造的檔案寫成不是路徑的樣子才能
# 讓 CI 綠——2026-07-27 一份提案 11 處這樣寫，讓 selftest 常紅、mutate.py 拒跑、
# **每個動到 scripts/ 的 PR 都合不進去**，整個變異安全網停擺一天。
# 假路徑一樣要用拼的（理由見下面那條的註解——寫成字面值，掃描器會在 selftest.py
# 自己身上抓到它，「repo 裡沒有死引用」那條就永遠紅）。第一版就踩了，當場紅一條。
_dr_open = ("---\ntitle: T\nstatus: proposal\n---\n\n見 _config"
            + "/no-such-proposal-file.yaml。\n")
acase("deadrefs：docs/design/ 下還開著的提案，指到不存在的檔案不算斷鏈"
      "（那是它要造的東西，不是它引用的）",
      _dr.is_open_proposal("docs/design/x.md", _dr_open), True)
acase("deadrefs：豁免綁在 status 上所以**會過期**——提案落地後改掉 status，"
      "檢查就回來（永不過期的豁免等於把整個目錄從檢查裡拿掉，而白名單腐爛"
      "正是這個模組開頭在避免的事）",
      _dr.is_open_proposal("docs/design/x.md",
                           _dr_open.replace("status: proposal", "status: accepted")),
      False)
acase("deadrefs：同樣的內容放在 docs/design/ 以外不豁免（反方向，確認上面兩條"
      "不是恆真）",
      [_dr.is_open_proposal("references/x.md", _dr_open),
       _dr.is_open_proposal("scripts/x.py", _dr_open)], [False, False])
acase("deadrefs：docs/design/ 下沒有 status 欄的檔案不豁免"
      "（沒宣告自己是提案的東西，不能默默拿到提案的待遇）",
      _dr.is_open_proposal("docs/design/x.md",
                           "# 沒有 frontmatter\n見 _config" + "/no-such.yaml。"),
      False)
acase("deadrefs：豁免真的接在 dead() 上，不是只有那個判斷函式存在"
      "（判準對了但沒接線，等於沒判）",
      [(f, p) for f, p in _dr.dead(_REPO)
       if f.startswith("docs/design/")], [])
# 這個假路徑刻意用拼的，不寫成一整個字面值：寫成字面值，掃描器會在 selftest.py
# 自己身上抓到它，上面那條「repo 裡沒有死引用」就永遠是紅的。把 selftest.py 排除
# 掉也能解決，但那等於在檢查上開一個沒有底的洞——測試檔裡的真斷鏈也一起看不到了。
_dr_missing = "references" + "/no-such-file-here.md"
acase("deadrefs：頂層目錄存在、檔案不存在＝真的斷鏈（這條是整份檢查的唯一出口）",
      _dr.resolves(_REPO, "AGENTS.md", _dr_missing), False)
acase("deadrefs：extract 只認含目錄的路徑，裸檔名不收"
      "（收了，散文裡每一句「見 xxx.md」都變成候選，誤報會淹掉真報）",
      _dr.extract("見 BACKLOG.md 與 references/vault-pages.md"),
      ["references/vault-pages.md"])

# ------------------------------------------- 時區：儲存 UTC、顯示台北（2026-07-27）
# 規格 references/timezones.md。這一段釘的是**兩件不同的事**：
#   1. 判準本身對不對（clock.utc_date / display_date 的單元測試）
#   2. 有沒有人繞過它（機械掃全 repo）
# 只有第 1 條的話，這條規則會第三次犯——前兩次就是「規則寫下來、修好了」，
# 然後另一個消費端安靜地繼續用舊寫法，而且不會有任何東西紅。
from lib import clock as _clk  # noqa: E402
import datetime as _dt_m  # noqa: E402

_TZ_QWEN = "2026-07-28T02:00:00+08:00"
acase("clock.utc_date：+08:00 的 02:00 是**前一天**的 UTC"
      "（這個字串會進 evt-<日期>-<hash> 的 id，而 id 寫進 Events/ 之後不能改）",
      [_clk.utc_date(_dt_m.datetime.fromisoformat(_TZ_QWEN)).isoformat(),
       _clk.display_date(_dt_m.datetime.fromisoformat(_TZ_QWEN)).isoformat()],
      ["2026-07-27", "2026-07-28"])
acase("clock：UTC 16:00 之後的事，對台北讀者是隔天"
      "（實測 52 則 Event 有 12 則落在這條帶上）",
      [_clk.utc_date(_dt_m.datetime.fromisoformat("2026-07-23T20:11:00+00:00")).isoformat(),
       _clk.display_date_str(_dt_m.datetime.fromisoformat("2026-07-23T20:11:00+00:00"))],
      ["2026-07-23", "2026-07-24"])
acase("clock：UTC 16:00 之前的事兩邊同一天（反方向，確認上一條不是恆位移）",
      [_clk.utc_date(_dt_m.datetime.fromisoformat("2026-07-23T09:00:00+00:00")).isoformat(),
       _clk.display_date_str(_dt_m.datetime.fromisoformat("2026-07-23T09:00:00+00:00"))],
      ["2026-07-23", "2026-07-23"])
acase("clock：沒有時區標示的值視為 UTC，不是視為台北"
      "（實測語料 1391 筆裡有 429 筆沒標時區；當成台北會讓歷史資料整批位移，"
      "而我們沒有任何證據說那些站是用台北時間發的——紅線 8）",
      _clk.utc_date(_dt_m.datetime(2026, 7, 23, 20, 11)).isoformat(), "2026-07-23")
acase("clock.display_stamp 帶得出時區四個字"
      "（沒有標示的日期，讀者會預設是自己的時區，而 23% 的情況那是錯的）",
      _clk.DISPLAY_TZ_LABEL in _clk.display_stamp(
          _dt_m.datetime(2026, 7, 27, 4, 28, tzinfo=_dt_m.timezone.utc)), True)
acase("clock.display_stamp：台北 = UTC + 8",
      _clk.display_stamp(_dt_m.datetime(2026, 7, 27, 4, 28, tzinfo=_dt_m.timezone.utc)),
      "2026-07-27 12:28（台北時間）")
acase("clock.utc_stamp：給機器讀的那一版留 Z、不換算",
      _clk.utc_stamp(_dt_m.datetime(2026, 7, 27, 4, 28, tzinfo=_dt_m.timezone.utc)),
      "2026-07-27 04:28Z")
acase("clock：None 進 None 出，不要炸也不要變成今天",
      [_clk.utc_date(None), _clk.display_date(None), _clk.display_date_str(None)],
      [None, None, None])

# 掃描器自己要先是活的：偵測邏輯壞掉時，下面那條「沒有人繞過」會自動變綠。
acase("clock.banned_date_calls：抓得到裸 .date()",
      _clk.banned_date_calls("d.date()\n"), ["1:date()"])
acase("clock.banned_date_calls：抓得到 date.today()",
      _clk.banned_date_calls("import datetime\nx = date.today()\n"), ["2:today()"])
acase("clock.banned_date_calls：自己格式化日期字串也算"
      "（`strftime(\"%Y-%m-%d\")` 一樣繞過時鐘，只是換個寫法）",
      _clk.banned_date_calls('d.strftime("%Y-%m-%d")\n'), ["1:strftime()"])
acase("clock.banned_date_calls：純時間格式不算（%H:%M 沒有日期欄位，不會位移）",
      _clk.banned_date_calls('d.strftime("%H:%M")\n'), [])
acase("clock.banned_date_calls：註解與 docstring 裡的寫法不算違規"
      "（走 ast 不走 regex——這個 repo 的說明文字裡到處都是 `.date()`，"
      "用 regex 會把解釋讀成違規，然後大家就把這條檢查關掉）",
      _clk.banned_date_calls('"""別用 d.date()。"""\n# 也別用 date.today()\nx = 1\n'), [])
acase("clock.banned_date_calls：別人的 .today() 不算（只認 date.today()）",
      _clk.banned_date_calls("cal.today()\n"), [])

# 真正的那一條：全 repo 掃，除了 clock.py 自己。
_clk_files = sorted(_glob.glob(os.path.join(_HERE, "*.py"))
                    + _glob.glob(os.path.join(_HERE, "lib", "*.py")))
acase("clock：掃描真的走到全部腳本（檔案數掉下來＝下一條變恆綠）",
      len(_clk_files) > 20, True)
acase("除了 lib/clock.py，沒有任何腳本自己取日期"
      "（規則 2026-07-26 就寫下來過、也修好過——但只修在發現它的那個消費端，"
      "產生 id 的 pulse-cluster 安靜地用了三個月的裸 .date()。"
      "收成一個模組擋不住第三次，擋得住的是這條）",
      [f"{os.path.relpath(_p, _REPO)}:{_v}" for _p in _clk_files
       if os.path.basename(_p) not in ("clock.py", "selftest.py")
       for _v in _clk.banned_date_calls(open(_p, encoding="utf-8").read())],
      [])
# 顯示層的時區只准出現在 render：儲存層碰到它，UTC 那條線就破了。
acase("DISPLAY_TZ 只有 pulse-render.py 與 pulse-github.py 會用到"
      "（榜單頁把 generated 直接印給讀者，所以它也是顯示層；"
      "其他任何檔案出現＝儲存層開始寫台北日期了）",
      sorted(os.path.basename(_p) for _p in _clk_files
             if os.path.basename(_p) not in ("clock.py", "selftest.py")
             and ("DISPLAY_TZ" in open(_p, encoding="utf-8").read()
                  or "display_stamp" in open(_p, encoding="utf-8").read()
                  or "display_date" in open(_p, encoding="utf-8").read())),
      ["pulse-github.py", "pulse-render.py"])

# `utc_today()` 在這個容器裡跟 `date.today()` 是同一個答案（runner 是 UTC），
# 所以拿值去比對釘不住任何東西——M78 第一輪就是這樣活下來的。
# 改成**同一個瞬間、兩個相差 26 小時的本機時區**各問一次：UTC 的答案必須一樣，
# 本機時區的答案必須不一樣。兩邊都釘，才分得出「它讀 UTC」與「它剛好等於 UTC」。
import time as _time_m  # noqa: E402

_tz_saved = os.environ.get("TZ")


def _under_tz(tz, fn):
    os.environ["TZ"] = tz
    _time_m.tzset()
    try:
        return fn()
    finally:
        if _tz_saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = _tz_saved
        _time_m.tzset()


_TZ_EAST, _TZ_WEST = "Etc/GMT-14", "Etc/GMT+12"   # UTC+14 / UTC−12，差 26 小時
acase("clock.utc_today 不隨執行機器的時區跑掉"
      "（UTC+14 與 UTC−12 相差 26 小時，本機日期必然不同日；"
      "utc_today 兩邊必須一樣，否則同一份語料在台北跟在 Actions 上會開出"
      "兩個不同的 _corpus/<日>/ 目錄）",
      _under_tz(_TZ_EAST, lambda: _clk.utc_today().isoformat())
      == _under_tz(_TZ_WEST, lambda: _clk.utc_today().isoformat()),
      True)
# ── 排程：cron 是 UTC，連 day-of-week 也是 ──
# 起因：一個叫「每週一」的排程任務寫 `0 16 * * 1`，那是 UTC 週一 16:00＝**台北週二**。
# 換算了「時」卻忘了換算「星期」——同一個錯的第二半，而且不會有任何東西紅。
_wf_dir = os.path.join(_REPO, ".github", "workflows")
_crons = {os.path.basename(_p): open(_p, encoding="utf-8").read()
       for _p in sorted(_glob.glob(os.path.join(_wf_dir, "*.yml")))}
acase("cron 掃描真的讀到 workflow（檔案不見了，下面兩條會變成恆綠）",
      sorted(_crons) and all(_clk.cron_entries(_t) for _n, _t in _crons.items()
                          if "schedule:" in _t), True)
acase("每一行 cron 都在同一行註解裡寫出台北時間"
      "（cron 欄位沒有時區，一個沒被換算過的 cron 會被下一個人照台北讀）",
      {_n: _clk.cron_unannotated(_t) for _n, _t in _crons.items()
       if _clk.cron_unannotated(_t)}, {})
# **豁免清單是具名的，不是規則變寬。** 16:00Z 那條規則的理由是
# 「一班收到的東西正好是台北的一整天，而 _corpus/<UTC 日>/ 的目錄名也正好
# 等於那個台北日」——它是**寫 _corpus/ 的那條鏈**的規則，不是所有 cron 的規則。
#
# watchdog 不寫 _corpus/，而且它跑在 16:00Z 就失去意義：它存在的理由是
# 「被監看的那條鏈沒被排上時，它還在」，跟被監看的那一班同時起跑等於自廢武功
# （04:00Z ＝ 台北 12:00，看的是前一晚那班的結果）。
#
# 用具名清單而不是「只檢查 data-refresh」，是因為前者在有人加第三支每日班時
# 會紅——那正是應該有人停下來想一想的時刻。
_CRON_1600_EXEMPT = {"watchdog.yml"}
acase("每天固定一班的 cron 必須跑在 16:00Z"
      "（＝台北隔日 00:00，於是一班收到的東西正好是台北的一整天，"
      "而 _corpus/<UTC 日>/ 的目錄名也正好等於那個台北日。"
      "改成 20:00Z 看起來無害，但目錄名會跟內容錯開一天而不會有東西紅）",
      {_n: _clk.misanchored_daily(_t) for _n, _t in _crons.items()
       if _n not in _CRON_1600_EXEMPT
       if _clk.misanchored_daily(_t)}, {})
# 判準本身的單元測試。
acase("clock.daily_utc_hour：每天一班才回小時；週班與 */N 都回 None"
      "（把週班也拉進來管，`0 3 * * 1` 會被逼成 16:00Z，而那條規則對它沒有意義）",
      [_clk.daily_utc_hour("0 16 * * *"), _clk.daily_utc_hour("0 3 * * 1"),
       _clk.daily_utc_hour("0 */2 * * *"), _clk.daily_utc_hour("garbage")],
      [16, None, None, None])
acase("clock.misanchored_daily：20:00Z 的每日班要被抓出來",
      _clk.misanchored_daily("    - cron: '0 20 * * *'   # 台北 04:00\n"),
      ["0 20 * * *"])
acase("clock.misanchored_daily：16:00Z 放行（反方向，確認上一條不是恆紅）",
      _clk.misanchored_daily("    - cron: '0 16 * * *'   # 台北 00:00\n"), [])
acase("clock.cron_unannotated：沒有註解的 cron 要被抓出來",
      _clk.cron_unannotated("    - cron: '0 16 * * *'\n"), ["0 16 * * *"])

acase("對照：date.today() 在那兩個時區下必然不同日"
      "（沒有這一條，上面那條可能只是「這台機器剛好是 UTC」）",
      _under_tz(_TZ_EAST, lambda: _dt_m.date.today().isoformat())
      != _under_tz(_TZ_WEST, lambda: _dt_m.date.today().isoformat()),
      True)

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
    # 判斷層帳本那一行要真的印在看板上。只釘 narrative_ledger_line 這個純函式
    # 不夠——判準對而呼叫端沒接，帳本一樣沒有消費者，而它哪天停掉就沒有東西會紅。
    _md_led = _mm.render_health(_r3, _h_green, None, [
        {"at": "2026-07-02T00:00:00+00:00", "id": "infra-cost", "field": "now",
         "from": "a", "to": "b", "reason": "nightly-enrich"}])
    acase("健康頁：判斷層帳本那一行真的印得出來（走真的 render_health——"
          "純函式對而呼叫端沒接，帳本一樣沒有消費者）",
          ["判斷層帳本" in _md_led, "infra-cost" in _md_led,
           "判斷層帳本" in _mm.render_health(_r3, _h_green)],
          [True, True, True])

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

# ── Event 標題中文化（references/obsidian-schema.md〈Event 的標題有兩個〉）──
from lib import zhtext as _zt  # noqa: E402

_tp_spec = importlib.util.spec_from_file_location(
    "pulse_title_prep", os.path.join(_HERE, "pulse-title-prep.py"))
_tp = importlib.util.module_from_spec(_tp_spec)
_tp_spec.loader.exec_module(_tp)
_ta_spec = importlib.util.spec_from_file_location(
    "pulse_title_apply", os.path.join(_HERE, "pulse-title-apply.py"))
_ta = importlib.util.module_from_spec(_ta_spec)
_ta_spec.loader.exec_module(_ta)

acase("references/obsidian-schema.md 有〈Event 的標題有兩個〉那一節（紅線 9）",
      "Event 的標題有兩個" in _read_repo_file("references/obsidian-schema.md"), True)
acase("排程：Event 標題待譯清單真的被排進 workflow，且自己一個 run:",
      [bool(_step_with("pulse-title-prep.py")),
       _step_with("pulse-title-prep.py") == _step_with("pulse-github-desc-prep.py")],
      [True, False])

# 驗章：判準只有一份，榜單描述與 Event 標題共用。
acase("譯文驗章：原文變了譯文就失效（前台退回原文，不掛一句在講舊標題的中文）",
      [_zt.valid_for({"zh": "中文", "src_hash": _zt.src_hash("A")}, "A"),
       _zt.valid_for({"zh": "中文", "src_hash": _zt.src_hash("A")}, "B"),
       _zt.valid_for({"zh": "", "src_hash": _zt.src_hash("A")}, "A"),
       _zt.valid_for(None, "A")],
      ["中文", None, None, None])
from lib import ghdesc as _gd3  # noqa: E402
acase("譯文驗章：ghdesc 的 src_hash 就是 zhtext 的那一支（不留第二份實作）",
      _gd3.src_hash("abc") == _zt.src_hash("abc"), True)
acase("譯文驗章：英文原樣貼回來不算翻譯、AI 腔套話退件、正常的放行",
      [_zt.validate("This is english", 40)[1] is not None,
       _zt.validate("這個專案賦能開發者", 40)[1] is not None,
       _zt.validate("NVIDIA 發表新一代 GPU", 40)[1]],
      [True, True, None])
acase("譯文驗章：退件訊息可以由呼叫端補自己那一層的理由"
      "（判準共用、解釋不共用——一句解釋不到位的退件訊息會讓人以為規則寫錯了）",
      "標題要跟原文並排" in _zt.validate("中" * 50, 40, len_note="（標題要跟原文並排）")[1],
      True)

# prep：誰要翻是規則的事。
_tp_rows = [
    {"id": "e1", "title": "A"},                                        # 沒翻過
    {"id": "e2", "title": "B", "title_zh": "乙", "title_zh_src": _zt.src_hash("B")},
    {"id": "e3", "title": "C", "title_zh": "丙", "title_zh_src": _zt.src_hash("舊")},
    {"id": "e4", "title": ""},                                         # 沒有標題
]
acase("標題待譯：沒翻過的、以及原文變了失效的要進清單；已經對得上的不進",
      [t["id"] for t in _tp.pending(_tp_rows)], ["e1", "e3"])
acase("標題待譯：原文變了那一條要標 stale_zh（那是重譯不是新增）",
      [t["stale_zh"] for t in _tp.pending(_tp_rows)], [None, "丙"])

with tempfile.TemporaryDirectory() as _ttd:
    _tv = Path(_ttd)
    _tw = _tv / "_probe"
    _tw.mkdir()
    (_tw / "title-zh-worklist.json").write_text('[{"id": "keep"}]', encoding="utf-8")
    _t_argv, _t_env = sys.argv[:], os.environ.get("VAULT_DIR")
    sys.argv = ["pulse-title-prep.py"]
    os.environ["VAULT_DIR"] = str(_tv)
    try:
        _t_rc = _tp.main()                      # Events/ 不存在
    finally:
        sys.argv = _t_argv
        if _t_env is not None:
            os.environ["VAULT_DIR"] = _t_env
    _t_kept = (_tw / "title-zh-worklist.json").read_text("utf-8")
acase("標題待譯：Events/ 不在 → 回 2 且**不覆寫**既有清單"
      "（跟 github-desc-prep 同一個坑：量不到寫成空清單，下游照著跳過）",
      [_t_rc, _t_kept], [2, '[{"id": "keep"}]'])

# apply：寫回 frontmatter，body 一個字不動、欄位順序不洗掉。
_ta_note = ("---\nid: e1\ntitle: Some English Title\nstatus: published\n"
            "keywords:\n- a\n---\n\n## 事實\n本文不該被動到。\n")
_ta_new = _ta.rewrite(_ta_note, "中文標題", "Some English Title")
_ta_fm = _yaml.safe_load(_ta_new.split("---")[1])
acase("標題寫回：title_zh 與 title_zh_src 都寫進去，且綁的是當下那句原文",
      [_ta_fm["title_zh"], _ta_fm["title_zh_src"] == _zt.src_hash("Some English Title"),
       _ta_fm["title"]],
      ["中文標題", True, "Some English Title"])
acase("標題寫回：body 一個字不動（潤好的 prose 不能被翻譯這一步吃掉）",
      "## 事實\n本文不該被動到。" in _ta_new, True)
acase("標題寫回：既有欄位順序不變"
      "（順序一洗，每則 Event 的 diff 都像被整份改寫過，真正的變化就埋掉了）",
      list(_ta_fm)[:4], ["id", "title", "status", "keywords"])

# 顯示層：中文在上、原文在下；沒有中文就只有原文。
_rs2 = importlib.util.spec_from_file_location(
    "pulse_render_t", os.path.join(_HERE, "pulse-render.py"))
_pr = importlib.util.module_from_spec(_rs2)
_rs2.loader.exec_module(_pr)
acase("標題顯示：有中文就中文在上、原文在下（譯文是二手的，讀者要看得到一手那句）",
      [_pr.title_html({"title": "English", "title_zh": "中文"}).count("<div"),
       "中文" in _pr.title_html({"title": "English", "title_zh": "中文"}),
       "English" in _pr.title_html({"title": "English", "title_zh": "中文"})],
      [2, True, True])
acase("標題顯示：沒有中文就只印原文一行（反方向，確認上一條不是恆為兩行）",
      [_pr.title_html({"title": "English", "title_zh": None}).count("<div"),
       "English" in _pr.title_html({"title": "English"})], [1, True])

# ── 待譯清單由 Actions 準備（scripts/enrich-runbook.md 的 C2 段）──
_dp_spec = importlib.util.spec_from_file_location(
    "pulse_github_desc_prep", os.path.join(_HERE, "pulse-github-desc-prep.py"))
_dp = importlib.util.module_from_spec(_dp_spec)
_dp_spec.loader.exec_module(_dp)

acase("排程：待譯清單由抓取鏈準備，且不跟別的頁共用同一個 run:"
      "（潤稿端沒有 GITHUB_TOKEN——它自己重建榜單那一步是整個 C2 唯一的外部依賴）",
      [bool(_step_with("pulse-github-desc-prep.py")),
       _step_with("pulse-github-desc-prep.py") == _step_with("pulse-entity-notes.py")],
      [True, False])
acase("排程：待譯清單要排在 pulse-github.py 之後（榜單先生出來才有得挑）、Commit 之前",
      (max(_step_with("pulse-github.py"))
       < min(_step_with("pulse-github-desc-prep.py"))
       < min(_step_with("git push"))), True)
acase("runbook：C2 已經不叫潤稿端自己重建榜單",
      "python scripts/pulse-github.py" in
      open(os.path.join(_HERE, "enrich-runbook.md"), encoding="utf-8").read()
      .split("**C2.")[1].split("**D.")[0], False)


def _dp_run(vault):
    _a, _e = sys.argv[:], os.environ.get("VAULT_DIR")
    sys.argv = ["pulse-github-desc-prep.py", "--limit", "25"]
    os.environ["VAULT_DIR"] = str(vault)
    try:
        return _dp.main()
    finally:
        sys.argv = _a
        if _e is not None:
            os.environ["VAULT_DIR"] = _e


with tempfile.TemporaryDirectory() as _dptd:
    _dpv = Path(_dptd)
    (_dpv / "_probe").mkdir()
    _dpwl = _dpv / "_probe" / "github-desc-worklist.json"
    _dpwl.write_text('[{"full_name": "a/b"}]', encoding="utf-8")   # 上一班留下的清單

    _rc_missing = _dp_run(_dpv)                                     # board 不在
    _kept_missing = _dpwl.read_text("utf-8")

    (_dpv / "dist" / "data").mkdir(parents=True)
    (_dpv / "dist" / "data" / "github.json").write_text(
        _json.dumps({"generated": "x", "count": 0, "repos": [], "measured": False}),
        encoding="utf-8")
    _rc_unmeasured = _dp_run(_dpv)                                  # 抓取全失敗的佔位檔
    _kept_unmeasured = _dpwl.read_text("utf-8")

    (_dpv / "dist" / "data" / "github.json").write_text(
        _json.dumps({"generated": "x", "count": 0, "repos": [], "measured": True}),
        encoding="utf-8")
    _rc_ok = _dp_run(_dpv)                                          # 真的沒有東西要翻
    _wrote_empty = _json.loads(_dpwl.read_text("utf-8"))

acase("待譯清單：量不到就不覆寫，而且回離開碼 2"
      "（舊版在這裡寫一份空陣列，於是「榜單沒生出來」跟「今晚沒東西要翻」"
      "在磁碟上長得一模一樣，下游照著跳過、沒有人知道為什麼）",
      [_rc_missing, _kept_missing, _rc_unmeasured, _kept_unmeasured],
      [2, '[{"full_name": "a/b"}]', 2, '[{"full_name": "a/b"}]'])
acase("待譯清單：真的量到而且沒有東西要翻 → 才寫空陣列、回 0"
      "（反方向；只釘「不覆寫」的話，一支永遠不寫檔的腳本也會通過）",
      [_rc_ok, _wrote_empty], [0, []])

# ── 待譯清單要涵蓋整頁，不是涵蓋其中一個榜（2026-07-29）─────────────
# 2026-07-29 GitHub 那一頁變成兩個榜（星速 / 竄升），而這條翻譯鏈只認 `repos`。
# 兩個榜是同一批 repo 的兩種排序、各自截前 top_n，所以 `surging \ repos` 非空是
# **結構上一定可能發生**的：落在那個差集裡的 repo 永遠排不進待譯清單，而每一班
# 照樣印「待譯 N 條」，讀起來像清單是滿的。
# 同一隻病：一個比事實窄的東西掛著事實的名字。
# （差集實際多大這個容器量不到——api.github.com 在這裡是 403。下面用的是自製的
#  四條 fixture，它證明的是「程式碼會不會漏」，不是「生產環境漏了幾條」。）
from lib import ghdesc as _gu  # noqa: E402

_B1 = [{"full_name": "big/a"}, {"full_name": "big/b"}, {"full_name": "big/c"}]
_B2 = [{"full_name": "sml/x"}, {"full_name": "big/b"}]     # big/b 兩邊都上
acase("兩個榜併清單：輪流取、重複的只留一份、長度不同也不掉條"
      "（接起來的話 --limit 的額度會整段落在第一個榜上，"
      "而星速榜偏袒大 repo——那條偏袒就從排序爬回了翻譯順序）",
      [[r["full_name"] for r in _gu.board_union(_B1, _B2)],
       [r["full_name"] for r in _gu.board_union([], _B2)],
       _gu.board_union()],
      [["big/a", "sml/x", "big/b", "big/c"], ["sml/x", "big/b"], []])

_BOARD2 = {"generated": "x", "count": 2, "measured": True,
           "repos": [{"full_name": "big/a", "desc": "A"},
                     {"full_name": "big/b", "desc": "B"}],
           "surging": [{"full_name": "sml/x", "desc": "X"},
                       {"full_name": "big/a", "desc": "A"}]}
with tempfile.TemporaryDirectory() as _u2td:
    _u2v = Path(_u2td)
    (_u2v / "_probe").mkdir()
    (_u2v / "dist" / "data").mkdir(parents=True)
    (_u2v / "dist" / "data" / "github.json").write_text(
        _json.dumps(_BOARD2), encoding="utf-8")
    _dp_run(_u2v)
    _u2_todo = [t["full_name"] for t in
                _json.loads((_u2v / "_probe" / "github-desc-worklist.json")
                            .read_text("utf-8"))]
acase("待譯清單：竄升榜上的 repo 也要排得進來"
      "（只掃星速榜的那一版，讓竄升榜整個榜永遠是英文，"
      "而覆蓋率印的是星速榜的分母，所以看起來一直很滿）",
      [sorted(_u2_todo), "sml/x" in _u2_todo], [["big/a", "big/b", "sml/x"], True])
# 反向：那個測試不是因為「什麼都排得進來」才綠的——已經翻好的不會再排進來。
with tempfile.TemporaryDirectory() as _u3td:
    _u3v = Path(_u3td)
    (_u3v / "_probe").mkdir()
    (_u3v / "_github").mkdir()
    (_u3v / "dist" / "data").mkdir(parents=True)
    (_u3v / "dist" / "data" / "github.json").write_text(
        _json.dumps(_BOARD2), encoding="utf-8")
    (_u3v / "_github" / "desc-zh.json").write_text(_json.dumps(
        {"sml/x": {"zh": "小專案", "src_hash": _gu.src_hash("X"), "at": "t"}}),
        encoding="utf-8")
    _dp_run(_u3v)
    _u3_todo = [t["full_name"] for t in
                _json.loads((_u3v / "_probe" / "github-desc-worklist.json")
                            .read_text("utf-8"))]
acase("待譯清單：竄升榜上已經有有效中文的不再排進來（反向）",
      [sorted(_u3_todo), "sml/x" in _u3_todo], [["big/a", "big/b"], False])
# 寫回端要認同一份榜。只認 `repos` 的話，prep 排進清單的竄升榜 repo 翻回來會被
# 退件、理由是「不在目前榜單上」——而它就在榜上，只是在另一個榜。
# 退件訊息把人指向沒有問題的地方，跟 2026-07-28 那次一模一樣。
_u_src, _u_origin = _dam.english_source(_BOARD2, None)
acase("寫回：英文原文兩個榜都認得（不然竄升榜的譯文會被退件，"
      "理由是「不在目前榜單上」——而它就在榜上，只是在另一個榜）",
      [_u_origin, sorted(_u_src), _u_src.get("sml/x")],
      ["board", ["big/a", "big/b", "sml/x"], "X"])
# 覆蓋率那一格的分母要等於畫面上有幾列。只算星速榜的那一版會印「8/8」，
# 而畫面上有十五列、其中七列是英文——分母比畫面窄，名字卻叫「中文描述」。
# 真的跑一次 main()，不 grep 原始碼：grep 只證明那串字還在。
_gh2_spec = importlib.util.spec_from_file_location(
    "pulse_github_mod2", os.path.join(_HERE, "pulse-github.py"))
_ghm2 = importlib.util.module_from_spec(_gh2_spec)
_gh2_spec.loader.exec_module(_ghm2)
# 兩個榜必須真的排出不同的前二名，否則這條測試會在「union 等於任一個榜」的
# 情況下自動變綠——那正是它要抓的錯。
_U_REPOS = {
    "big/a": {"full_name": "big/a", "desc": "A", "stars": 100000, "url": "u",
              "language": "Go", "topics": [], "created": "2020-01-01"},
    "big/b": {"full_name": "big/b", "desc": "B", "stars": 50000, "url": "u",
              "language": "Go", "topics": [], "created": "2020-01-01"},
    "sml/x": {"full_name": "sml/x", "desc": "X", "stars": 1000, "url": "u",
              "language": "Go", "topics": [], "created": "2020-01-01"},
    "sml/y": {"full_name": "sml/y", "desc": "Y", "stars": 400, "url": "u",
              "language": "Go", "topics": [], "created": "2020-01-01"},
}
with tempfile.TemporaryDirectory() as _u4td:
    _u4v = Path(_u4td)
    (_u4v / "_config").mkdir()
    (_u4v / "_github").mkdir()
    (_u4v / "_config" / "github.yaml").write_text("top_n: 2\nsearches: []\n",
                                                  encoding="utf-8")
    _u4_ts = _dt_m.datetime.now(_dt_m.timezone.utc).timestamp() - 86400
    (_u4v / "_github" / "state.json").write_text(_json.dumps({
        "big/a": {"stars": 99000, "ts": _u4_ts}, "big/b": {"stars": 49500, "ts": _u4_ts},
        "sml/x": {"stars": 500, "ts": _u4_ts}, "sml/y": {"stars": 210, "ts": _u4_ts}}),
        encoding="utf-8")
    # 一條中文，掛在**只在竄升榜上**的那個 repo 身上：只算星速榜的分子會是 0。
    (_u4v / "_github" / "desc-zh.json").write_text(_json.dumps(
        {"sml/x": {"zh": "小專案", "src_hash": _gu.src_hash("X"), "at": "t"}}),
        encoding="utf-8")
    _u4_collect, _u4_argv, _u4_env = _ghm2.collect, sys.argv[:], os.environ.get("VAULT_DIR")
    try:
        _ghm2.collect = lambda *a, **k: _U_REPOS
        sys.argv = ["pulse-github.py"]
        os.environ["VAULT_DIR"] = str(_u4v)
        _ghm2.main()
    finally:
        _ghm2.collect = _u4_collect
        sys.argv = _u4_argv
        if _u4_env is not None:
            os.environ["VAULT_DIR"] = _u4_env
    _u4_board = _json.loads((_u4v / "dist" / "data" / "github.json").read_text("utf-8"))
    _u4_cov = _json.loads((_u4v / "_github" / "desc-coverage.json").read_text("utf-8"))
_u4_vel = [r["full_name"] for r in _u4_board["repos"]]
_u4_sur = [r["full_name"] for r in _u4_board["surging"]]
acase("GitHub 動能：中文覆蓋率算整頁去重後的 repo 數，不是算其中一個榜"
      "（分母比畫面窄，而它掛著「中文描述」這個名字；"
      "分子同理——中文掛在只上竄升榜的那個 repo 上，只算星速榜會印 0）",
      [_u4_vel, _u4_sur, _u4_cov["ranked"], _u4_cov["with_zh"]],
      [["big/a", "big/b"], ["sml/x", "sml/y"], 4, 1])
# 頁上那一行是同一個分母的第二份說法（JS 自己算一次）。兩份要用同一個判準。
_GH_JS = open(os.path.join(_HERE, "pulse-github.py"), encoding="utf-8").read()
acase("GitHub 動能：頁上那行覆蓋率也數兩個榜（它是同一個分母的第二份說法）",
      ["repos.concat(surging)" in _GH_JS, '/"+repos.length+"' in _GH_JS],
      [True, False])

# ── 榜單中文描述：C2 段跳過不留痕跡（references/vault-pages.md）──
from lib import ghdesc as _gd2  # noqa: E402

_mon_spec = importlib.util.spec_from_file_location(
    "pulse_monitor_mod", os.path.join(_HERE, "pulse-monitor.py"))
_mon = importlib.util.module_from_spec(_mon_spec)
_mon_spec.loader.exec_module(_mon)

acase("榜單中文描述：量到中文那天才更新 last_with_zh_day（黏性）",
      [_gd2.next_coverage({}, "2026-07-27", 25, 0, 0)["last_with_zh_day"],
       _gd2.next_coverage({}, "2026-07-27", 25, 3, 3)["last_with_zh_day"],
       _gd2.next_coverage({"last_with_zh_day": "2026-07-20"}, "2026-07-27",
                          25, 0, 3)["last_with_zh_day"]],
      [None, "2026-07-27", "2026-07-20"])
acase("榜單中文描述：從來沒有過 → 回 None，不是 0 也不是一個很大的數"
      "（「從來沒有」跟「昨天還有」用同一個數字表示，第一種就會被讀成第二種）",
      [_gd2.days_without_zh({"last_with_zh_day": None}, "2026-07-27"),
       _gd2.days_without_zh({"last_with_zh_day": "2026-07-20"}, "2026-07-27")],
      [None, 7])
acase("榜單中文描述：那一班沒抓到榜單 → 寫 null 不寫 0（紅線 8）",
      [_gd2.next_coverage({}, "2026-07-27", None, None, 3)[k]
       for k in ("ranked", "with_zh", "store_entries")], [None, None, 3])

_dz = lambda cov: _mon.desc_zh_line(cov, "2026-07-27")
acase("榜單中文描述：四種狀態印出四句不同的話"
      "（量不到 / 從來沒翻過 / 有過然後停了 / 正常。擠成同一句就等於沒有這一格）",
      ["量不到" in _dz({})[0],
       "量不到" in _dz({"ranked": None, "with_zh": None, "store_entries": 0,
                     "day": "2026-07-27"})[0],
       "從來沒有" in _dz({"ranked": 25, "with_zh": 0, "store_entries": 0,
                       "last_with_zh_day": None, "day": "2026-07-27"})[0],
       "7 天前" in _dz({"ranked": 25, "with_zh": 0, "store_entries": 3,
                      "last_with_zh_day": "2026-07-20", "day": "2026-07-27"})[0],
       _dz({"ranked": 25, "with_zh": 7, "store_entries": 7,
            "last_with_zh_day": "2026-07-27", "day": "2026-07-27"})[1]],
      [True, True, True, True, False])
# 上面幾條釘的是判準。真正會騙人的是**呼叫端有沒有照著寫**——所以這條走真的
# main()，把 collect() 換成「API 全失敗」，看它寫出來的是 null 還是 0。
_gh_spec = importlib.util.spec_from_file_location(
    "pulse_github_mod", os.path.join(_HERE, "pulse-github.py"))
_ghm = importlib.util.module_from_spec(_gh_spec)
_gh_spec.loader.exec_module(_ghm)
with tempfile.TemporaryDirectory() as _ghtd:
    _ghv = Path(_ghtd)
    (_ghv / "_config").mkdir()
    (_ghv / "_config" / "github.yaml").write_text("top_n: 5\nsearches: []\n",
                                                  encoding="utf-8")
    _gh_collect, _gh_argv, _gh_envv = _ghm.collect, sys.argv[:], os.environ.get("VAULT_DIR")
    try:
        _ghm.collect = lambda *a, **k: {}
        sys.argv = ["pulse-github.py"]
        os.environ["VAULT_DIR"] = str(_ghv)
        _ghm.main()
    finally:
        _ghm.collect = _gh_collect
        sys.argv = _gh_argv
        if _gh_envv is not None:
            os.environ["VAULT_DIR"] = _gh_envv
    _ghcov = _json.loads((_ghv / "_github" / "desc-coverage.json").read_text("utf-8"))
    _ghboard = _json.loads(
        (_ghv / "dist" / "data" / "github.json").read_text("utf-8"))
acase("榜單佔位檔要標成沒量到（`measured: false`）"
      "（不標的話，這份 0 條的榜單跟「今天真的沒有 repo 上榜」在下游眼裡一樣，"
      "待譯清單會照著回報 0 條，翻譯就在沒人知道的情況下停擺）",
      [_ghboard.get("measured"), _ghboard.get("count")], [False, 0])
acase("榜單中文描述：抓取全失敗那一班照樣留下紀錄，而且兩格是 null 不是 0"
      "（寫 0 會讓「今天問不到 GitHub」看起來跟「榜上一條中文都沒有」一樣）",
      [_ghcov.get("ranked"), _ghcov.get("with_zh"), _ghcov.get("store_entries"),
       "day" in _ghcov], [None, None, 0, True])

acase("榜單中文描述：只有「有過然後停了」與「從來沒翻過」標成異常，"
      "量不到與正常都不標（量不到標成異常＝把 API 額度問題算成翻譯鏈壞了）",
      [_dz({})[1],
       _dz({"ranked": None, "with_zh": None, "store_entries": 0})[1],
       _dz({"ranked": 25, "with_zh": 0, "last_with_zh_day": None})[1],
       _dz({"ranked": 25, "with_zh": 0, "last_with_zh_day": "2026-07-20"})[1]],
      [False, False, True, True])

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
          # 這份清單要跟 event_markdown() 讀的欄位同步。不同步就 AttributeError
          # 當場炸——**那是刻意留著的**：一個會自動補上缺欄位的假物件，
          # 會讓「event_markdown 多讀了一格而沒人帶」變成靜默通過。
          type("E", (), {**{k: getattr(_e, k) for k in
                           ("id", "slug", "title", "happened_at", "fingerprint",
                            "facet", "company", "keywords", "evidence", "scores",
                            "title_zh", "title_zh_src", "coverage", "recovered_by")},
                         "ingested_at": None})()), True)

# ── coverage：事情發生的時候，我們看得到嗎 ───────────────────────────
# 規格：references/event-timestamps.md〈第三個現場：呈現層〉。判準：lib/coverage.py。
#
# 為什麼這批值得釘：時間軸上一則 backfilled 的舊事件，跟真的追到的長得**一模一樣**。
# 這一格是唯一分得開兩者的東西，而它的失效是靜默的——欄位還在、值是 observed、
# 頁面照印，只是那句話是假的。2026-07-27 實測 36 則已發布事件裡有 30 則的日期
# 早於其所有證據來源的首抓日，也就是事情發生時我們一條相關來源都沒有。
from lib import coverage as _covlib  # noqa: E402

_CV_FF = {"src-a": "2026-07-23T23:52:35+00:00",
          "src-b": "2026-07-26T10:00:00+00:00"}
_CV_EV_A = [{"source_id": "src-a", "url": "u1"}]

acase("coverage：封閉集維持三態（新增狀態要同時改規格、判準、selftest 與 mutation）",
      sorted(_covlib.COVERAGE_STATES), ["backfilled", "observed", "unknown"])
acase("coverage：事情發生在該來源首抓之前 → backfilled（首抓撈回的存量，不是追到的）",
      _covlib.coverage_of("2026-07-14T00:00:00+00:00", _CV_EV_A, _CV_FF), "backfilled")
acase("coverage：事情發生在首抓之後 → observed",
      _covlib.coverage_of("2026-07-25T00:00:00+00:00", _CV_EV_A, _CV_FF), "observed")
acase("coverage：正好等於首抓時刻算 observed"
      "（跟訊號層 is_backfill「每條來源第一次抓取整批算存量」是同一條線）",
      _covlib.coverage_of("2026-07-23T23:52:35+00:00", _CV_EV_A, _CV_FF), "observed")
acase("coverage：多來源取**最早**的首抓日（只要有一條當時在看，就算看得到）",
      _covlib.coverage_of("2026-07-25T00:00:00+00:00",
                          [{"source_id": "src-a"}, {"source_id": "src-b"}],
                          _CV_FF), "observed")

# 下面這條釘的是「讓數字變好看、又不會讓任何測試變紅」的那個改法。
acase("coverage：observable_from 只取**該事件證據來源**的首抓日，不取全體最小值"
      "（改成全體最小值幾乎所有事件都會變 observed，而畫面上沒有任何數字看起來不對）",
      _covlib.coverage_of("2026-07-25T00:00:00+00:00",
                          [{"source_id": "src-b"}], _CV_FF), "backfilled")

# unknown 這一族：全部**不得**倒向 observed。紅線 8——量不到就說量不到。
acase("coverage：任一證據來源沒有 first_fetch_at → unknown"
      "（跳過那一條去算其餘的最小值，等於把「有一條不知道何時開始看」稀釋成"
      "「別條看得到就算看得到」）",
      _covlib.coverage_of("2026-07-25T00:00:00+00:00",
                          [{"source_id": "src-a"}, {"source_id": "src-none"}],
                          _CV_FF), "unknown")
acase("coverage：first_fetch 整個沒傳進來 → unknown，不是 observed"
      "（預設值必須倒向誠實那一邊：併進 observed 的話，state.json 的任何缺格"
      "都會靜靜變成「我們當時在看」）",
      _covlib.coverage_of("2026-07-25T00:00:00+00:00", _CV_EV_A, None), "unknown")
acase("coverage：沒有證據 → unknown",
      _covlib.coverage_of("2026-07-25T00:00:00+00:00", [], _CV_FF), "unknown")
acase("coverage：沒有 happened_at → unknown",
      _covlib.coverage_of(None, _CV_EV_A, _CV_FF), "unknown")

# 寫檔那一端：算對了但沒寫出去，等於沒算。
_cv_e = _cm.Event("evt-cv", "cv", "T", "2026-07-14T00:00:00+00:00")
_cv_e.scores = dict(_e.scores)
acase("pulse-cluster：Event 預設 coverage 是 unknown"
      "（建立時忘了算的那一則，不得預設成「我們當時在看」）",
      _cv_e.coverage, "unknown")
acase("pulse-cluster：coverage 真的寫進 frontmatter",
      "coverage: unknown" in _cm.event_markdown(_cv_e), True)

_cv_e2 = _cm.Event("evt-cv2", "cv2", "T", "2026-07-14T00:00:00+00:00")
_cv_e2.add_evidence("src-a", "u1", "t", 100)
_cm.rescore(_cv_e2, {"src-a": {"tier": 1}}, None, None, None, _CV_FF)
acase("pulse-cluster：rescore 會算 coverage"
      "（07-14 發生的事 vs src-a 07-23 才首抓 → backfilled）",
      [_cv_e2.coverage, "coverage: backfilled" in _cm.event_markdown(_cv_e2)],
      ["backfilled", True])

_cm.rescore(_cv_e2, {"src-a": {"tier": 1}}, None, None, None,
            {"src-a": "2026-07-01T00:00:00+00:00"})
acase("pulse-cluster：coverage 是推導欄位不是 sticky 欄位——first_fetch_at 修正之後"
      "值要跟著改（寫死成 sticky 的話，來源首抓日修正了它會永遠停在舊答案）",
      _cv_e2.coverage, "observed")

# 遷移那條路：既有 Event reload 之後 dirty=False，沒有人會重寫它們。少了
# 「算出來跟檔案上不一樣就標髒」，這一格只會長在有新證據進來的那些 Event 上——
# 實測（上線前那一跑）52 則一則都沒拿到，而畫面上沒有任何異狀。
_cv_old = _cm.Event("evt-cv3", "cv3", "T", "2026-07-14T00:00:00+00:00")
_cv_old.add_evidence("src-a", "u1", "t", 100)
_cv_old.fm = {"coverage": None}        # 模擬還沒有這一格的既有 note
_cv_old.dirty = False                  # reload 之後的狀態
acase("pulse-cluster：既有 Event 的 coverage 跟磁碟上不一樣 → apply_coverage 回 True"
      "（沒有這條，欄位只會長在有新證據的那些 Event 上，而規格會說得像每則都有）",
      [_cm.apply_coverage(_cv_old, _CV_FF), _cv_old.coverage], [True, "backfilled"])
acase("pulse-cluster：apply_coverage **只算不標髒**——標髒等於整份重寫，而整份重寫會把"
      "還沒潤稿的 dropped 事件復活成 review、還會拿今天的時鐘重算全部分數",
      _cv_old.dirty, False)

_cv_same = _cm.Event("evt-cv4", "cv4", "T", "2026-07-14T00:00:00+00:00")
_cv_same.add_evidence("src-a", "u1", "t", 100)
_cv_same.fm = {"coverage": "backfilled"}
acase("pulse-cluster：coverage 沒變就回 False（否則每班重寫全部 Event，git 每天長一次"
      "無意義的 diff，真正的改動會被埋在裡面）",
      _cm.apply_coverage(_cv_same, _CV_FF), False)

# 外科式補一格：這條釘的是「補欄位不得有副作用」。第一版把 coverage 走整份重寫，
# 實測會讓 52 則的 value / freshness 全部位移，而未潤稿的 dropped 事件會被復活成
# review 並丟掉 dropped_at / drop_reason——人工判定被一個「加欄位」的改動洗掉。
_pc_dir = _pathlib.Path(_tempfile.mkdtemp())
_pc_note = _pc_dir / "evt-x.md"
_pc_note.write_text(
    "---\nid: evt-x\nstatus: dropped\nenriched: false\n"
    "dropped_at: '2026-07-20T00:00:00+00:00'\ndrop_reason: 人工判定不追\n"
    "value: 71\n---\n\n## 事實\n潤好的字\n", encoding="utf-8")
_cm.patch_coverage(_pc_note, "backfilled")
_pc_fm = _yaml.safe_load(_pc_note.read_text("utf-8").split("---")[1])
acase("patch_coverage：只改 coverage 一格，status / dropped_at / drop_reason / value"
      "與 body 全部原樣（人工判定不能被一個「加欄位」的改動洗掉）",
      [_pc_fm.get("coverage"), _pc_fm.get("status"), _pc_fm.get("drop_reason"),
       _pc_fm.get("value"), "潤好的字" in _pc_note.read_text("utf-8")],
      ["backfilled", "dropped", "人工判定不追", 71, True])

_cv_tmp = _pathlib.Path(_tempfile.mkdtemp())
acase("load_first_fetch：沒有 state.json 回空 dict，而空 dict 讓每則判 unknown"
      "——設定讀不到的時候規則要變嚴不是變鬆（跟 lib/dictgaps.thresholds() 同一條）",
      [_cm.load_first_fetch(_cv_tmp),
       _covlib.coverage_of("2026-07-25T00:00:00+00:00", _CV_EV_A,
                           _cm.load_first_fetch(_cv_tmp))], [{}, "unknown"])
(_cv_tmp / "state.json").write_text("{ not json", encoding="utf-8")
acase("load_first_fetch：state.json 壞掉回空 dict，不得爆炸",
      _cm.load_first_fetch(_cv_tmp), {})
(_cv_tmp / "state.json").write_text(
    '{"src-a": {"first_fetch_at": "2026-07-23T23:52:35+00:00"}, "src-x": null}',
    encoding="utf-8")
acase("load_first_fetch：state.json 裡的 null 條目不得害整份掛掉",
      _cm.load_first_fetch(_cv_tmp), {"src-a": "2026-07-23T23:52:35+00:00"})

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
# 中文標題也是 sticky 欄位：event_markdown() 整份重寫 frontmatter，沒帶過去就沒了。
# 這是第三、第四個踩到這個坑的欄位（前兩個是 ingested_at 與 backfill 旗標）。
# 在第二輪之前先把譯文寫進去，第二輪之後它要還在。
_t_before = _made[0].read_text("utf-8")
_made[0].write_text(
    _t_before.replace("\nstatus:", "\ntitle_zh: 一句中文標題\ntitle_zh_src: deadbeef1234\n"
                      "recovered_by: identity-repair-2026-08-12\nstatus:", 1),
    "utf-8")

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
acase("pulse-cluster 跑第二輪：中文標題也活下來"
      "（title_zh 沒帶過去的話，潤稿端翻好的標題會在下一班被抹掉，"
      "而且它會安靜地重新排進待譯清單——每晚翻一次、每晚被洗掉一次）",
      ["title_zh: 一句中文標題" in _txt2, "title_zh_src: deadbeef1234" in _txt2],
      [True, True])
# 第五個踩到 sticky 坑的欄位。被抹掉的後果特別隱蔽：一則補寫的 Event 會在
# 下一次整份重寫時**變回看起來像自己長出來的**，而 recovered_by 存在的唯一
# 理由就是讓它別看起來像那樣。規格 references/obsidian-schema.md〈recovered_by〉。
acase("pulse-cluster 跑第二輪：recovered_by 也活下來"
      "（被抹掉的話，補寫的事件會安靜地變回「看起來是這條鏈自己長出來的」）",
      ["recovered_by: identity-repair-2026-08-12" in _txt2,
       "recovered_by: null" in _txt2], [True, False])
acase("event_markdown：沒補寫過的 Event 這一格是 null，不是缺席"
      "（省略的話，讀的人分不出「沒補寫過」與「這個版本還沒有這個欄位」）",
      "recovered_by:" in _txt, True)

# ── 身分修復遷移（references/incidents/2026-08-12-identity-repair.md）──
#
# 這支是一次性腳本，但它會**改既有資料**，所以兩道欄杆要有測試釘住。
_mgs = importlib.util.spec_from_file_location(
    "mig_identity", os.path.join(_HERE, "migrate-2026-08-12-identity-repair.py"))
_mg = importlib.util.module_from_spec(_mgs)
_mgs.loader.exec_module(_mg)

acase("身分修復：只在「現值等於舊還原法的產出」時才改標題"
      "（拿新還原法直接覆蓋的話，人手改過的標題會被機器版本蓋掉，"
      "而且沒有任何地方會顯示它被蓋過）",
      [_mg.retitle("https://www.anthropic.com/news/claude-opus-4-5",
                   "Claude Opus 4 5", "sitemap"),
       _mg.retitle("https://www.anthropic.com/news/claude-opus-4-5",
                   "人手改過的標題", "sitemap"),
       _mg.retitle("https://www.anthropic.com/news/claude-opus-4-5",
                   "Claude Opus 4 5", "rss")],
      ["Claude Opus 4.5", None, None])

# 冪等：跑第二次要什麼都不做。**這一條抓到過一個真的 bug**——第一版把
# 「標題改了」漏出髒集合，於是只改標題、沒有錯掛證據的那幾則改在記憶體裡
# 沒落地，報告說改了、檔案沒改。沒有任何斷言看得出來，是跑第二次看出來的。
_mvault = Path(tempfile.mkdtemp())
(_mvault / "Events").mkdir()
(_mvault / "_probe").mkdir()
(_mvault / "_corpus").mkdir()
shutil.copytree(os.path.join(_HERE, "..", "_config"), _mvault / "_config")
(_mvault / "Events" / "evt-2026-07-22-aaaaaa.md").write_text(
    "---\n" + _yaml.safe_dump({
        "id": "evt-2026-07-22-aaaaaa", "slug": "claude-haiku-4-5-aaaa",
        "title": "Claude Haiku 4 5", "date": "2026-07-22",
        "happened_at": "2026-07-22T01:05:15+00:00", "status": "published",
        "fingerprint": "anthropic:claude:haiku:4", "facet": "update",
        "evidence": [{"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/claude-haiku-4-5",
                      "title": "Claude Haiku 4 5", "relevance": 100,
                      "published": "2026-07-22T01:05:15.000Z",
                      "suspected_repost": False},
                     {"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/claude-opus-4-7",
                      "title": "Claude Opus 4.7", "relevance": 33,
                      "published": "2026-07-23T04:19:56.000Z",
                      "suspected_repost": False}],
    }, allow_unicode=True, sort_keys=False) + "---\n\n內文\n", "utf-8")
# 第二則專門隔離「只有 Event 標題要改」那條路：證據標題已經是對的
# （人手修過），所以證據那一圈不會標髒。第一版的 fixture 沒有這一則，
# 於是 M259 那條變異跑成 regression——測試看起來在守，其實是被隔壁那圈救的。
(_mvault / "Events" / "evt-2026-07-22-bbbbbb.md").write_text(
    "---\n" + _yaml.safe_dump({
        "id": "evt-2026-07-22-bbbbbb", "slug": "claude-opus-4-8-bbbb",
        "title": "Claude Opus 4 8", "date": "2026-07-22",
        "happened_at": "2026-07-22T01:28:45+00:00", "status": "published",
        "fingerprint": "anthropic:claude:opus:4", "facet": "update",
        "evidence": [{"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/claude-opus-4-8",
                      "title": "Claude Opus 4.8", "relevance": 100,
                      "published": "2026-07-22T01:28:45.000Z",
                      "suspected_repost": False}],
    }, allow_unicode=True, sort_keys=False) + "---\n\n內文\n", "utf-8")


# 第三則：帶一筆身分衝突的證據，而且它的 relevance 是**對舊標題**算的。
# 搬到正確的事件之後那個數字必須重算——33 是「跟 Sonnet 5 有多像」，
# 對 Opus 4.8 而言它其實是 100。不重算的話那一格會留著一個看起來有意義、
# 其實在講另一件事的值。
(_mvault / "Events" / "evt-2026-07-22-cccccc.md").write_text(
    "---\n" + _yaml.safe_dump({
        "id": "evt-2026-07-22-cccccc", "slug": "claude-sonnet-5-cccc",
        "title": "Claude Sonnet 5", "date": "2026-07-22",
        "happened_at": "2026-07-22T01:20:28+00:00", "status": "published",
        "fingerprint": "anthropic:claude:sonnet:5", "facet": "update",
        "evidence": [{"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/claude-sonnet-5",
                      "title": "Claude Sonnet 5", "relevance": 100,
                      "published": "2026-07-22T01:20:28.000Z",
                      "suspected_repost": False},
                     # 這一筆的 URL **刻意跟 bbbbbb 自己那筆不同**：同 URL 會被
                     # 去重、根本不會被附上去，那樣「搬家後重算 relevance」那條
                     # 斷言讀到的是目的地原本就有的那一筆——一顆永遠綠的燈。
                     # 標題也刻意不同，讓重算後的值不是 100：
                     # {introducing, claude, opus} ∩ {claude, opus} = 2/3 → 67。
                     {"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/introducing-claude-opus-4-8",
                      "title": "Introducing Claude Opus 4.8", "relevance": 33,
                      "published": "2026-07-22T01:28:45.000Z",
                      "suspected_repost": False},
                     {"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/claude-opus-4-7",
                      "title": "Claude Opus 4.7", "relevance": 33,
                      "published": "2026-07-23T04:19:56.000Z",
                      "suspected_repost": False}],
    }, allow_unicode=True, sort_keys=False) + "---\n\n內文\n", "utf-8")


# 第四則，也是 M259 真正的隔離組：**既不是搬家的來源、也不是目的地**。
# 前面 bbbbbb 兩度失去隔離性——第一次是它的證據標題也要重推導、
# 第二次是它變成了搬家的目的地——兩次都靠變異盤點才發現斷言在測空氣。
# 這一則的證據標題已經是對的、指紋跟事件一致，所以「標題那一圈標髒」
# 是它唯一的落地理由。
(_mvault / "Events" / "evt-2026-07-21-dddddd.md").write_text(
    "---\n" + _yaml.safe_dump({
        "id": "evt-2026-07-21-dddddd", "slug": "claude-sonnet-4-6-dddd",
        "title": "Claude Sonnet 4 6", "date": "2026-07-21",
        "happened_at": "2026-07-21T23:52:43+00:00", "status": "published",
        "fingerprint": "anthropic:claude:sonnet:4", "facet": "update",
        "evidence": [{"source_id": "src-anthropic-news",
                      "url": "https://www.anthropic.com/news/claude-sonnet-4-6",
                      "title": "Claude Sonnet 4.6", "relevance": 100,
                      "published": "2026-07-21T23:52:43.000Z",
                      "suspected_repost": False}],
    }, allow_unicode=True, sort_keys=False) + "---\n\n內文\n", "utf-8")


def _mig_run(apply_it):
    _a, _e2 = sys.argv[:], os.environ.get("VAULT_DIR")
    sys.argv = ["m"] + (["--apply"] if apply_it else [])
    os.environ["VAULT_DIR"] = str(_mvault)
    _buf = io.StringIO()
    try:
        with _c2.redirect_stdout(_buf):
            _mg.main()
    finally:
        sys.argv = _a
        if _e2 is not None:
            os.environ["VAULT_DIR"] = _e2
    return _buf.getvalue()


_m1 = _mig_run(True)
_m2 = _mig_run(False)
acase("身分修復：只改了標題、沒有錯掛證據的那則也要真的落地"
      "（第一版漏了這一格：報告說改了、檔案沒改）",
      "title: Claude Haiku 4.5" in
      (_mvault / "Events" / "evt-2026-07-22-aaaaaa.md").read_text("utf-8"), True)
acase("身分修復：標題改了，fingerprint 要跟著改"
      "（只改標題不改指紋，這則從此對不上自己的證據）",
      "fingerprint: anthropic:claude:haiku:4.5" in
      (_mvault / "Events" / "evt-2026-07-22-aaaaaa.md").read_text("utf-8"), True)
acase("身分修復：**只有** Event 標題要改的那則也要落地"
      "（證據標題已經對了、指紋也一致 → 既不是搬家來源也不是目的地。"
      "少了標題那圈自己標髒，這則會改在記憶體裡不落地，而報告會說它改了）",
      ["title: Claude Sonnet 4.6", "fingerprint: anthropic:claude:sonnet:4.6"],
      [x for x in ["title: Claude Sonnet 4.6",
                   "fingerprint: anthropic:claude:sonnet:4.6"]
       if x in (_mvault / "Events" / "evt-2026-07-21-dddddd.md").read_text("utf-8")])
acase("身分修復：證據搬家之後 relevance 要對新標題重算"
      "（relevance 的不變式是「證據標題與事件標題的相似度」，"
      "搬家不重算就留下一個看起來有意義、其實在講另一件事的數字）",
      [(e["relevance"], e["title"]) for e in _yaml.safe_load(
          (_mvault / "Events" / "evt-2026-07-22-bbbbbb.md").read_text("utf-8")
          .split("---")[1])["evidence"]],
      [(100, "Claude Opus 4.8"), (67, "Introducing Claude Opus 4.8")])
# 同一個 URL 從兩則事件被搬到同一個補寫的 Event：add_evidence 依
# (source_id, url) 去重，所以實際只會有一筆。帳目要記實際附上的那個數字——
# **報告多報比少報更難發現**，因為看起來像是資料比較豐富。
_mrep = _json.loads(
    (_mvault / "_probe" / "identity-repair-2026-08-12.json").read_text("utf-8"))
acase("身分修復：補寫的 Event 帳目記實際附上的證據數，不是蒐集到的筆數"
      "（同一個 URL 從兩則事件搬過來會被去重，帳目報兩筆就是在多報）",
      [(c["title"], c["evidence"]) for c in _mrep["created"]],
      [("Claude Opus 4.7", 1)])
# 冪等要冪等到帳目那一層。第一版的帳目寫在 --apply 的無條件路徑上，
# 於是「第二次跑（正確地什麼都沒做）」會把第一次的紀錄整份覆蓋成全 0——
# 一份說謊的帳目比沒有帳目更糟：沒有的時候人會去翻 diff，有的時候人會相信它。
# 2026-08-12 真的在 main 上踩到，全 0 的那份還進了 commit。
_mrep_before = (_mvault / "_probe" / "identity-repair-2026-08-12.json").read_text("utf-8")
_mig_run(True)
acase("身分修復：沒事可做的重跑不得把上一次的帳目洗掉"
      "（資料層冪等不等於帳目冪等——第二次 --apply 覆蓋成全 0，"
      "會留下一份寫著「什麼都沒做」的紀錄躺在一個改了幾十個檔的 commit 旁邊）",
      (_mvault / "_probe" / "identity-repair-2026-08-12.json").read_text("utf-8"),
      _mrep_before)
acase("身分修復：可重跑——第二次應該什麼都不寫"
      "（一次性遷移只跑一次就不會有人發現它沒落地，冪等是唯一看得見的訊號）",
      "要寫的檔：0" in _m2, True)

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

# ── 同語言逐字轉載（references/attach-rule.md〈順序〉）──
# P0-e 量到：現行 attach 規則唯一黏得上的兩篇第三方後續，兩篇的標題相似度都是
# 1.00 —— 系統唯一收得到的「第二個獨立來源」正好是最不獨立的那一種，
# 而上面那支跨語言守門的第一個條件就是「語言不同」，它在旁邊看著。
_VR = _yaml.safe_load(open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
                           encoding="utf-8"))["evidence"]["verbatim_repost"]


def _vrow(title, hour, tier=2, day=4):
    from datetime import datetime as _dt2
    return {"title": title, "tier": tier,
            "published": _dt2(2026, 8, day, hour, tzinfo=_tz.utc)}


_VR_A = _vrow("AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency", 13, tier=1)
acase("逐字轉載：同語言、標題一字不差、47 小時後 → 後發的判成轉載"
      "（實測那兩篇就是這個形狀，而跨語言那支攔不到）",
      _cl.verbatim_reposts([_VR_A, _vrow(
          "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency", 12, day=6)],
          _VR), {1})
acase("逐字轉載：改寫過的標題不判"
      "（兩家各自重寫是兩個真的聲音；判成轉載等於把獨立性做假到反方向——"
      "而 P0-e 量到 12/14 的第三方後續正是這一類）",
      _cl.verbatim_reposts([_VR_A, _vrow(
          "AI industry unveils SAFE cybersecurity disclosure framework", 18)], _VR), set())
acase("逐字轉載：超出 window_hours 不判（168 小時真的被讀）",
      _cl.verbatim_reposts([_VR_A, _vrow(
          "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency", 13, day=20)],
          _VR), set())
acase("逐字轉載：title_similarity_min 真的被讀（拉到 1.01 就沒有任何一對過得了）",
      _cl.verbatim_reposts([_VR_A, _vrow(
          "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency", 12, day=6)],
          {**_VR, "title_similarity_min": 1.01}), set())
acase("逐字轉載：enabled: false 是真的關掉",
      _cl.verbatim_reposts([_VR_A, _vrow(
          "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency", 12, day=6)],
          {**_VR, "enabled": False}), set())
acase("逐字轉載：缺標題或缺時間一律不判（往「維持原本算法」倒，"
      "捏造一個「它們是同一篇」的結論比漏抓一次更難發現）",
      [_cl.verbatim_reposts([_VR_A, _vrow("", 12, day=6)], _VR),
       _cl.verbatim_reposts([_VR_A, {**_vrow("AI Leaders Propose SAFE Guidelines "
                                             "for Cybersecurity Transparency", 12),
                                     "published": None}], _VR)],
      [set(), set()])
acase("逐字轉載：原文＝最早發布的那一條（同 suspected_reposts 的三段排序，"
      "確定性，同一份輸入永遠給同一個答案）",
      _cl.verbatim_reposts([_vrow("Third-party cyber evaluations involving OpenAI models", 19, day=6),
                            _vrow("Third-party cyber evaluations involving OpenAI models", 12, day=5)],
                           _VR), {0})
acase("gate.yaml: evidence.verbatim_repost 這一塊真的在（判準讀不到就靜靜不判）",
      sorted(_VR), ["enabled", "excluded_from", "title_similarity_min", "window_hours"])
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

# 端到端：判準寫好了不等於接上了。第四十輪的教訓是「規則存在 ≠ 規則被套用」，
# 而 M240/M242 第一版就是靠這一段才被殺——上面那幾條只測 lib 裡的純函式，
# 把 pulse-cluster 那一行接線拿掉，它們一條都不會紅。
_VRSRC = {"src-orig": {"tier": 1, "media_group": "NVIDIA", "language": "en"},
          "src-copy": {"tier": 3, "media_group": "Medium", "language": "en"}}


def _vr_event():
    e = _cm.Event("evt-vr", "vr",
                  "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency",
                  "2026-08-04T13:00:00+00:00")
    e.add_evidence("src-orig", "https://nvidia.test/safe",
                   "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency",
                   100, "2026-08-04T13:00:00+00:00")
    e.add_evidence("src-copy", "https://medium.test/safe",
                   "AI Leaders Propose SAFE Guidelines for Cybersecurity Transparency",
                   40, "2026-08-06T12:00:00+00:00")
    return e


_vr_ev = _vr_event()
_cm.rescore(_vr_ev, _VRSRC, None, _TC, _ENT_TABLE, vr_cfg=_VR)
acase("逐字轉載：走 rescore 之後真的扣得到分"
      "（這是 P0-e 量到的那個形狀——兩篇標題一字不差、不同媒體集團，"
      "在這一版之前它們會讓 independent_sources 從 1 變成 2）",
      [_vr_ev.scores["independent_sources"], _vr_ev.scores["suspected_reposts"],
       [e["suspected_repost"] for e in _vr_ev.evidence]],
      [1, 1, [False, True]])
_vr_ev2 = _vr_event()
_cm.rescore(_vr_ev2, _VRSRC, None, _TC, _ENT_TABLE, vr_cfg={**_VR, "enabled": False})
acase("逐字轉載：關掉之後獨立性回到 2（反方向，確認上面那條不是恆為 1）",
      [_vr_ev2.scores["independent_sources"], _vr_ev2.scores["suspected_reposts"]],
      [2, 0])
_vr_ev3 = _vr_event()
_cm.rescore(_vr_ev3, _VRSRC, None, _TC, _ENT_TABLE,
            vr_cfg={**_VR, "excluded_from": ["heat"]})
acase("逐字轉載：excluded_from 走的是兩支的聯集——這一支沒列 "
      "independent_sources 而跨語言那支列了，所以照樣扣"
      "（少了聯集就會出現「標記在那裡但沒有人扣分」）",
      [_vr_ev3.scores["independent_sources"],
       [e["suspected_repost"] for e in _vr_ev3.evidence]],
      [1, [False, True]])
# 反過來也要成立：只有逐字那一支列了 independent_sources 的時候，
# 聯集才是唯一不會靜靜漏掉一邊的選法。少了聯集這一格會退回 2。
_vr_ev4 = _vr_event()
_cm.rescore(_vr_ev4, _VRSRC, None, {**_TC, "excluded_from": ["heat"]}, _ENT_TABLE,
            vr_cfg=_VR)
acase("逐字轉載：只有這一支列 independent_sources 時照樣扣得到"
      "（排除清單取聯集，不是只讀跨語言那一份）",
      _vr_ev4.scores["independent_sources"], 1)

# ── attach 門檻搬進 gate.yaml 並降到 0.30（references/attach-rule.md）──
# P0-e：0.46 在 14 篇真實第三方後續裡只黏得上 2 篇，而那 2 篇都是逐字轉載。
_AR_TH = _yaml.safe_load(open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
                              encoding="utf-8"))["cluster"]["title_similarity_min"]
_AR_CAND = ("Meta's 'Open Source' Muse Glimmer Model Can Run On A Single Computer",
            "2026-08-10T18:00:00+00:00")
_AR_EV = ("Meta is back with Muse Glimmer: local, agentic, multimodal, and open source",
          "2026-08-10T00:00:00+00:00")
acase("attach 門檻：gate.yaml 的 cluster.title_similarity_min 是 0.30"
      "（在此之前它寫死在 belongs_to_event 的預設參數裡，設定檔沒有這一格）",
      _AR_TH, 0.30)
acase("attach 門檻：0.30 黏得上真實的第三方改寫，0.46 黏不上"
      "（實測語料：Engadget 對 Hugging Face 官方那篇，相似度 0.33）",
      [_cl.belongs_to_event(*_AR_CAND, *_AR_EV, _AR_TH),
       _cl.belongs_to_event(*_AR_CAND, *_AR_EV, 0.46)],
      [True, False])
acase("attach 門檻：pulse-cluster 真的把它讀出來"
      "（判準寫在設定檔但沒人讀，就是這個 repo 抓過很多次的假旋鈕）",
      _cm.load_title_similarity_min(_P2(os.path.join(_HERE, "..", "_config"))), 0.30)
# 讀出來還要真的用在聚類那一步。attach_target 的 sim_min 沒有預設值，
# 所以「忘記傳」在語法上就會炸，不會安靜地退回某個內建數字。
_AR_EVS = [_cm.Event("evt-mg", "mg", _AR_EV[0], _AR_EV[1])]
acase("attach 門檻：真的用在聚類那一步（0.30 掛得上、0.46 掛不上，同一組輸入）",
      [getattr(_cm.attach_target(*_AR_CAND, _AR_EVS, 0.30), "id", None),
       getattr(_cm.attach_target(*_AR_CAND, _AR_EVS, 0.46), "id", None)],
      ["evt-mg", None])
acase("attach 門檻：設定檔讀不到要退回**舊的 0.46**，不是退回 0.30"
      "（設定檔壞掉時規則要變嚴不是變鬆——在 YAML 打錯字的那天悄悄放寬聚類，"
      "汙染會混進 independent_sources 而沒有人知道）",
      [_cm.load_title_similarity_min(_P2("/nonexistent-cfg-dir")),
       _cl.DEFAULT_TITLE_SIMILARITY_MIN],
      [0.46, 0.46])

# ── 身分否決：結構化事實不准被模糊相似覆寫（2026-08-12）──
#
# 這一組全部用**真實發生過的污染案例**，不是造的。
# evt-2026-07-25-0fa594「Claude Opus 5」的 primary_evidence 是 5，
# 其中 4 筆是 Opus 4.5 / 4.6 / 4.7 / 4.8，全部 relevance 100，
# 而它的 confidence 是全 vault 最高的 100。規格 references/attach-rule.md。
_IV_5 = ("Claude Opus 5", "2026-07-25T02:03:36+00:00")
_IV_47 = ("Claude Opus 4.7", "2026-07-23T04:19:56+00:00")
_IV_46 = ("Claude Opus 4.6", "2026-07-22T00:06:14+00:00")
_IV_45 = ("Claude Opus 4.5", "2026-07-23T04:09:31+00:00")
_IV_48 = ("Claude Opus 4.8", "2026-07-22T01:28:45+00:00")

acase("身分否決：Claude Opus 4.7 不得掛進 Claude Opus 5"
      "（標題 token 集合完全相同、相似度 1.00——這就是那 6 筆 relevance 100 的來源）",
      _cl.belongs_to_event(*_IV_47, *_IV_5, 0.30), False)

acase("身分否決：反向也一樣（Opus 5 不得掛進 Opus 4.7）"
      "（否決要對稱，不然掛不掛得上會取決於誰先進 vault）",
      _cl.belongs_to_event(*_IV_5, *_IV_47, 0.30), False)

# 這一條的成功標準很容易被漏掉，而少了它會誤報成功：只加 veto 不修 slug 的話，
# 四則 4.x 的 fingerprint 全是 opus:4，veto 對它們之間不觸發，
# 它們會改走路徑 A 合併成一則、relevance 全部 100——錯誤只是換了個形狀。
acase("身分否決：Opus 4.5 / 4.6 / 4.7 / 4.8 四次發布不得互相合併"
      "（只驗「4.x 不進 5」會漏掉這個形狀——它們本來就是四件事）",
      [_cl.belongs_to_event(*a, *b, 0.30)
       for a, b in [(_IV_48, _IV_47), (_IV_48, _IV_46), (_IV_48, _IV_45),
                    (_IV_47, _IV_46), (_IV_47, _IV_45), (_IV_46, _IV_45)]],
      [False] * 6)

acase("身分否決：正向不得被砍（Introducing Claude Opus 5 仍要掛得上 Claude Opus 5）"
      "（一條只會拒絕的規則很容易全綠——要有一條證明它還讓對的通過）",
      _cl.belongs_to_event("Introducing Claude Opus 5", "2026-07-25T03:00:00+00:00",
                           *_IV_5, 0.30), True)

acase("身分否決：只有兩邊都說得出版本才否決，單邊 None 照走 fallback"
      "（_FP_PATTERNS 是寫死的 11 個家族白名單，None 是「這支正則不認得」，"
      "不是「這不是那個模型」——拿「我不認得」去否決會砍掉整批第三方報導）",
      [_cl.event_fingerprint("Anthropic ships pricing changes"),
       _cl.belongs_to_event("Claude Opus 5 pricing changes", "2026-07-25T05:00:00+00:00",
                            "Anthropic ships pricing changes", "2026-07-25T02:00:00+00:00",
                            0.30)],
      [None, True])

# 為什麼 slug 還原必須跟這條 veto 同一輪：沒有小數點，版號組吃到第一個整數就停。
acase("身分否決的前提：版號要進得了 fingerprint"
      "（`Claude Opus 4 5` 少了小數點 → opus:4，四次發布塌成同一個鍵，veto 因此失效）",
      [_cl.event_fingerprint("Claude Opus 4.5"),
       _cl.event_fingerprint("Claude Opus 4 5"),
       _cl.event_fingerprint("Claude Opus 5")],
      ["anthropic:claude:opus:4.5", "anthropic:claude:opus:4",
       "anthropic:claude:opus:5"])

# ── sitemap 還原：URL 的 `-` 同時是斷詞符與小數點 ──
# 規格 references/title-provenance.md。
acase("slug 還原：版號的小數點要還原回來"
      "（sitemap 沒有標題欄位，這幾條來源的標題全是從 URL 推導的）",
      [_pp._slug_to_title("https://www.anthropic.com/news/claude-opus-4-5"),
       _pp._slug_to_title("https://www.anthropic.com/news/claude-sonnet-4-6"),
       _pp._slug_to_title("https://x.ai/news/grok-4-5-everywhere")],
      ["Claude Opus 4.5", "Claude Sonnet 4.6", "Grok 4.5 Everywhere"])

acase("slug 還原：沒有版號的照舊，不得無中生有小數點",
      _pp._slug_to_title("https://www.anthropic.com/news/claude-opus-5"),
      "Claude Opus 5")

acase("slug 還原：年份型 slug 不得被當成版號"
      "（`2026-08-03` 變成 `2026.08.03` 會讓一整批部落格標題變形，"
      "而那種變形不會讓任何東西變紅——它只會安靜地改變相似度）",
      [_pp._slug_to_title("https://example.invalid/blog/2026-08-03"),
       _pp._slug_to_title("https://example.invalid/a/webb-telescope-2026-08-moons")],
      ["2026 08 03", "Webb Telescope 2026 08 Moons"])

acase("slug 還原：文章編號不得被當成版號（右邊限 1–2 位數的理由）",
      _pp._slug_to_title(
          "https://example.invalid/x/harvard-study-links-glp-1-123000637.html"),
      "Harvard Study Links Glp 1 123000637")

acase("slug 還原：併過的結果不再參與下一輪（不無限往右吃）",
      _pp._slug_to_title("https://example.invalid/n/a-1-2-3-4"), "A 1.2 3 4")

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
# 時間軸的年月分組要跟卡片上印的日期同一個時鐘。M78 第一輪活下來的理由是「值一樣」，
# M81 活下來的理由不同：**我釘了 fmt_date 換算對不對，沒釘拿它去分組的那一端。**
# 第九次同一個形態（釘判準沒釘消費端）。一則 UTC 07-31、台北 08-01 的事件，
# 分組走儲存日的話，卡片上會寫著 2026-08-01、卻躺在「7 月」底下。
_tl_ev = {"id": "evt-2026-07-31-aaaaaa", "slug": "x-aaaa", "title": "T",
          "date": "2026-07-31", "date_display": "2026-08-01", "company": "C",
          "category": "", "track": "models", "summary": "S",
          "confidence": 80, "heat": None, "title_zh": None}
_tl_html = _rmod.build_timeline([_tl_ev], "now")
acase("pulse-render.build_timeline：分組跟著**顯示日**走"
      "（UTC 07-31 / 台北 08-01 的事件要進「8 月」，"
      "不是印著 08-01 卻掛在 7 月底下）",
      ["2026 · 8 月" in _tl_html, "2026 · 7 月" in _tl_html,
       "<time>2026-08-01</time>" in _tl_html],
      [True, False, True])

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

# ── 潤稿鏈的死人開關：由推得上去的那一邊，監看推不上去的那一邊 ──────
# 2026-08-05：半夜潤稿那條 Cowork 鏈把活做完了、commit 也建了，但 push 被沙箱的
# git proxy 擋掉（403）。容器是拋棄式的，那一晚的成果等於沒了——而現有三個警報
# **一條都沒叫**，因為判準各自對得上別的故障：未 enrich 是 0、中文覆蓋 31/35 不是
# 0、health 那一頁是 Actions 自己寫的。兩條鏈的失效模式不一樣，警報只長在其中一條。
acase("潤稿鏈：超過門檻要叫，門檻內不叫（日更的鏈，隔一天是誤點，隔兩天是壞了）",
      [_mon.enrich_chain_line("2026-08-04", "ok", "2026-08-05", 2)[1],
       _mon.enrich_chain_line("2026-08-04", "ok", "2026-08-06", 2)[1],
       "2 天前" in _mon.enrich_chain_line("2026-08-04", "ok", "2026-08-06", 2)[0]],
      [False, True, True])
# 淺 checkout 裡 git log --grep 什麼都找不到，而「找不到」跟「很久沒有」在數字上
# 長得一模一樣。回一個大 lag 會變成天天叫的假警報，而天天叫的警報跟不會叫的
# 一樣沒有資訊——所以量不到就說量不到，且不觸警（紅線 8）。
acase("潤稿鏈：淺 checkout 判成「量不到」且不觸警，不是判成一個很大的 lag"
      "（fetch-depth: 1 裡找不到 enrich commit，而那跟「很久沒推回」數字上一樣）",
      [_mon.enrich_chain_line(None, "shallow", "2026-08-06", 2),
       _mon.enrich_chain_line(None, "no-git", "2026-08-06", 2)[1]],
      [(_mon.enrich_chain_line(None, "shallow", "2026-08-06", 2)[0], False), False])
acase("潤稿鏈：淺 checkout 那句話要指得出怎麼修（不然讀的人只知道量不到）",
      ["fetch-depth" in _mon.enrich_chain_line(None, "shallow", "x", 2)[0],
       "量不到" in _mon.enrich_chain_line(None, "shallow", "x", 2)[0]], [True, True])
# 「從來沒推回過」跟「淺 checkout」是兩件事：前者是潤稿鏈真的沒動，要叫；
# 後者是這支腳本的環境沒設對，不該叫。擠成同一種就等於這一格不存在。
acase("潤稿鏈：「從來沒推回過」要叫，跟「量不到」分開"
      "（擠成同一種，第一天就會誤報，而真的斷掉那天反而不叫）",
      [_mon.enrich_chain_line(None, "none", "2026-08-06", 2)[1],
       _mon.enrich_chain_line(None, "shallow", "2026-08-06", 2)[1]], [True, False])
# 負數的 lag。`lag >= 門檻` 對它是沉默的（-1 >= 2 為假 → 綠燈），而且時間往前走
# 只會更綠，這個洞**不會自癒**。〈三條規則〉第 3 條早就為 stale_after_days 寫過
# 同一句，而 enrich_chain_line 是後來新接的第二個消費者、沒有一起拿到那條規則
# ——同一個形狀這個 repo 量到第六次。
# 成因最常見的不是時鐘：是有人在**推不上去的那一邊**開了這支旗標，那一邊會讀到
# 自己剛建、還沒推出去的那顆 commit（實測 2026-08-07：回「-1 天前」、不叫）。
_neg = _mon.enrich_chain_line("2026-08-07", "ok", "2026-08-06", 2)
acase("潤稿鏈：日期在未來的 enrich commit 要叫，不能因為 lag 是負數就綠"
      "（-1 >= 2 為假 → 靜靜綠燈，而且時間往前走只會更綠，這個洞不會自癒）",
      [_neg[1], "-1 天前" in _neg[0], "不算數" in _neg[0]],
      [True, False, True])
# 訊息要自成一種：既不跟「超過門檻」混（那是鏈斷了），也不借用「量不到」那個詞
# （那個詞在這支腳本裡保留給不觸警的淺 clone / 非 git）。混用會讓讀的人以為
# 這一格不叫，然後往錯的方向找。
acase("潤稿鏈：未來日期那句要自成一種，不跟「超過門檻」也不跟「量不到」混"
      "（一個是鏈斷了、一個是這一格算不得數，要人做的事不一樣）",
      ["超過門檻" in _neg[0], "量不到" in _neg[0], "推不上去的那一邊" in _neg[0]],
      [False, False, True])
# 判準對而呼叫端沒接，警報一樣不會叫——這條分支上已經抓過一次（M198）。
_md_enr = _mm.render_health(_r3, dict(_h_green, enrich_stale_after_days=2),
                            None, None, ("2026-06-01", "ok"))
acase("潤稿鏈：那一格真的印在看板上，而且超過門檻時帶警告記號"
      "（走真的 render_health——純函式對而呼叫端沒接，這一格等於不存在）",
      ["半夜潤稿那條鏈" in _md_enr, "⚠" in _md_enr.split("半夜潤稿那條鏈")[1][:200]],
      [True, True])
# last_enrich_commit 自己也要有判準——上面那幾條餵的是手寫的 reason，
# 而**產生那個 reason 的碼沒有任何東西在守**。M200 就是這樣活下來的：
# 把偵測淺 clone 那一段拿掉，六條判準一條都不紅。所以這裡真的建 repo 出來問它。
#
# **四個 fixture 全部現場造，一個都不看「這份 selftest 正在哪個 checkout 裡跑」。**
# 第一版拿 repo 自己當「完整 clone」那一格——本機跑得好好的，進 CI 就紅了：
# `mutation.yml` 的 checkout 沒設 fetch-depth，預設是淺的，於是那一格量到
# "shallow" 而不是 "ok"，基準線一垮 mutate.py 當場收工（實測 14 秒就紅）。
# 判準去問環境、而不是去問被判的那個東西——這條分支上第五次同一個形狀。
def _mk_enrich_repo(path, with_enrich=True):
    """造一個小 git repo。gpgsign / user 都在指令上帶，不吃全域設定。"""
    g = ["git", "-c", "commit.gpgsign=false", "-c", "user.name=t",
         "-c", "user.email=t@e", "-C", str(path)]
    path.mkdir(parents=True, exist_ok=True)
    _subprocess.run(g + ["init", "-q", "-b", "main"], capture_output=True)
    (path / "a.txt").write_text("1", "utf-8")
    _subprocess.run(g + ["add", "-A"], capture_output=True)
    _subprocess.run(g + ["commit", "-q", "-m", "chore: base"], capture_output=True)
    (path / "a.txt").write_text("2", "utf-8")
    _subprocess.run(g + ["add", "-A"], capture_output=True)
    _subprocess.run(g + ["commit", "-q", "-m",
                         "nightly: enrich + narrative 2026-08-04" if with_enrich
                         else "chore: nightly refresh"], capture_output=True)
    return path


with _tf2.TemporaryDirectory() as _td_sh:
    _root = Path(_td_sh)
    _full = _mk_enrich_repo(_root / "full")
    _noen = _mk_enrich_repo(_root / "noenrich", with_enrich=False)
    _subprocess.run(["git", "clone", "--depth", "1", "-q",
                     "file://" + str(_full), str(_root / "shallow")], capture_output=True)
    _full_res = _mon.last_enrich_commit(_full)
    _sh_res = _mon.last_enrich_commit(_root / "shallow")
    _noen_res = _mon.last_enrich_commit(_noen)
    _nogit_res = _mon.last_enrich_commit(_root)
acase("潤稿鏈：last_enrich_commit 分得出四種情況（完整 / 淺 clone / 沒有 enrich commit / 非 git）"
      "——而且四個 fixture 都是現場造的，**不看這份 selftest 正在哪個 checkout 裡跑**"
      "（第一版拿 repo 自己當「完整」那一格，進了淺 checkout 的 CI 就紅）",
      [_full_res[1], _sh_res[1], _noen_res[1], _nogit_res[1],
       bool(_re.fullmatch(r"\d{4}-\d{2}-\d{2}", _full_res[0] or ""))],
      ["ok", "shallow", "none", "no-git", True])

# 這條檢查的是「旗標有沒有真的掛在夜班上」。判準寫得再好，沒有人開那個旗標，
# 它就只是一段不會執行的碼。
#
# **註解要先剝掉。** 第一版寫 `"--alert-enrich-stale" in 整份 yaml`，而那個旗標
# 在它上面的註解區塊裡也出現一次——把命令列那一行刪掉，判準照樣綠。
# 這條分支上第四次「判準抓到隔壁那一處」，四次都是在一整份文字裡找一個字串。
_WF_DR = open(os.path.join(_HERE, "..", ".github", "workflows", "data-refresh.yml"),
              encoding="utf-8").read()
_WF_DR_CODE = "\n".join(ln for ln in _WF_DR.splitlines()
                        if not ln.lstrip().startswith("#"))
acase("排程：夜班真的開了 --alert-enrich-stale，而且 checkout 拿得到 commit 歷史"
      "（判準量的是 git log；預設的淺 clone 裡它什麼都看不到）",
      ["--alert-enrich-stale" in _WF_DR_CODE, "fetch-depth: 0" in _WF_DR_CODE],
      [True, True])

# ── 2026-08-09：一個部署閘門把抓取鏈擋了四天 ────────────────────────────
# refresh job 掛著 environment: github-pages，那個環境的一條保護規則讓它停在
# Waiting 三天；concurrency: nightly 單槽且 cancel-in-progress: false，後面每一班
# 排隊到期被砍。main 四天沒進資料，而**現場沒有一盞燈是紅的**——這條鏈所有的警報
# 都住在它自己裡面，job 沒開始警報就沒開始。
# 經過見 references/incidents/2026-08-09-the-gate-that-stopped-the-chain.md。
_WF_PG = open(os.path.join(_HERE, "..", ".github", "workflows", "pages.yml"),
              encoding="utf-8").read()
_WF_PG_CODE = "\n".join(ln for ln in _WF_PG.splitlines()
                        if not ln.lstrip().startswith("#"))
acase("部署閘門不准擋資料鏈：data-refresh 不宣告 environment、也不自己部署"
      "（那條鏈的最後一步是 push 到 main，必然觸發 pages.yml——自己再部署一次是重複的，"
      "代價是兩支工作流搶同一個 environment）",
      ["environment:" in _WF_DR_CODE, "deploy-pages" in _WF_DR_CODE,
       "upload-pages-artifact" in _WF_DR_CODE],
      [False, False, False])
acase("部署只有一個主人：宣告 environment: github-pages 的工作流剛好一支"
      "（兩支搶同一個環境，其中一支卡住另一支就跟著停在 Waiting）",
      sorted(n for n, code in (("data-refresh.yml", _WF_DR_CODE),
                               ("pages.yml", _WF_PG_CODE))
             if "github-pages" in code),
      ["pages.yml"])
# 整份 workflow 以前一個 timeout-minutes 都沒有：卡住的那班燒滿預設 6 小時，
# 而單槽 concurrency 讓後面每一班陪葬。實測正常一班 8～14 分鐘。
acase("兩支工作流都有 timeout-minutes（沒有的話一次卡住會燒滿 6 小時，"
      "而 concurrency 是單槽——後面每一班跟著排隊到期被砍）",
      ["timeout-minutes" in _WF_DR_CODE, "timeout-minutes" in _WF_PG_CODE],
      [True, True])
# paths 清單跟 pulse-render 實際讀什麼會慢慢分岔，而分岔那天沒有任何東西會紅，
# 網站只是靜靜停在舊版本。render 是確定性的、分鐘級，寧可多跑幾次。
acase("pages.yml 不用 paths 過濾（清單跟渲染器讀什麼會分岔，而分岔那天不會有東西變紅）",
      [ln.strip() for ln in _WF_PG_CODE.splitlines() if ln.strip().startswith("paths:")],
      [])

# --alert-stale 的訊息尾巴以前是寫死的「跑班日期是今天而這裡紅了」，而 2026-08-09
# 那次它跟「最後一次跑班 2026-08-05」印在同一行——同一句話自相矛盾，還把人指向
# 「來源全死了」，實際上是鏈連跑都沒跑到。兩件事要做的動作完全相反。
_st_today = _mm.stale_alert_tail(0)
_st_old = _mm.stale_alert_tail(4)
_st_never = _mm.stale_alert_tail(None)
acase("死人開關：「今天跑過但沒東西」跟「根本沒跑到」的訊息要分開"
      "（前者去查來源，後者去查排程／CI——寫死成前者會讓人往反方向找一整晚）",
      ["鏈在跑" in _st_today, "鏈連跑都沒跑到" in _st_old,
       "鏈在跑" in _st_old, len({_st_today, _st_old, _st_never})],
      [True, True, False, 3])

# 同一條規矩的另一半：警報旗標**只准掛在推得上去的那一邊**。潤稿那一邊讀本地
# git log，會讀到自己剛剛建、還沒推出去的那顆 commit，然後回報一盞綠燈——
# 那正是這支旗標存在要抓的故障，由它自己來量就永遠是綠的。
#
# 只活在文件裡的規矩，會在有人「順手補齊」的那天消失，這個 repo 已經證明過很多次。
# 所以量的是**命令列**、不是整份文字：散文要能解釋為什麼不准（runbook 步驟 17
# 底下那段就是），所以只挑同時帶 `pulse-monitor` 與警報旗標的那幾行。
_RB_ENRICH = open(os.path.join(_HERE, "enrich-runbook.md"), encoding="utf-8").read()
_RB_ALERT_LINES = [ln.strip() for ln in _RB_ENRICH.splitlines()
                   if "pulse-monitor" in ln and "--alert" in ln]
acase("潤稿 runbook：步驟 17 不准帶警報旗標"
      "（那一邊推不上去，判準卻讀本地 git log——它會把自己沒推成功的那顆讀成推成功了）",
      _RB_ALERT_LINES, [])

import datetime as _hdt2  # noqa: E402

# ── 鏈外的死人開關（2026-08-11）──────────────────────────────────────
# 前面每一條警報都有一個共同前提：它自己要被執行到。2026-08-09 證明那個前提
# 不成立——四個判準全長在 data-refresh.yml 最後兩個 step 上，而那一班卡在
# 部署閘門、job 一個 step 都沒開始。這一支的價值**全部來自它跟被監看的那條鏈
# 分開**，所以判準守的是那幾個「分開」，不只是它算得對不對。
_wd_spec = importlib.util.spec_from_file_location(
    "pulse_watchdog", os.path.join(_HERE, "pulse-watchdog.py"))
_wd = importlib.util.module_from_spec(_wd_spec)
_wd_spec.loader.exec_module(_wd)
_D = _hdt2.date(2026, 8, 11)
acase("鏈外開關：四種結果分開——量不到／從來沒有／未來日期／超過門檻"
      "（擠成兩種的話，看到紅燈的人得自己猜是哪一種，而四種要做的事完全不同）",
      [_wd.verdict("x", "2026-08-10", 1, 2, "ok")[1],
       _wd.verdict("x", "2026-08-05", 6, 2, "ok")[1],
       _wd.verdict("x", None, None, 2, "ok")[1],
       _wd.verdict("x", "2026-08-20", -9, 2, "ok")[1],
       _wd.verdict("x", "2026-08-05", 6, 2, "shallow")[1]],
      [False, True, True, True, False])
acase("鏈外開關：未來日期那句要跟「太久沒有」分開（一個是鏈斷了，一個是日期壞了）",
      ["不算數" in _wd.verdict("x", "2026-08-20", -9, 2, "ok")[0],
       "超過門檻" in _wd.verdict("x", "2026-08-20", -9, 2, "ok")[0],
       "量不到" in _wd.verdict("x", "2026-08-05", 6, 2, "shallow")[0]],
      [True, False, True])
# 它的價值全部來自「分開」。這幾條守的是那幾個分開還在不在——
# 同一支 workflow、同一個 concurrency group、或掛上 environment，都會讓它
# 在 08-09 那種故障裡跟著沉默，而判準算得再對也沒用。
_WD_YML = open(os.path.join(_HERE, "..", ".github", "workflows", "watchdog.yml"),
               encoding="utf-8").read()
_WD_CODE = "\n".join(ln for ln in _WD_YML.splitlines() if not ln.lstrip().startswith("#"))
acase("鏈外開關：它必須是另一支 workflow、另一個 concurrency、不掛 environment"
      "（同一支裡加 step 完全沒用——job 沒開始，step 也不會開始）",
      ["group: watchdog" in _WD_CODE, "group: nightly" in _WD_CODE,
       "environment:" in _WD_CODE, "fetch-depth: 0" in _WD_CODE],
      [True, False, False, True])
# 不 import pipeline 模組：pulse-monitor.py 哪天語法壞掉，這一支要還跑得起來。
# 唯一准的是 lib.clock——取日期的唯一入口是紅線，抄第二份是這個 repo 量過的病。
_WD_SRC = open(os.path.join(_HERE, "pulse-watchdog.py"), encoding="utf-8").read()
acase("鏈外開關：只 import lib.clock，不碰任何 pipeline 模組"
      "（拿被監看那條鏈自己的碼去判斷它有沒有跑，等於問一個昏迷的人他醒著沒有）",
      sorted(set(_re.findall(r"^from lib import (\w+)", _WD_SRC, _re.M))
             | set(_re.findall(r"^from lib\.(\w+)", _WD_SRC, _re.M))),
      ["clock"])
# 門檻是另一個 key：共用的話，有人為了讓 monitor 安靜而調鬆它，會連這一支
# 一起調鬆——而這一支正是那種故障裡唯一還會叫的東西。
acase("鏈外開關：門檻是自己的 key，不跟 monitor 共用"
      "（共用的話，調鬆 monitor 會連唯一還會叫的那個一起調鬆）",
      ["watchdog:" in _gate_txt, "stale_after_days" in _gate_txt.split("watchdog:")[1][:200]],
      [True, True])

# ── 版型：移除指標之後留下的三個洞（2026-08-11）──────────────────────
# 實測（1440 寬）：header 底 131px、h1 頂 163px，中間只有 32px，而 h1 是 serif
# 大字級、上面還壓著一條 page-rubric——三層文字擠在一起。
_R_SRC_811 = open(os.path.join(_HERE, "pulse-render.py"), encoding="utf-8").read()
_R_CSS_811 = _rmod.CSS
acase("文章頁：標題與 header 之間要有呼吸（rubric 屬於導覽不屬於標題）",
      "padding-top:30px" in _R_CSS_811.split(".lf-head{")[1].split("}")[0], True)
# 右欄的 h3 曾經是「分數／評分理由／判斷的依據／證據／證據 · 1 筆」——兩組疊字。
# score_grid_html 自己印一個 <h3>評分理由</h3>，而呼叫端外面又包一層 <h3>分數</h3>。
acase("文章頁：評分那一塊只有一層標題（兩層疊字會讓讀者以為那是兩個區塊）",
      _rmod.score_grid_html({"confidence": 1, "heat": None, "impact": 1, "value": 1,
                             "independent": 2, "score_factors": {}}).count("<h3>"),
      0)
# journey_shape() 在只有一筆證據時把區塊標題換成 EVIDENCE_HEADING，也就是那個區塊
# 本身就是證據清單、而且每一筆都帶外連。再印一次 ev_block 就是同一份東西印兩次，
# 而 94% 的已發布事件都只有一筆證據——那是常態不是例外。
acase("文章頁：發展歷程退化成證據清單時，不再另印一份證據"
      "（94% 的事件只有一筆證據，所以那是常態）",
      [ln for ln in _R_SRC_811.splitlines()
       if "ev_links and journey_heading != EVIDENCE_HEADING" in ln] != [],
      True)
# 首頁：實測索引 9 筆內容 814px、計數欄 829px，而中欄被一個 21 字標題的 h1 撐到
# 1070px——兩側各空 250px。真正的修法是 h1 依標題長度換字級，不是把側欄塞滿。
def _hev811(title):
    return {"id": "e1", "slug": "s1", "title": title, "title_zh": None,
            "date": _rmod.clock.display_date(_rmod.clock.utc_now()).isoformat(), "date_display": "2026-08-11",
            "company": "OpenAI", "track": "模型能力與研究", "summary": "摘要。",
            "confidence": 73, "impact": 55, "independent": 1,
            "layers": {"事實": "一段事實。"}}
# 走真的 build_home，不是掃字串——掃字串的話，把 lead_cls 那一行整個拿掉、
# 只留 CSS 裡的 .t-long 規則，判準照樣全綠（M220 第一版就是這樣活下來的）。
_home_long = _rmod.build_home([_hev811("一二三四五六七八九十一二三四五六七八九十一")],
                              {}, "2026-08-11")
_home_mid = _rmod.build_home([_hev811("一二三四五六七八九十一二三四五")], {}, "2026-08-11")
_home_short = _rmod.build_home([_hev811("短標題")], {}, "2026-08-11")
acase("首頁：頭條字級依標題長度分級（長標題不降級，中欄會把兩側各撐出 250px 空白）"
      "——走真的 build_home，掃字串會讓「規則還在但沒人套用」全綠",
      ['class="lead-story t-long"' in _home_long,
       'class="lead-story t-mid"' in _home_mid,
       'class="lead-story"' in _home_short,
       ".lead-story.t-long h1" in _R_CSS_811],
      [True, True, True, True])
# 累計數幾乎不動，一頁每天都長一樣的看板讀者第二天就不再看。「本期」用的是
# 頭條的同一個窗口，兩邊講同一段時間，讀者才對得起來。
acase("首頁：主線那一欄要有「本期」而不是只有累計"
      "（累計幾乎不動，而窗口跟頭條同一個，兩邊講的是同一段時間）",
      ["本期 +" in _R_SRC_811,
       "LEAD_WINDOW_DAYS" in _R_SRC_811.split("recent = {")[1][:400]],
      [True, True])

# ── 「我上次說要看什麼」：待回答清單與裁決帳本（2026-08-11）────────────
# 原本的 P1 是「把 next_signal 結構化讓機器自動核對」。實測推翻了那個規劃：
# next_signal 這個 frontmatter 欄位早就存在而且 **0/86 被填過**，有內容的一直是
# body 那段散文；而那 86 段裡約六成以「看…」開頭——寫給人的觀察指示，
# 指向 benchmark 數字、出貨時程這類抓取鏈看不到的世界。同期 81/86 的事件仍然
# 只有一個獨立來源。**瓶頸不在資料結構，在觀測範圍。**
# 所以這一支不判定任何事，只整理問題讓人回答。
# 見 docs/design/2026-08-11-theme-tracking-revisited.md。
_sr_spec = importlib.util.spec_from_file_location(
    "pulse_signal_review", os.path.join(_HERE, "pulse-signal-review.py"))
_sr = importlib.util.module_from_spec(_sr_spec)
_sr_spec.loader.exec_module(_sr)
# sid 綁內容不綁流水號：那段話被改寫過就是**另一個問題**，舊答案不該繼續掛著。
acase("待答清單：sid 綁內容——同一個來源鍵、話改了就是另一個 sid"
      "（不然改寫過的訊號會掛著上一版的答案，而那是完全不同的一個問題）",
      [_sr.sid("infra-cost", "看第三方 benchmark") == _sr.sid("infra-cost", "看第三方 benchmark"),
       _sr.sid("infra-cost", "看第三方 benchmark") == _sr.sid("infra-cost", "看出貨時程"),
       _sr.sid("a", "x") == _sr.sid("b", "x")],
      [True, False, False])
with _tf2.TemporaryDirectory() as _td_sr:
    _v = Path(_td_sr)
    (_v / "Events").mkdir(parents=True)
    (_v / "_config").mkdir(parents=True)
    (_v / "_config" / "narratives.yaml").write_text(
        "version: 1\ntracks:\n  infra-cost:\n    next: 看有沒有第三方成本數字。\n", "utf-8")
    (_v / "Events" / "a.md").write_text(
        "---\nid: evt-a\nstatus: published\n---\n\n## 事實\n某某公司發表了東西。\n\n"
        "## 下一個訊號\n看有沒有第二個獨立來源。\n", "utf-8")
    # 未潤稿的那一則不該進待答清單——它不是一個待回答的問題，是待潤稿。
    (_v / "Events" / "b.md").write_text(
        "---\nid: evt-b\nstatus: published\n---\n\n## 下一個訊號\n待編輯：接下來看什麼。\n", "utf-8")
    # review 的也不該進：門禁還沒讓它上線，它的訊號還不是對外的宣稱。
    (_v / "Events" / "c.md").write_text(
        "---\nid: evt-c\nstatus: review\n---\n\n## 下一個訊號\n看後續有沒有人跟進。\n", "utf-8")
    _sr_all = _sr.collect(_v)
    _sr_kinds = sorted(k for _s, k, _src, _t in _sr_all)
    _sr_srcs = sorted(src for _s, _k, src, _t in _sr_all)
    _sr_pend0 = len(_sr.pending(_v))
    _sr_sid0 = _sr.collect(_v)[0][0]
    _rc_sr_bad = _subprocess.run(
        [sys.executable, os.path.join(_HERE, "pulse-signal-review.py"),
         "--answer", "bogus#00000000", "--verdict", "happened"],
        capture_output=True, text=True, env=dict(os.environ, VAULT_DIR=str(_v))).returncode
    def _sr_run(*extra):
        return _subprocess.run(
            [sys.executable, os.path.join(_HERE, "pulse-signal-review.py"),
             "--answer", _sr_sid0, *extra],
            capture_output=True, text=True,
            env=dict(os.environ, VAULT_DIR=str(_v))).returncode
    # P0-b 的四道閘。全部要在寫進帳本**之前**擋下來——帳本是 append-only。
    _sr_rc_noreason = _sr_run("--verdict", "unanswerable", "--note", "看不到")
    _sr_rc_badreason = _sr_run("--verdict", "unanswerable",
                               "--reason", "enterprise_adoptions")
    _sr_rc_other = _sr_run("--verdict", "unanswerable", "--reason", "other")
    _sr_rc_misplaced = _sr_run("--verdict", "happened", "--reason", "benchmark")
    _sr_led_before = _sr.history.read(_v / "_probe" / "signal-verdicts.jsonl")
    _sr_run("--verdict", "unanswerable", "--reason", "enterprise_adoption",
            "--note", "看不到")
    _sr_pend1 = len(_sr.pending(_v))
    _sr_led = _sr.history.read(_v / "_probe" / "signal-verdicts.jsonl")
    _sr_led_v = _sr.history.read(_v / "_probe" / "signal-verdicts.jsonl",
                                 field="verdict")
    _sr_led_r = _sr.history.read(_v / "_probe" / "signal-verdicts.jsonl",
                                 field="unanswerable_reason")
acase("待答清單：只收已上線、而且真的潤過的那幾則"
      "（待編輯佔位還在的是待潤稿不是待回答；review 的還不是對外宣稱）",
      [_sr_kinds, _sr_srcs], [["主線", "事件"], ["evt-a", "infra-cost"]])
acase("待答清單：回答過的從待辦消失，答案進帳本"
      "（這一頁是待辦不是歷史——歷史在 _probe/signal-verdicts.jsonl）",
      [_sr_pend0, _sr_pend1, len(_sr_led_v),
       (_sr_led_v[0].get("to") if _sr_led_v else None)],
      [2, 1, 1, "unanswerable"])
# 一次裁決寫兩筆、用 field 分開：覆蓋率矩陣要的是「原因碼的分佈」，
# 用 field 過濾一次就拿得到。塞進同一筆（to="unanswerable:enterprise_adoption"）
# 的話，每個下游都要自己 split，而 split 規則會在第二個消費者那裡分岔。
acase("裁決帳本：unanswerable 寫兩筆（verdict + unanswerable_reason），"
      "而且 field 分得開",
      [len(_sr_led), len(_sr_led_r),
       (_sr_led_r[0].get("to") if _sr_led_r else None)],
      [2, 1, "enterprise_adoption"])
acase("裁決帳本：unanswerable 缺 reason 要拒寫"
      "（一筆「這個系統看不到它」但沒說看不到哪一類，只剩下一個計數——"
      "而那個原因碼正是整條線最有價值的資料點）",
      [_sr_rc_noreason, len(_sr_led_before)], [2, 0])
acase("裁決帳本：不認得的 reason 要拒寫（開放詞彙表會讓覆蓋率矩陣的軸長出同義異形）",
      _sr_rc_badreason, 2)
acase("裁決帳本：`other` 沒有 --note 要拒寫"
      "（分類表是 n=0 時猜出來的，other 是它的死人開關；"
      "一筆沒有說明的 other 會進分母把比例撐大，卻留不下任何能重新分類的線索）",
      _sr_rc_other, 2)
acase("裁決帳本：reason 只能配 unanswerable"
      "（happened / not-yet 記了原因碼會進覆蓋率矩陣的分子，"
      "而那張表問的是「答不了的有哪些」）",
      _sr_rc_misplaced, 2)
acase("lib/sources.REASONS ＝ CAPABILITIES + other（衍生不抄寫）"
      "——PRD 給的是兩份不同的清單（11 vs 14），而 §19 的矩陣要求兩邊能直接比較；"
      "用兩份清單 join，對不到的列是詞彙表的洞不是量出來的洞",
      [sorted(_smod.REASONS - _smod.CAPABILITIES), len(_smod.REASONS)],
      [["other"], 16])
# append-only 的帳本記錯了刪不掉，所以 sid 對不上就要拒寫並回非零。
acase("待答清單：對不上任何問題的 sid 要拒寫並回非零"
      "（帳本是 append-only，一筆打錯字的裁決會永遠留在裡面當雜訊）",
      [_rc_sr_bad, len(_sr_led_v)], [2, 1])
# 這一頁要有人產生，否則又是一個「寫了沒人讀」的反面：沒人寫。
_WF_SR = "\n".join(ln for ln in open(
    os.path.join(_HERE, "..", ".github", "workflows", "data-refresh.yml"),
    encoding="utf-8").read().splitlines() if not ln.lstrip().startswith("#"))
acase("待答清單：夜班真的有一步在產生它（沒有生產者的頁面等於不存在）",
      "pulse-signal-review.py --write" in _WF_SR, True)

# ── 覆蓋缺口矩陣：需求 × 供給（references/vault-pages.md〈coverage-gap.md〉）──
# 這一頁最重要的性質是「它會誠實地說自己量不到」。把「還沒有人回答過」印成 0，
# 會讓 procurement（0 需求、0 來源）看起來跟一個真的沒問題的格子一樣綠。
_cgs = importlib.util.spec_from_file_location(
    "pulse_coverage_gap", os.path.join(_HERE, "pulse-coverage-gap.py"))
_cg = importlib.util.module_from_spec(_cgs)
_cgs.loader.exec_module(_cg)
_CG_TH = _cg.thresholds({})
_CG_SRC = _yaml.safe_load(
    open(os.path.join(_HERE, "..", "_config", "sources.yaml"), encoding="utf-8"))
acase("覆蓋缺口：樣本不足時**每一格**都是量不到，不是 0"
      "（燈號本身是拿需求算出來的，需求量不到而燈照亮，那個燈亮的是空氣）",
      [_cg.cell(0, 13, 0, False, _CG_TH)[0], _cg.cell(9, 0, 3, False, _CG_TH)[0]],
      ["－", "－"])
acase("覆蓋缺口：0 需求不給綠燈"
      "（0 需求可能是「這一輪沒人問到」，不是「這一類沒問題」——"
      "而 0 需求 + 0 來源更不是綠，那是這個系統最大的盲區的樣子）",
      [_cg.cell(0, 7, 0, True, _CG_TH)[0], _cg.cell(0, 0, 0, True, _CG_TH)[0]],
      ["⚪", "⚪"])
acase("覆蓋缺口：獨立供給是 0 而有需求一律紅（不看比值——除以 0 那一格是另一種狀態，"
      "不該用一個大數字表達）",
      _cg.cell(1, 0, 0, True, _CG_TH)[0], "🔴")
# ── 供給拆兩欄（references/vault-pages.md〈官方自述 vs 獨立〉）──
# P0-a 第一批量到：benchmark 名義供給 4 條判 🟡，但其中 3 條是官方線自己評自己，
# 真正獨立的只有 1 條。7 個需求對 1 條獨立供給，那不是 🟡。
acase("覆蓋缺口：燈號只看獨立供給，官方再多也不算"
      "（22 則 unanswerable 每一則都是「只有官方說了，我們判定看不到」——"
      "官方供給在這批需求上的實測命中率是 0）",
      [_cg.cell(7, 1, 3, True, _CG_TH)[0], _cg.cell(7, 3, 0, True, _CG_TH)[0]],
      ["🔴", "🟡"])
acase("覆蓋缺口：獨立 0 而官方 > 0 的訊息要跟「完全沒人看」分開"
      "（前者去找第三方來對，後者連題材都沒有人碰——擠成同一句話會讓人找錯方向）",
      [_cg.cell(1, 0, 5, True, _CG_TH)[1], _cg.cell(1, 0, 0, True, _CG_TH)[1]],
      ["只有當事人自己在說，沒有獨立來源", "沒有任何來源在看"])
acase("lib/sources: aggregator 不算獨立供給"
      "（sources.yaml 檔頭寫明它只當候選來源、不作任何事實依據；"
      "把 HN 算成獨立，等於讓一個轉貼站撐起某一格的覆蓋率）",
      ["aggregator" in _smod.INDEPENDENT_TRACKS,
       "src-hn-frontpage" in sum(_smod.capability_claims(
           _CG_SRC, _smod.INDEPENDENT_TRACKS).values(), []),
       "src-hn-frontpage" in sum(_smod.capability_claims(_CG_SRC).values(), [])],
      [False, False, True])
# legal_proceeding 是 P0-a 的 `other` 累積出來的第一個具體產出：3 筆 other 裡
# 有 2 筆是同一件事（法院受理與裁定）。一次是巧合，兩次是分類表少一格。
acase("lib/sources: legal_proceeding 在詞彙表裡，而且供給是「官方 0／獨立 3」"
      "（沒有公司會發文報自己被告的進度——這一類只可能從第三方來）",
      ["legal_proceeding" in _smod.CAPABILITIES,
       len(_smod.capability_claims(_CG_SRC, _smod.OFFICIAL_TRACKS)
           .get("legal_proceeding") or []),
       len(_smod.capability_claims(_CG_SRC, _smod.INDEPENDENT_TRACKS)
           .get("legal_proceeding") or [])],
      [True, 0, 3])
acase("lib/sources: benchmark 的獨立供給實測只有 1 條"
      "（名義 4 條裡 3 條是官方線自己評自己——這是 P0-a 之後把供給拆兩欄的起因）",
      [len(_smod.capability_claims(_CG_SRC, _smod.INDEPENDENT_TRACKS).get("benchmark") or []),
       len(_smod.capability_claims(_CG_SRC, _smod.OFFICIAL_TRACKS).get("benchmark") or [])],
      [1, 3])
acase("覆蓋缺口：`other` 佔比是那份分類表的死人開關（超過門檻要提醒；"
      "沒有樣本時是「量不到」不是 0%）",
      [_cg.other_line(0, 0, _CG_TH)[1], _cg.other_line(3, 29, _CG_TH)[1],
       _cg.other_line(12, 29, _CG_TH)[1],
       "量不到" in _cg.other_line(0, 0, _CG_TH)[0]],
      [False, False, True, True])
acase("覆蓋缺口：門檻讀 gate.yaml，壞掉的值走預設而不是往鬆的方向倒",
      [_cg.thresholds({"coverage_gap": {"min_answers": "十"}})["min_answers"],
       _cg.thresholds({"coverage_gap": {"min_answers": 26}})["min_answers"]],
      [10, 26])
acase("覆蓋缺口：gate.yaml 真的有 coverage_gap 這一塊（判準讀不到就會靜靜走預設）",
      sorted((_yaml.safe_load(open(os.path.join(_HERE, "..", "_config", "gate.yaml"),
                                   encoding="utf-8")).get("coverage_gap") or {})),
      ["amber_ratio", "min_answers", "other_reason_warn", "red_ratio"])
# append-only 的現值是最後一筆，不是每一筆。這條在 26 則一次答完的時候
# 跟舊算法給一樣的答案——它會在第一次有人改答案的那天才開始分岔，
# 而那正是「錯得慢」的形狀：一直是個合理的數字，只是慢慢地偏。
from lib import history as _histmod  # noqa: E402
_LAT = [{"id": "a", "field": "verdict", "to": "unanswerable"},
        {"id": "a", "field": "unanswerable_reason", "to": "benchmark"},
        {"id": "b", "field": "verdict", "to": "unanswerable"},
        {"id": "b", "field": "unanswerable_reason", "to": "procurement"}]
_LAT2 = _LAT + [{"id": "a", "field": "verdict", "to": "happened"}]
acase("帳本現值：latest() 取每個 id 的最後一筆，不是每一筆"
      "（append-only 的 from/to 就是為了讓「改過」看得見，"
      "下游不分現值與歷史的話那個設計就白做了）",
      [len(_histmod.latest(_LAT2, "verdict")),
       _histmod.latest(_LAT2, "verdict")["a"]["to"]],
      [2, "happened"])
acase("覆蓋缺口：改判之後那一則的舊原因碼不再佔需求"
      "（a 從 unanswerable 改成 happened，benchmark 就不該繼續算一格；"
      "而 26 則一次答完時新舊算法同分——它是在第一次改答案那天才分岔的）",
      [dict(_cg.tally(_LAT)[0]), dict(_cg.tally(_LAT2)[0]),
       _cg.tally(_LAT2)[1], _cg.tally(_LAT2)[2]],
      [{"benchmark": 1, "procurement": 1}, {"procurement": 1}, 2, 1])

acase("覆蓋缺口：夜班真的有一步在產生它（沒有生產者的頁面等於不存在）",
      "pulse-coverage-gap.py --write" in _WF_SR, True)
# `.index()` 在字串不見時會丟 ValueError，而丟例外的判準不會紅，會 crash——
# 而 crash 的變異在 mutate.py 眼裡「不算數」（M182 記過同一個形狀）。
# 所以用 find()：不存在是 -1，順序判斷自然為假，紅得乾淨。
def _wf_at(needle):
    return _WF_SR.find(needle)


acase("覆蓋缺口：必須排在 signal review 之後（它讀的是那一支寫進帳本的東西）"
      "，也必須在 commit 之前（不然整天不會被推上去）",
      (0 <= _wf_at("pulse-signal-review.py --write")
       < _wf_at("pulse-coverage-gap.py --write")
       < _wf_at("Commit & push data changes")), True)

# ── 判斷層的帳本：覆寫之前先留痕（references/narrative-layer.md〈帳本〉）──
# now / next 是整段覆寫的，實測相鄰兩版有過只剩 10% 相同的。在這一版之前，被改掉的
# 那一段只活在 git history 裡，而沒有任何一支腳本或任何一頁在讀它——這個系統因此
# 答不出「我上週對這條線怎麼說」。而同一個 repo 的來源層一直有帳本。
from lib import history as _hist  # noqa: E402


def _read_ledger(v):
    return _hist.read(v / "_probe" / "narrative-history.jsonl")


with _tf2.TemporaryDirectory() as _td_h1:
    _hv1 = _narr_vault(_td_h1)
    _run_narr_apply(_hv1, {"infra-cost": {"now": "換一版新的 now。", "next": "原本的 next"}})
    _led1 = _read_ledger(_hv1)
acase("判斷層帳本：覆寫之前把舊值留下來（走真的子行程；"
      "沒有這一筆，「我上週怎麼說」就只剩 git history，而沒有任何東西在讀它）",
      [len(_led1),
       [(r.get("id"), r.get("field"), r.get("from"), r.get("to"), r.get("reason"))
        for r in _led1]],
      [1, [("infra-cost", "now", "原本的 now", "換一版新的 now。", "nightly-enrich")]])
# next 這一欄送進去的值跟舊值一模一樣。記下去的話，帳本每晚多六筆「什麼都沒改」，
# 而「這一期有幾條主線改過主張」會被稀釋成常數——這個 repo 已經量過的那種沒有
# 鑑別力的指標（confidence 54/60 同一個數字、tier_evidence 59/59 都是 1）。
acase("判斷層帳本：值沒變就不記（假異動會把「幾條主線改過」稀釋成常數）",
      [r.get("field") for r in _led1], ["now"])

with _tf2.TemporaryDirectory() as _td_h2:
    _hv2 = _narr_vault(_td_h2)
    _run_narr_apply(_hv2, {"infra-cost": {"now": "第一版。"}})
    _run_narr_apply(_hv2, {"infra-cost": {"now": "第二版。"}})
    _led2 = _read_ledger(_hv2)
acase("判斷層帳本：同一個 (id, field) 前一筆的 to 等於後一筆的 from"
      "（不相等就代表有人繞過寫入路徑動了 narratives.yaml——只存 from 的話"
      "那件事會無聲通過）",
      [len(_led2),
       [r.get("from") for r in _led2], [r.get("to") for r in _led2]],
      [2, ["原本的 now", "第一版。"], ["第一版。", "第二版。"]])

# 拒收的那一欄不該留痕：它根本沒有被寫進 yaml，記一筆會讓帳本說一件沒發生的事。
with _tf2.TemporaryDirectory() as _td_h3:
    _hv3 = _narr_vault(_td_h3)
    _run_narr_apply(_hv3, {"infra-cost": {
        "now": "這輪 heat 8–10 偏低，還沒共振。", "next": "乾淨的下一步。"}})
    _led3 = _read_ledger(_hv3)
acase("判斷層帳本：被熱度規則拒收的欄位不留痕（它沒有被寫進 yaml，"
      "記一筆等於帳本說了一件沒發生的事）",
      [r.get("field") for r in _led3], ["next"])

# jsonl 的半行只損失那一筆；一個大 JSON 的半份是整份讀不起來。append 不是原子的，
# 所以讀取端一定要容錯——而容錯不能靜靜吃掉「缺欄位」那種壞行（它進到下游會被
# 當成某個欄位處理，而它其實是壞的）。
with _tf2.TemporaryDirectory() as _td_h4:
    _hp4 = Path(_td_h4) / "h.jsonl"
    _hist.append(_hp4, [_hist.change("t1", "a", "now", "x", "y", "r")])
    with _hp4.open("a", encoding="utf-8") as _fh:
        _fh.write('{"at":"t2","id":"a","field":"now","from":"y","to":  \n')  # 半行
        _fh.write('{"at":"t3","id":"b"}\n')                                   # 缺欄位
    _hist.append(_hp4, [_hist.change("t4", "b", "next", None, "z", "r")])
    _read4 = _hist.read(_hp4)
    _read4b = _hist.read(_hp4, id="b")      # 要在 with 裡讀完：temp dir 一刪，
    _read4x = _hist.read(_hp4 / "nope")     # read() 對不存在的路徑回 []，
                                            # 兩者長得一樣，測試會假綠。
acase("帳本讀取：半行與缺欄位的壞行一律跳過，不炸也不放行"
      "（append 不是原子的，被砍在中間會留下半行；壞行進到下游會被當成好行）",
      [len(_read4), [(r.get("id"), r.get("field")) for r in _read4],
       len(_read4b), _read4x],
      [2, [("a", "now"), ("b", "next")], 1, []])
acase("帳本：rows 是空的就連檔案都不建"
      "（0 bytes 的帳本會讓「還沒開始記」跟「這班沒有異動」長得一樣）",
      [_hist.append(Path(_td_h4) / "never.jsonl", []),
       (Path(_td_h4) / "never.jsonl").exists()], [0, False])

# 一份沒有人讀的帳本會在某一天停掉，而停掉的樣子跟「這陣子沒有主線改過主張」
# 一模一樣。這個 repo 已經量過同一隻病：value 每則都算、沒有任何東西讀它。
_nl_today = _dt_m.date(2026, 8, 3)
acase("判斷層帳本要有消費者：空帳本標成異常，有紀錄的印出最近改過的主線"
      "（沒有這一行，帳本停掉不會有任何東西變紅——value-沒人用 同一隻病）",
      [_mon.narrative_ledger_line([], _nl_today)[1],
       _mon.narrative_ledger_line(
           [_hist.change("2026-08-02T01:00:00+00:00", "infra-cost", "now", "a", "b", "r")],
           _nl_today)[1],
       "infra-cost" in _mon.narrative_ledger_line(
           [_hist.change("2026-08-02T01:00:00+00:00", "infra-cost", "now", "a", "b", "r")],
           _nl_today)[0],
       "沒有主線改過主張" in _mon.narrative_ledger_line(
           [_hist.change("2026-06-01T01:00:00+00:00", "infra-cost", "now", "a", "b", "r")],
           _nl_today)[0]],
      [True, False, True, True])
# render_health 拿的 today 是報告裡的 r["date"]，那是字串。直接丟給 _lag 會 TypeError，
# 而 render_health 沒有人接例外——一個觀測用的欄位不該炸掉整張看板。
acase("判斷層帳本：today 給字串也要活著（看板那條路徑傳的就是字串）",
      _mon.narrative_ledger_line(
          [_hist.change("2026-08-02T01:00:00+00:00", "x", "now", "a", "b", "r")],
          "2026-08-03")[1], False)

# narratives.yaml 下一班會被讀回去當事實，卻一直用裸 write_text。半份 YAML 讀得
# 起來、不報錯、被 git add -A commit 上去，而站上與 Tracks/*.md 照樣渲染。
_NA_SRC = open(os.path.join(_HERE, "pulse-narrative-apply.py"), encoding="utf-8").read()
acase("narratives.yaml 走原子寫，而且進了 atomic-writes 的表"
      "（它下一班會被讀回去當事實，半份 YAML 讀得起來——就是 sources.yaml 那次）",
      ['narr_file.write_text' in _NA_SRC,
       'atomic_write_text(narr_file' in _NA_SRC,
       "`_config/narratives.yaml`" in open(
           os.path.join(_HERE, "..", "references", "atomic-writes.md"),
           encoding="utf-8").read()],
      [False, True, True])

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

# ── 發展歷程／證據區塊：只在能主張的時候才說「起點」 ────────────────
# 規格：references/event-timestamps.md〈第三個現場：呈現層〉。
# 修正前的判準是 `if is_first: return "origin"`——那是關於**我們資料排序位置**的
# 事實，被印成一個關於**世界**的宣稱。2026-07-27 實測 36 則已發布事件裡 32 則
# 只有一筆證據：那個「第一」同時是「唯一」，卻標著「起點」。

acase("journey_shape：單筆證據不叫發展歷程、不發起點"
      "（一個只有一項的清單不是歷程，它唯一的那一項也不是起點）",
      _rmod.journey_shape("observed", 1), ("證據", None, False))
acase("journey_shape：backfilled 不發起點，而且要印出回填說明"
      "（沒有那句話，一則首抓撈回的舊事件在畫面上跟真的追到的一模一樣）",
      _rmod.journey_shape("backfilled", 3),
      ("證據", _rmod.COVERAGE_NOTE["backfilled"], False))
acase("journey_shape：unknown 用**另一句**說明，不跟 backfilled 共用"
      "（共用的話讀者會把「我們沒紀錄」讀成「我們確定沒在看」＝把不知道講成知道）",
      [_rmod.journey_shape("unknown", 3)[1] != _rmod.journey_shape("backfilled", 3)[1],
       _rmod.journey_shape("unknown", 3)[2]], [True, False])
acase("journey_shape：coverage 欄位還沒長出來（None）時倒向保守，不發起點"
      "（舊 note 還沒被重寫過就是這一格，不能因為欄位缺席就開始亂宣稱）",
      _rmod.journey_shape(None, 3)[2], False)
acase("journey_shape：observed 且 ≥2 筆證據才叫發展歷程、才發起點",
      _rmod.journey_shape("observed", 2), ("發展歷程", None, True))

# 語料查不到時不得編造。這條釘的是**兩個**退路，因為它們的傷害不同：
# 標題退回來源名 → 畫面上出現一筆標題是「NVIDIA Blog」的證據；
# 日期退回事件日 → 一整串證據看起來同一天出現，而那是讀者判斷「怎麼發展」的唯一線索。
_jn_ev = {"evidence": [{"sid": "src-x", "url": "https://no.such/url"}],
          "date": "2026-07-14", "coverage": "observed"}
_jn_head, _jn_html = _rmod.journey_html(_jn_ev, {}, {})
# 比對的是**標題元素本身**，不是整段 HTML：來源名本來就會出現在下面那個連結標籤裡，
# 那是對的。第一版斷言整段不含來源名，紅的是斷言不是碼。
_jn_title = _jn_html.split("<b>")[1].split("</b>")[0]
acase("journey_html：語料查不到 → 標題元素印「標題未留存」，不得退回來源名"
      "（跟 HEAT_UNMEASURED 同一條規矩：印一個看起來合理的值，"
      "會被讀成「這就是那筆證據的標題」）",
      [_jn_title, _jn_title == _rmod.prettify_source("src-x")],
      [_rmod.TITLE_UNKEPT, False])
acase("journey_html：語料查不到 → 印「日期未留存」，不得退回事件日"
      "（退回事件日會讓一則事件的所有證據看起來同一天出現）",
      [_rmod.DATE_UNKEPT in _jn_html, "2026-07-14" in _jn_html], [True, False])
acase("journey_html：回傳的是 (區塊標題, HTML)——標題不再是寫死的字串",
      _jn_head, "證據")

_jn_bf = dict(_jn_ev, coverage="backfilled",
              evidence=[{"sid": "src-x", "url": "u1"},
                        {"sid": "src-y", "url": "u2"}])
_jn_bf_head, _jn_bf_html = _rmod.journey_html(_jn_bf, {}, {})
acase("journey_html：backfilled 的事件頁真的印出回填說明，且標題不是「發展歷程」"
      "（判準對了但沒印出來，等於沒判）",
      [_jn_bf_head, _rmod.COVERAGE_NOTE["backfilled"] in _jn_bf_html,
       "起點" in _jn_bf_html], ["證據", True, False])

# 自我審查補的一條：拿掉日期退路之後才走得到的路徑。原本「解不出日期就當 1970」
# 讓一筆**我們承認不知道日期**的證據保證排第一，然後拿到「起點」——印出來的那行是
# 「起點／日期未留存／標題未留存」，正是這個修正要消滅的東西，由修正本身引進。
_jn_mix = {"evidence": [{"sid": "src-a", "url": "https://known"},
                        {"sid": "src-b", "url": "https://unknown"}],
           "date": "2026-07-14", "coverage": "observed"}
_jn_mix_head, _jn_mix_html = _rmod.journey_html(
    _jn_mix, {"https://known": {"title": "真的最早那一篇", "date": "2026-07-10"}}, {})
_jn_rows = [(_re.search(r'jn-type">([^<]*)', li).group(1),
             _re.search(r'<b>([^<]*)', li).group(1))
            for li in _jn_mix_html.split("<li ")[1:]]
acase("journey_html：沒有日期的證據排**最後**、且不得拿到「起點」"
      "（缺值不能贏過已知值；連它什麼時候發生都不知道，就沒有資格說"
      "「這件事從這裡開始」）",
      [_jn_rows[0][1], _jn_rows[0][0], _jn_rows[-1][1]],
      ["真的最早那一篇", "起點", _rmod.TITLE_UNKEPT])
acase("journey_html：連第一筆的日期都不知道時，整則都不發「起點」",
      "起點" in _rmod.journey_html(
          dict(_jn_mix, evidence=[{"sid": "src-a", "url": "u1"},
                                  {"sid": "src-b", "url": "u2"}]), {}, {})[1],
      False)

# ── 接線：判準算對了，但有沒有真的接到輸出上 ────────────────────────
# 這三條是自我審查補的。M93–M95 一開始「看起來被殺掉」，但實測是**假殺**——
# 只有「find 必須剛好出現一次」那條 meta 測試變紅，沒有任何行為測試在守。
# 一個只被 meta 殺掉的變異，等於沒有被守住。

_en_ev = _cm.Event("evt-en", "en", "T", "2026-07-14T00:00:00+00:00")
_en_ev.add_evidence("src-a", "u1", "t", 100)
_en_ev.fm = {"id": "evt-en", "status": "published", "coverage": None}
_en_ev.orig_body = "\n## 事實\n潤好的字\n"
_cm.rescore(_en_ev, {"src-a": {"tier": 1}}, None, None, None, _CV_FF)
acase("pulse-cluster：**已潤稿**那條寫檔路徑也要寫 coverage"
      "（漏掉的話這格只會長在沒潤過稿的 Event 上——實測 52 則只有 1 則拿到，"
      "而且每班都判「跟磁碟上不一樣」、每班重寫、每班寫的還是舊值）",
      "coverage: backfilled" in _cm.rescored_enriched_markdown(_en_ev), True)

_lv = _pathlib.Path(_tempfile.mkdtemp())
(_lv / "Events").mkdir()
(_lv / "Events" / "evt-lv.md").write_text(
    "---\nid: evt-lv\nslug: lv\ntitle: T\ndate: '2026-07-14'\nstatus: published\n"
    "coverage: backfilled\ncompany: C\n"
    "evidence:\n- source_id: src-a\n  url: https://a\n  title: T1\n"
    "  published: '2026-07-10'\n---\n\n## 事實\nx\n",
    encoding="utf-8")
acase("pulse-render.load_events：coverage 從檔案讀，不得寫死"
      "（寫死成 observed 會讓每一則都宣稱我們當時在看——往編造的方向倒）",
      _rmod.load_events(_lv)[0].get("coverage"), "backfilled")

_pg_ev = dict(_rmod.load_events(_lv)[0],
              layers={}, summary="", confidence=0, heat=None, impact=0, value=0,
              independent=0, score_factors={}, date_display="2026-07-14",
              category="", track="",
              evidence=[{"sid": "src-a", "url": "u1"},
                        {"sid": "src-b", "url": "u2"}])
_pg_html = _rmod.build_event_page(_pg_ev, [_pg_ev], {}, {}, "now")
acase("pulse-render.build_event_page：頁面標題用 journey_html 回傳的那個"
      "（回傳值被測了、頁面有沒有用它沒被測——寫死回「發展歷程」的話，"
      "backfilled 的事件頁會掛著一個它不配的標題）",
      # 標題現在住在側註的 h3（長文版把驗證用的東西全部移到側邊），
      # 查的還是同一件事：頁面用的是 journey_html 回傳的那個字，不是寫死的。
      [f"<h3>{_rmod.journey_html(_pg_ev, {}, {})[0]}</h3>" in _pg_html,
       "<h3>發展歷程</h3>" in _pg_html], [True, False])

# ── 發展歷程不再依賴語料保留期 ──────────────────────────────────
# 規格〈第三個現場〉的〈一條沒被記下來的依賴〉：這一區原本只查 _corpus/，而語料的
# 保留期由 `corpus-累積` 那個**還沒拍板的決定**控制。欄位一直都在 frontmatter 裡，
# 只是 render 讀進來的時候把它丟掉了——規格說已經解開、實作沒有，那是紅線 8。
_ee = [{"sid": "src-a", "url": "https://a", "title": "Event 自己存的標題",
        "published": "2026-07-10"},
       {"sid": "src-b", "url": "https://b", "title": "第二筆", "published": "2026-07-11"}]
_ee_ev = {"evidence": _ee, "date": "2026-07-14", "coverage": "observed"}

_, _ee_html = _rmod.journey_html(_ee_ev, {}, {})
acase("journey_html：**語料全空**時照樣印得出真標題與真日期"
      "（這條就是「不再依賴語料保留期」那句話的全部意思；掉了它，corpus-累積 改成"
      "滾動視窗的那天，所有舊事件的證據會靜靜變成「未留存」）",
      ["Event 自己存的標題" in _ee_html, "2026-07-10" in _ee_html,
       _rmod.TITLE_UNKEPT in _ee_html, _rmod.DATE_UNKEPT in _ee_html],
      [True, True, False, False])

_, _ee_html2 = _rmod.journey_html(
    _ee_ev, {"https://a": {"title": "語料裡的舊標題", "date": "2026-01-01"}}, {})
acase("journey_html：Event 自己存的優先於語料（語料是補充，不是真相源）",
      ["Event 自己存的標題" in _ee_html2, "語料裡的舊標題" in _ee_html2],
      [True, False])

_, _ee_html3 = _rmod.journey_html(
    {"evidence": [{"sid": "src-a", "url": "https://a"}], "date": "2026-07-14",
     "coverage": "observed"},
    {"https://a": {"title": "只有語料有", "date": "2026-07-10"}}, {})
acase("journey_html：Event 沒存時才退到語料（反方向，確認上一條不是把語料整條關掉）",
      ["只有語料有" in _ee_html3, "2026-07-10" in _ee_html3], [True, True])

# 驗**值**不只驗 key：第一版只比對 keys，而把值換成 None 的變異照樣活著——
# 一個「欄位在、內容是空的」的 load_events，下游看起來跟沒接一模一樣。
_lv_e = _rmod.load_events(_lv)[0]["evidence"][0]
acase("pulse-render.load_events：證據帶著 title / published 的**值**一起讀進來"
      "（只讀 (source_id, url)、或讀了但填 None，上面那些優先序全部走不到）",
      [_lv_e.get("sid"), _lv_e.get("url"), _lv_e.get("title"), str(_lv_e.get("published"))],
      ["src-a", "https://a", "T1", "2026-07-10"])

# 遷移那支：body 裡的「（標題未留存）」是**佔位不是標題**，補進去比空著更糟——
# 空著時 render 知道要印「標題未留存」，補了假值之後它會以為自己有標題。
_mg = importlib.util.spec_from_file_location(
    "mig_ev", os.path.join(_HERE, "migrate-2026-07-27-evidence-titles.py"))
_mgm = importlib.util.module_from_spec(_mg)
_mg.loader.exec_module(_mgm)
acase("migrate evidence-titles：body 的「（標題未留存）」不得被當成標題補進去"
      "（補假值之後 render 會以為自己有標題，比空著更糟）",
      _mgm.titles_from_body(
          "## 證據\n- [[Sources/src-a|src-a]] — （標題未留存）https://a\n"
          "- [[Sources/src-b|src-b]] — 真的標題（https://b）\n"),
      {"https://b": "真的標題"})

# 這條釘的是第一版真正的缺陷：**依位置**配對。同一條來源兩筆證據、body 兩行，
# 而 frontmatter 的順序跟 body 相反——位置配對會把 A 的標題貼到 B 的網址上。
# 實測 main 上沒有真的錯配（資料剛好沒踩到），所以只能靠測試釘，不能靠觀察。
_mg_body2 = ("## 證據\n"
             "- [[Sources/src-a|src-a]] — 第一篇的標題（https://one）\n"
             "- [[Sources/src-a|src-a]] — 第二篇的標題（https://two）\n")
_mg_fm2 = {"evidence": [{"source_id": "src-a", "url": "https://two"},
                        {"source_id": "src-a", "url": "https://one"}]}
_mgm.backfill(_mg_fm2, _mg_body2)
acase("migrate evidence-titles：同一來源多筆時**用 URL 配對不用位置**"
      "（frontmatter 與 body 順序相反時，位置配對會把 A 的標題貼到 B 的網址上）",
      [_mg_fm2["evidence"][0]["title"], _mg_fm2["evidence"][1]["title"]],
      ["第二篇的標題", "第一篇的標題"])

# 反方向：body 裡根本沒有這個 URL 的行 → 維持空著，不得從別行借一個看起來合理的。
_mg_fm3 = {"evidence": [{"source_id": "src-a", "url": "https://nowhere"}]}
_mgm.backfill(_mg_fm3, _mg_body2)
acase("migrate evidence-titles：body 沒有這個 URL 的行 → 留空，不從別行借"
      "（借來的標題會是另一篇文章的，而畫面上看不出來）",
      _mg_fm3["evidence"][0].get("title"), None)
_mg_fm = {"evidence": [{"source_id": "src-a", "url": "https://a", "title": "原本就有"}]}
_mgm.backfill(_mg_fm, "## 證據\n- [[Sources/src-a|src-a]] — 新的（https://a）\n")
acase("migrate evidence-titles：只補空的，不覆蓋既有值",
      _mg_fm["evidence"][0]["title"], "原本就有")

# ── 時間軸：觀測起點線與回填標記 ────────────────────────────────
# 規格〈第三個現場〉的〈事件時間軸〉。修正前，一則首抓撈回的舊事件在時間軸上跟
# 真的追到的長得**一模一樣**，讀者只能得出「這個系統從 07-07 就在追」的結論。
def _tlev(i, cov, d="2026-07-20"):
    return {"id": f"evt-{i}", "slug": f"s{i}", "title": f"T{i}", "date": d,
            "date_display": d, "company": "C", "category": "", "track": "models",
            "summary": "S", "confidence": 80, "heat": None, "title_zh": None,
            "coverage": cov}


acase("observed_cut：線畫在**最後一則 observed 之後**"
      "（只宣稱守得住的那一半：線以下沒有任何一則是我們當場看到的。反過來畫一條"
      "「以上都是觀測到的」是假的——coverage 逐則逐來源算，新來源會讓晚期事件"
      "照樣是 backfilled）",
      _rmod.observed_cut([_tlev(1, "observed"), _tlev(2, "observed"),
                          _tlev(3, "backfilled"), _tlev(4, "backfilled")]), 2)
acase("observed_cut：一則 observed 都沒有 → 線畫在最前面，整條都在線下"
      "（不是不畫線——不畫等於讓整條時間軸看起來都是我們追到的）",
      _rmod.observed_cut([_tlev(1, "backfilled"), _tlev(2, "unknown")]), 0)
acase("observed_cut：最後一則就是 observed → 沒有回填區，不畫線",
      _rmod.observed_cut([_tlev(1, "observed"), _tlev(2, "observed")]), None)

acase("時間軸標記：backfilled 與 unknown **不共用字樣**"
      "（「確定是首抓撈回的」跟「不知道當時看不看得到」是兩件事，共用會把後者"
      "講成前者），且 observed 不掛標籤（滿版的標記等於沒有標記）",
      [_rmod.COVERAGE_CHIP["backfilled"] != _rmod.COVERAGE_CHIP["unknown"],
       _rmod.COVERAGE_CHIP.get("observed")], [True, None])

# 接線：判準對了但沒印出來等於沒判（M95 那一課）。
_tl_html = _rmod.build_timeline(
    [_tlev(1, "observed", "2026-07-25"), _tlev(2, "backfilled", "2026-07-20"),
     _tlev(3, "unknown", "2026-07-10")], "now")
# 2 不是 1：同一則事件現在畫兩次（泳道一個點、編年一張卡），
# 而**兩邊都要掛回填標記**——只掛一邊，另一邊就在說這則是我們當場看到的。
# 泳道與編年是同一批事件的兩種畫法，**兩邊都要看得出哪些是回填**。
# 編年掛「回填」兩個字；泳道的點沒有文字空間，所以改成實心／空心／虛線空心，
# 並在圖例上說明。只做一邊，另一邊就在說那些是我們當場看到的。
acase("build_timeline：編年掛文字標記、泳道用點的樣式區分，觀測起點線印在編年區",
      # 只數 tl-chip，不數整頁的字：圖例上也寫著「回填」兩個字。
      [_tl_html.count(f'<span class="tl-chip">{_rmod.COVERAGE_CHIP["backfilled"]}<'),
       _tl_html.count(f'<span class="tl-chip">{_rmod.COVERAGE_CHIP["unknown"]}<'),
       _tl_html.count('data-cov="backfilled"'), _tl_html.count('data-cov="unknown"'),
       "tl-cut" in _tl_html, _rmod.OBSERVED_CUT_NOTE in _tl_html,
       "lane-legend" in _tl_html],
      [1, 1, 1, 1, True, True, True])
acase("build_timeline：頁首印出回填則數（看不見的時候有兩種意思——沒有回填，"
      "或這段沒跑，而「整條看起來像持續觀測」正是這一層要修掉的誤會）",
      "其中回填" in _tl_html, True)

# ─────────────────────────── verify-article-metadata.py（C-4 的驗證器）─────
# 這一段守的是紅線 7 的下半句：**「我們讀不到」不等於「站方拒絕」**。
# 2026-07-27 把 egress allowlist 的 403 讀成 Anthropic 的 WAF，差一點寫進設計。
# 下面每一條都是那次誤讀的具體反面。
_vam = importlib.util.spec_from_file_location(
    "verify_article_metadata", os.path.join(_HERE, "verify-article-metadata.py"))
_vamod = importlib.util.module_from_spec(_vam)
_vam.loader.exec_module(_vamod)

acase("egress 攔截：認 x-deny-reason 標頭（大小寫不敏感——標頭本來就不分大小寫，"
      "而分大小寫的判斷會在別的 proxy 上安靜地失效）",
      [bool(_vamod.is_egress_intercept(403, "", {"X-Deny-Reason": "host_not_allowed"})),
       bool(_vamod.is_egress_intercept(403, "", {"x-deny-reason": "host_not_allowed"}))],
      [True, True])
acase("egress 攔截：沒有標頭時認 body 簽名"
      "（實測就是這 104 bytes：Host not in allowlist: www.anthropic.com.）",
      bool(_vamod.is_egress_intercept(
          403, "Host not in allowlist: www.anthropic.com. Add this host to your "
               "network egress settings to allow access.", {})), True)
# 反方向同樣重要，而且更容易被寫壞：把站方真正的拒絕洗成「沒有判決」，
# 等於讓一個確定的壞消息消失。站方的 403 沒有那兩個簽名，就必須留在 site_error。
acase("egress 攔截：站方自己的 403 不得被洗成「沒有判決」"
      "（Cloudflare 那種擋人頁沒有 allowlist 簽名；判成 no_verdict 等於"
      "把一個確定的答案變成不確定，然後永遠等不到它變確定）",
      _vamod.is_egress_intercept(403, "<html><title>Access denied</title></html>", {}),
      None)
# body 刻意**含有**簽名字樣。不含的話這一條在拿掉狀態碼判斷之後照樣會過，
# 等於什麼都沒守——M109 第一次跑就是這樣活下來的。
acase("egress 攔截：200 的 **body 簽名**不算攔截（body 那條分支只在 403 生效；"
      "把 200 也拿去比對簽名，會讓一篇正好在講 allowlist 的文章變成無判決，"
      "而那是我們讀得到的頁。標頭那條分支刻意不看狀態碼——proxy 什麼碼都可能回）",
      _vamod.is_egress_intercept(
          200, "Why your host is not in allowlist by default: a 2026 explainer",
          {}), None)

_VAM_PAGE = ('<html><head>'
             '<meta property="og:title" content="Introducing Claude Opus 5">'
             '<title>Introducing Claude Opus 5 \\ Anthropic</title>'
             '</head><body><h1>Introducing Claude Opus 5</h1>'
             '<p>Jul 24, 2026</p><p>body text here</p></body></html>')
_vam_f = _vamod.extract(_VAM_PAGE)
acase("C-4 抽取：og:title 取到真值，而三個機器可讀日期全部 ABSENT"
      "（這正是 C-2 在真頁面上量到的形狀：標題可以完全修好，日期不行）",
      [_vam_f["og:title"], _vam_f["article:published_time"],
       _vam_f["time@datetime"], _vam_f["jsonld:datePublished"]],
      ["Introducing Claude Opus 5", None, None, None])
# 上面那條的 fixture **不含**那三個 tag，所以它斷言的是 None == None——
# 三個 regex 全部改壞它照樣綠（實測）。而「機器可讀日期全部 ABSENT」已經
# 被當成關於世界的事實寫進設計文件：抽取器壞掉的話，「我們讀不到」就變成
# 「站方沒有寫」——紅線 7 那句話的第四種犯法。下面這條是它缺的另一半。
_VAM_FULL = ('<meta property="article:published_time" content="2026-07-24T10:00:00Z">'
             '<time datetime="2026-07-25">x</time>'
             '{"datePublished": "2026-07-26"}'
             '<meta content="Rev Order Title" property=\'og:title\'>'
             '<title>Page &amp; Title</title>')
_vam_full = _vamod.extract(_VAM_FULL)
acase("C-4 抽取：這三個 tag **在**的時候要真的抽得到"
      "（不測這一半，「全部 ABSENT」就可能是抽取器壞了而不是站方沒寫）",
      [_vam_full["article:published_time"], _vam_full["time@datetime"],
       _vam_full["jsonld:datePublished"], _vam_full["og:title(rev)"],
       _vam_full["<title>"]],
      ["2026-07-24T10:00:00Z", "2026-07-25", "2026-07-26",
       "Rev Order Title", "Page & Title"])
# 撇號在雙引號屬性裡完全合法。第一版的 `content=["\']([^"\']+)` 會在它那裡
# 截斷，抽出 `Anthropic`——一個更短、看起來仍然像標題的字串，寫進
# c4-report.json，而設計文件說那份 JSON 才是可以引用的證據。
acase("C-4 抽取：屬性值裡的撇號不得截斷標題，HTML entity 要解開"
      "（截斷後的字串仍然像標題，這是最難看見的一種錯）",
      [_vamod.extract('<meta property="og:title" content="Anthropic\'s Opus 5">')["og:title"],
       _vamod.extract('<meta property="og:title" content="Claude&#x27;s tool">')["og:title"]],
      ["Anthropic's Opus 5", "Claude's tool"])
# 修撇號的第二版改用 `[^>]*?`，註解寫著「屬性值裡的 `>` 在合法 HTML 裡是
# `&gt;`」——**那句話是錯的**。HTML5 只禁止同款引號與有歧義的 `&`。
# 後果是 verdict=no_og_title → 「這一站沒有 og:title」，又一次把
# 「我們讀不到」寫成「站方沒有」。
acase("C-4 抽取：屬性值裡的 `>` 是合法 HTML，不得因此判成「沒有 og:title」",
      [_vamod.extract(
          '<meta property="og:title" content="Claude 3 -> Claude 5">')["og:title"],
       _vamod.verdict_for(_vamod.MODE_ARTICLE, _vamod.extract(
           '<meta property="og:title" content="Claude 3 -> Claude 5">'))],
      ["Claude 3 -> Claude 5", "ok"])
acase("C-4 抽取：值裡可以有另一種引號；`og:title:alt` 不算 og:title",
      [_vamod.extract("<meta property='og:title' content='He said \"hi\"'>")["og:title"],
       _vamod.extract('<meta property="og:title:alt" content="ALT">')["og:title"],
       _vamod.extract('<meta property="og:title" content="">')["og:title"]],
      ['He said "hi"', None, None])
# og:title 有 rev companion，日期沒有——而「三個機器可讀日期全部 ABSENT」
# 是已經寫進設計文件、關於世界的宣稱。
acase("C-4 抽取：日期也要有反序版本（content 在前、property 在後）"
      "（少一個順序，「全部 ABSENT」就可能是量測失真而不是事實）",
      _vamod.extract(
          '<meta content="2026-07-24" property="article:published_time">'
      )["article:published_time(rev)"], "2026-07-24")
# 這一條第一版寫成 `VERDICT_EXIT.get("x", 4) == 4`——那是在測 `dict.get`
# 的預設值行為，**不管碼怎麼寫都會過**（M132 因此活了下來）。
# 真正要測的判斷躲在 main() 裡，所以把它拉成 exit_code() 再測。
acase("C-4 退出碼：沒登記的 verdict 預設成 4（沒有判決），不是 2（站方的答案）"
      "（預設 2＝一個忘了寫進表裡的新狀態會被當成站方回覆過）",
      [_vamod.exit_code([{"verdict": "some_future_verdict"}]),
       _vamod.exit_code([{"verdict": "ok"}, {"verdict": "no_verdict"}]),
       _vamod.exit_code([{"verdict": "ok"}]),
       _vamod.exit_code([])],
      [4, 4, 0, 0])
acase("C-4 判準：verdict_for 兩種 mode 各自的通過條件"
      "（第一版整支從沒被呼叫過——改成無條件回 ok 也全綠）",
      [_vamod.verdict_for(_vamod.MODE_ARTICLE, {"og:title": "X"}),
       _vamod.verdict_for(_vamod.MODE_ARTICLE, {"og:title": None}),
       _vamod.verdict_for(_vamod.MODE_PAGE,
                          {"_visible_text_chars": 10, "visible_date_count": 9}),
       _vamod.verdict_for(_vamod.MODE_PAGE,
                          {"_visible_text_chars": 99999, "visible_date_count": 0}),
       _vamod.verdict_for(_vamod.MODE_PAGE,
                          {"_visible_text_chars": 99999, "visible_date_count": 9})],
      ["ok", "no_og_title", "js_shell", "no_dates", "ok"])


# robots 不是印給人看的，是要擋住這一支自己的。第一版算了、印了、然後無條件抓。
class _FakeRobots:
    def __init__(self, verdict):
        self.verdict, self.fetched = verdict, False

    def robots_verdict(self, url):
        return self.verdict

    def safe_fetch(self, url, etag=None):
        self.fetched = True
        return 200, "<html>" + "x" * 5000 + "</html>", {}


def _robots_case(verdict):
    fp = _FakeRobots(verdict)
    r = _vamod.probe_one(fp, "https://ex.test/a")
    return r["verdict"], fp.fetched


acase("C-4 robots：站方明文 Disallow → 不抓，判 robots_disallow（站方的答案，exit 2）",
      _robots_case((False, "disallow")), ("robots_disallow", False))
# `unavailable_403` 也回 False，但它的意思是我們讀不到那份 robots.txt。
# 只看布林值就會把它讀成拒絕——正是這整個 PR 在修的那句話。
acase("C-4 robots：401/403 取不到 robots → no_verdict，**不是** robots_disallow"
      "（pulse-probe 早就為這一格開過分支：非站方拒絕）",
      _robots_case((False, "unavailable_403")), ("no_verdict", False))
acase("C-4 robots：未知一律不當成許可，而且**不抓**（紅線 7）",
      [_robots_case((None, "not_robots")), _robots_case((None, "error"))],
      [("no_verdict", False), ("no_verdict", False)])
acase("C-4 robots：允許才抓（守到把自己鎖死也是一種壞掉）",
      _robots_case((True, "ok"))[1], True)
acase("C-4 抽取：人看的日期抓得到，但只到日、沒有時區"
      "（抓得到不等於能用——存成 T00:00:00Z 就是編造精度，"
      "所以 published_precision 必須跟值一起存）",
      _vam_f["visible_date"], "Jul 24, 2026")

# JS 空殼：og:title 是伺服器端算好的 meta，空殼照樣有；人看的日期不是。
# 若不量「去掉標籤後剩幾個字」，空殼與完整頁在這支的輸出上長得一模一樣。
_vam_shell = _vamod.extract(
    '<html><head><meta property="og:title" content="X"></head>'
    '<body><div id="__next"></div><script>var a=1;var d="Jul 24, 2026";</script>'
    '</body></html>')
acase("C-4 抽取：JS 空殼要看得出來——script 裡的日期不算數，"
      "可見文字接近零（不量這個，空殼與完整頁的輸出無法區分）",
      [_vam_shell["visible_date"], _vam_shell["_visible_text_chars"] < 10], [None, True])

# 退出碼：no_verdict 必須排在最前面。壞判決至少是關於站方的，
# 沒有判決是關於我們自己的——而後者更該讓 CI 紅。
acase("C-4 退出碼：no_verdict(4) 高於所有「站方回答了但答案不合用」的狀態(3/2)，"
      "而那些又高於 ok(0)",
      [_vamod.VERDICT_EXIT["no_verdict"],
       sorted({_vamod.VERDICT_EXIT[k] for k in
               ("no_og_title", "js_shell", "no_dates")}),
       sorted({_vamod.VERDICT_EXIT[k] for k in ("site_error", "robots_disallow")}),
       _vamod.VERDICT_EXIT["ok"]],
      [4, [3], [2], 0])
# 上面那條只釘常數表。main() 把 max 改成 min **全綠**（實測）——於是一次
# 「一個 host 被攔截、另一個 ok」的跑會回 0，CI 綠著放行一份不能引用的報告。
# M110 防的是常數，這一條防的是聚合。
acase("C-4 退出碼：一次跑裡最壞的那一條決定退出碼"
      "（改成取最小值＝有 ok 就綠，而 no_verdict 那條被吞掉）",
      max(_vamod.VERDICT_EXIT.get(v, 2) for v in ("ok", "no_verdict", "ok")), 4)
acase("C-4 退出碼：只有 ok 對應 0（任何其他狀態對應 0，都會讓 CI 綠著放行"
      "一份不能引用的報告）",
      [k for k, v in _vamod.VERDICT_EXIT.items() if v == 0], ["ok"])

# control probe：這一關不通過就整份不出判決。三條分別釘住它的三種輸入。
class _FakePP:
    def __init__(self, ret=None, exc=None):
        self._ret, self._exc = ret, exc

    def safe_fetch(self, url, etag=None):
        if self._exc:
            raise self._exc
        return self._ret


acase("C-4 control probe：對方回 403 但**有走到伺服器** → 算連得出去"
      "（GitHub 對未認證請求就回 403。要求 200 會讓 control probe 自己變成"
      "偽陽性來源，然後每一次驗證都中止在第一關）",
      _vamod.control_probe(_FakePP(ret=(403, "rate limit", {})), "u")[0], True)
acase("C-4 control probe：被 egress 攔截 → 連不出去（整份中止）",
      _vamod.control_probe(
          _FakePP(ret=(403, "Host not in allowlist: x.", {})), "u")[0], False)
acase("C-4 control probe：連不上（ProxyError 之類）→ 連不出去，"
      "而且不得讓例外炸穿（炸穿＝沒有報告，看起來像沒跑）",
      _vamod.control_probe(_FakePP(exc=OSError("Tunnel connection failed")), "u")[0],
      False)

_vam_wf_path = os.path.join(_HERE, "..", ".github", "workflows",
                            "verify-article-metadata.yml")
acase("C-4 必須在 CI 跑：workflow 存在且真的呼叫這支腳本"
      "（在有 egress allowlist 的開發機上量到的數字，回答的是別的問題）",
      [os.path.isfile(_vam_wf_path),
       "verify-article-metadata.py" in open(_vam_wf_path, encoding="utf-8").read()],
      [True, True])
_vam_wf = _yaml.safe_load(open(_vam_wf_path, encoding="utf-8"))
_vam_steps = _vam_wf["jobs"]["verify"]["steps"]
acase("C-4：control probe 不得在 CI 被跳過"
      "（--skip-control 一開，整支就退回成「手寫臨時腳本」——"
      "那正是 2026-07-27 誤讀的成因）",
      [s for s in _vam_steps if "--skip-control" in str(s.get("run") or "")], [])
# 判決原本只活在一個 artifact 裡：要下載才看得到、90 天過期、git 讀不到。
# 而 C-4 是整個時間線層的閘。這幾條釘住那份判決有沒有真的被留下來。
_c4s = importlib.util.spec_from_file_location(
    "c4_summary", os.path.join(_HERE, "c4-summary.py"))
_c4mod = importlib.util.module_from_spec(_c4s)
_c4s.loader.exec_module(_c4mod)

acase("C-4 摘要：四個退出碼各有各的意思，不得共用一句話"
      "（壓成一個 failure 就是把「沒有判決」跟「站方說不行」寫成同一件事）",
      [sorted(_c4mod.EXIT_MEANING), len(set(_c4mod.EXIT_MEANING.values()))],
      [["0", "2", "3", "4"], 4])
# 第一版寫成 `EXIT_MEANING.get("99", "未登記…")`——那是在讀**測試自己寫的
# 預設值**，不管碼怎麼寫都會過（M135 活下來）。這條分支上第五次犯同一個錯。
# 規則：**斷言裡不准出現 `X.get(k, 預設)`**。改成讀真的輸出。
_c4_unreg = _c4mod.render("/tmp/__no_such_c4__.json", "release-notes", "99")
_c4_known = _c4mod.render("/tmp/__no_such_c4__.json", "release-notes", "4")
acase("C-4 摘要：未登記的退出碼要在**印出來的字**裡當成沒有判決，不是留白"
      "（留白讀起來像沒事，而它的意思是我們不知道發生什麼）",
      ["未登記" in _c4_unreg, "退出碼 **99** — \n" in _c4_unreg + "\n",
       "沒有判決" in _c4_known], [True, False, True])
_c4_step = [s for s in _vam_steps if "c4-summary.py" in str(s.get("run") or "")]
acase("C-4 摘要：workflow 真的會叫它，而且 always()"
      "（判決最紅的時候正是最需要被留下來的時候）",
      [len(_c4_step), _c4_step[0].get("if") if _c4_step else None],
      [1, "always()"])
# GitHub 只給 success / failure。不自己把退出碼撈出來，2 / 3 / 4 三種
# 意思完全不同的壞消息會在摘要上長得一模一樣。
acase("C-4 摘要：退出碼有被撈出來傳給摘要，不是靠 GitHub 的 success/failure",
      [s for s in _vam_steps if "C4_EXIT=" in str(s.get("run") or "")] != [], True)

acase("C-4：驗證那一步不得 continue-on-error"
      "（吞掉退出碼＝把這次驗證退化成一份沒有人看的 log）",
      [s for s in _vam_steps if s.get("continue-on-error")], [])

# ────────────────────────────────── lib/modelline.py（模型演變時間線純函式層）
# 規格 references/model-timeline.md。**這一段的每一條都對應一個實測撞出來的洞**，
# 不是想像的案例——fixture 的標記結構抄自 2026-07-27 在 CI 之外唯一抓得到的那頁
# （platform.claude.com 的 release notes，1,436,122 bytes）。
from lib import modelline as _ml  # noqa: E402

_ML_LINES = [
    {"id": "claude", "canonical": "Claude",
     "version_pattern": r"(?:\s)?(opus|sonnet|haiku|fable|mythos)?(?:\s|-)?([0-9]+(?:\.[0-9]+)?)"},
    {"id": "chatgpt", "canonical": "ChatGPT"},   # 沒有 version_pattern，不該衍生
]

acase("lifecycle：封閉集，且 ambiguous 與 unknown 是兩個不同的答案"
      "（unknown 要補動詞表，ambiguous 要更細的切分——要人做的事不一樣）",
      [_ml.UNKNOWN in _ml.LIFECYCLES, _ml.AMBIGUOUS in _ml.LIFECYCLES,
       _ml.UNKNOWN != _ml.AMBIGUOUS], [True, True, True])
acase("lifecycle：單一動詞逐字判",
      [_ml.lifecycle_of("We've retired the Claude Sonnet 4 model"),
       _ml.lifecycle_of("We've deprecated fast mode"),
       _ml.lifecycle_of("released as GA versions"),
       _ml.lifecycle_of("now in research preview"),
       _ml.lifecycle_of("Pricing page updated")],
      [_ml.SHUTDOWN, _ml.DEPRECATED, _ml.GA, _ml.PREVIEW, _ml.UNKNOWN])
# 第一版用優先序解重疊：一條同時寫 launched 與 deprecated 的條目會被判成
# 其中一個，表看起來完整而那一格是編的。改成誠實地說「兩種宣稱都在」。
acase("lifecycle：兩種以上宣稱 → ambiguous，不用優先序挑一個"
      "（挑一個＝拿排序去代替一個我們沒有的答案）",
      _ml.lifecycle_of("We've launched Claude Sonnet 5 ... deprecated pricing"),
      _ml.AMBIGUOUS)

acase("日期：三種形狀各自的精度與年份出處",
      [_ml.parse_entry_date("July 24, 2026"),
       _ml.parse_entry_date("June 2026"),
       _ml.parse_entry_date("July 23")],
      [("2026-07-24", _ml.PRECISION_DAY, _ml.YEAR_EXPLICIT),
       ("2026-06", _ml.PRECISION_MONTH, _ml.YEAR_EXPLICIT),
       (None, _ml.PRECISION_NONE, _ml.YEAR_NONE)])
# docs.x.ai 的條目只印「July 23」。拿今年去補，2024 與 2025 的條目會全部堆到
# 今年，而每個日期都是合法日期——只有它們跟事實的關係是錯的。
acase("日期：缺年份時**不拿今年補**，除非呼叫端明示 year_hint；"
      "而補進去的年份要在 date_year_source 上留痕（section≠explicit）",
      [_ml.parse_entry_date("July 23")[0],
       _ml.parse_entry_date("July 23", 2024)],
      [None, ("2024-07-23", _ml.PRECISION_DAY, _ml.YEAR_SECTION)])
acase("日期：序數後綴（Anthropic 2024 年那批寫的是「July 9th, 2024」）"
      "——少了它那些條目會全部落回無年份",
      _ml.parse_entry_date("July 9th, 2024")[0], "2024-07-09")
acase("日期：2 月 30 日這種東西回 None 不丟例外"
      "（一條壞日期不該讓整頁解析中止）",
      _ml.parse_entry_date("February 30, 2026")[0], None)

# 兩道關卡要**分開**釘。第一版只給 `claude.com`（沒有數字），於是「必須有版本號」
# 那一關單獨就擋住了它，拿掉 TLD 名單照樣綠——M116 第一次跑就是這樣活下來的。
# `gpt-5.app` 有數字，只有 TLD 名單擋得住它。
acase("model id：網域不是模型，且兩道關卡各自都要有效"
      "（claude.com 靠「必須有版本號」擋；gpt-5.app 只有 TLD 名單擋得住）",
      [_ml.model_ids_in("see claude.com and claude.ai"),
       _ml.model_ids_in("hosted at gpt-5.app"),
       _ml.model_ids_in("We've launched Claude Opus 5 ( claude-opus-5 )")],
      [[], [], ["claude-opus-5"]])
acase("版本衍生：照 entities.yaml 寫下的規則產生 <line_id>@<slug>；"
      "沒有 version_pattern 的產品線不衍生（硬套會生出假實體）",
      [_ml.derive_versions("On Claude Opus 5, disabling thinking", _ML_LINES),
       _ml.derive_versions("ChatGPT went down", _ML_LINES)],
      [["claude@opus-5"], []])

# ── 整頁解析：fixture 的標記結構抄自真頁面 ──
_ML_HTML = (
    '<h3><div class="group relative pt-6 pb-2" id="july-24-2026">'
    '<div>July 24, 2026</div></div></h3>'
    '<ul><li>We&#x27;ve launched Claude Opus 5 ( claude-opus-5 ), see claude.com</li>'
    '<li>Mid-conversation tool changes are now in beta on Claude Fable 5</li></ul>'
    '<h3><div class="group relative pt-6 pb-2" id="may-30th-2024">'
    '<div>May 30th, 2024</div></div></h3>'
    '<ul><li>Tool use is now generally available</li></ul>'
    '<nav><ul><li>July 24, 2026</li><li>May 30th, 2024</li></ul></nav>')
_ml_rows = _ml.rows_from_anchor_page(_ML_HTML, "https://example.test/x", _ML_LINES)

acase("整頁：錨點的序數形式也要配到"
      "（第一版漏配 `-9th-`，後果不是少了那些條目——是它們全部被吞進上一個"
      "配到的錨點，2024-05 到 2025-04 每一條都被蓋上同一天）",
      sorted({r["happened_on"] for r in _ml_rows}), ["2024-05-30", "2026-07-24"])
acase("整頁：HTML entity 要解開，否則 `We&#x27;ve launched` 對不上動詞表"
      "（一個撇號讓整類發布條目判成 unknown）",
      _ml_rows[0]["lifecycle"], _ml.GA)
acase("整頁：lifecycle 逐 <li> 判，不是逐日判"
      "（同一天的一條 beta 會把整天染成 preview——每個值都對，歸屬錯了）",
      [_ml_rows[0]["lifecycle"], _ml_rows[1]["lifecycle"]], [_ml.GA, _ml.PREVIEW])
# 這一條擋掉的量在真頁面上是 124 列（全部落在最後一個錨點、全部同一天）。
acase("整頁：整條就是一個日期的 <li> 是目錄不是條目，要丟掉"
      "（不丟的話真頁面上三分之一的列是同一天的假列，而每一列的日期都合法）",
      [len(_ml_rows), _ml.is_date_only("July 24, 2026"),
       _ml.is_date_only("July 30, 2026 起 X 將停用")], [3, True, False])
# 第一版比的是「錨點個數 vs 日期出現次數」，真頁面健康時是 (124, 261)——
# 2.1 倍的落差是常態，而規則改壞之後只變成 (91, 261)。**永遠在叫的警報。**
# 改成比集合：內文有、而沒有任何錨點對應的日期，才是漏配的證據。
# 同一份真頁面：健康 4/128，錨點規則壞掉 27/128。
_ML_ORPHAN = _ML_HTML + "<p>Some entry dated March 3, 2025 with no anchor.</p>"
acase("整頁：漏配要靠 orphan_dates 看得出來，而不是靠一個永遠在叫的落差"
      "（漏配是安靜的：列數、解析率、日期格式全都正常）",
      [_ml.anchor_gap(_ML_HTML)["orphan_dates"],
       _ml.anchor_gap(_ML_ORPHAN)["orphan_dates"]], [0, 1])
acase("整頁：最後一個錨點的區間吃到檔尾，所以它的列要被標出來"
      "（頁尾的導覽與版權會被算成那一天的條目，is_date_only 只擋得住純日期的）",
      [sum(1 for r in _ml_rows if r["tail_chunk"]),
       _ml_rows[0]["tail_chunk"]], [1, False])

# 第一版在 rows 為空時回一個**少了 ambiguous 那把鑰匙**的 dict，一取就 KeyError。
acase("rates：沒有列的時候每一格都回 None，而且每一把鑰匙都要在"
      "（0 的意思是「量過了，沒問題」；少一把鑰匙的意思是消費端當場炸掉）",
      sorted(k for k, v in _ml.rates([]).items() if k.endswith("_rate")),
      ["ambiguous_lifecycle_rate", "no_date_rate", "section_year_rate",
       "unknown_lifecycle_rate", "unmatched_model_rate"])
acase("rates：lifecycle 兩格的母體是**有模型的列**，不是全部條目"
      "（真頁面 248 列裡只有 86 列有模型；用全部當母體，一次全面崩壞會"
      "從 0.47 走到 0.70，而真相是 0.33 走到 1.00——被稀釋成小幅上升）",
      _ml.rates([{"lifecycle": _ml.UNKNOWN, "model_ids": ["m-1"]},
                 {"lifecycle": _ml.UNKNOWN, "model_ids": []},
                 {"lifecycle": _ml.GA, "model_ids": []}])["unknown_lifecycle_rate"],
      1.0)
acase("rates：「年份是推的」與「根本沒有日期」要分成兩格"
      "（合成一格＝兩種要人做完全不同動作的狀況共用一個數字）",
      [_ml.rates([{"date_year_source": _ml.YEAR_SECTION, "happened_on": "2024-07-23"},
                  {"date_year_source": _ml.YEAR_NONE, "happened_on": None}])[k]
       for k in ("section_year_rate", "no_date_rate")], [0.5, 0.5])
# 第一版的分母是「全部條目」，於是 unmatched 是 0.79——量到的其實是
# 「有多少條不在講模型」，又一個比事實寬鬆的代理指標，我自己寫進去的。
# 這一條要用**兩個分母會給出不同答案**的資料才測得到。第一版拿 _ml_rows
# （0 條 unmatched）去測，兩個分母都是 0.0，改了照樣綠——M118 第一次跑活下來。
_ml_mixed = [{"versionish": True, "model_ids": [], "derived_entities": []},
             {"versionish": False, "model_ids": [], "derived_entities": []},
             {"versionish": False, "model_ids": [], "derived_entities": []}]
acase("rates：unmatched 的分母是「看起來在講版本」的條目，不是全部條目"
      "（用全部當分母，量到的是「有多少條不在講模型」——1.0 會被稀釋成 0.33，"
      "一個真正的字典缺口看起來像小問題）",
      [_ml.rates(_ml_rows)["versionish_rows"],
       _ml.rates(_ml_mixed)["unmatched_model_rate"]], [2, 1.0])
# _VERSIONISH 第一版寫死九個 token，而 entities.yaml 有二十三條產品線——
# 於是 Kimi / DeepSeek / Mistral 的新版本連分母都進不去，而這個比率的用途
# 正是「新版本有沒有被接住」。
acase("versionish：詞表來自 entities.yaml，不是寫死的九個廠商"
      "（DeepSeek-V4 這種「canonical 後面直接接數字」的也要算——"
      "詞尾加 \\b 會讓它永遠對不上自己的字典）",
      [_ml.mentions_version("DeepSeek-V4 is now generally available.",
                            [{"canonical": "DeepSeek-V"}]),
       _ml.mentions_version("Kimi K3 released as GA versions.",
                            [{"canonical": "Kimi"}])], [True, True])
acase("lifecycle：裸字 beta / preview 不算宣稱，要片語"
      "（真頁面上 42 條 ambiguous 有 34 條是被裸字 beta 打中的，包括"
      "「No beta header is required」——它明說**不是** beta）",
      [_ml.lifecycle_of("No beta header is required."),
       _ml.lifecycle_of("We've retired the 1M token context window beta"),
       _ml.lifecycle_of("now in beta on Claude Fable 5")],
      [_ml.UNKNOWN, _ml.SHUTDOWN, _ml.PREVIEW])
_ML_CLAUDE = [{"id": "claude", "canonical": "Claude",
               "version_pattern":
                   r"(?:\s)?(opus|sonnet|haiku)?(?:\s|-)?([0-9]+(?:\.[0-9]+)?)"}]
# 擋 model id 碎片的是**尾端邊界**（比對停在 `claude-3`，後面緊接 `-7`），
# 不是前面的 `\b`。第一版寫 `\b` 並宣稱它擋得住——實測加不加結果一模一樣，
# 因為 `deprecating claude-3-…` 的 claude 前面本來就有詞界。
acase("版本衍生：不得從廠商自己的 model id 裡切出裸數字版本"
      "（`claude-3-7-sonnet-20250219` → `claude@3` 是另一個世代的假實體，"
      "而 entities.yaml 說衍生實體是聚類主鍵）",
      [_ml.derive_versions("We are deprecating claude-3-7-sonnet-20250219.",
                           _ML_CLAUDE),
       _ml.derive_versions("Claude 3.5 and Claude Opus 4.8", _ML_CLAUDE)],
      [[], ["claude@3.5", "claude@opus-4.8"]])
acase("版本衍生：年份不是版本，單一字母不是版本",
      _ml.derive_versions("Run the command a second time",
                          [{"id": "command", "canonical": "command",
                            "version_pattern": r"(?:\s)?([a-z0-9]+)"}]), [])
# 第一版用「同一條裡只要有非裸數字的實體，就把所有裸數字實體全丟掉」擋碎片。
# 註解寫著「被別的衍生實體**字首包含**」，碼裡卻沒有任何包含判斷——實測它把
# 兩則真的下線宣告刪掉了，跨產品線更慘。
acase("版本衍生：裸數字版本是**合法的**，不得因為同一條裡有層級版本就被清掉"
      "（「retired the Claude 2.0, Claude 2.1, and Claude Sonnet 3 models」"
      "少掉的那兩個是真的下線宣告）",
      _ml.derive_versions(
          "We've retired the Claude 2.0, Claude 2.1, and Claude Sonnet 3 models.",
          _ML_CLAUDE),
      ["claude@2.0", "claude@2.1", "claude@sonnet-3"])
acase("版本衍生：跨產品線不得互相清除",
      _ml.derive_versions("GPT-4 and Claude Opus 5", [
          {"id": "gpt", "canonical": "GPT",
           "version_pattern": r"(?:-|\s)?([0-9]+(?:\.[0-9]+)?)"}] + _ML_CLAUDE),
      ["gpt@4", "claude@opus-5"])
# `\b` 在兩個 CJK 字之間不成立，於是字典裡 8 個中文 alias 全部失效。
acase("版本衍生：中文 alias 在中文散文裡要命中"
      "（`\\b` 前綴會讓「發布通義千問 3」的「布」把詞界吃掉——"
      "一個為了修 A 而加的東西，A 沒修到、B 全死）",
      _ml.derive_versions("阿里巴巴發布通義千問 3", [
          {"id": "qwen", "canonical": "Qwen", "aliases": ["通義千問"],
           "version_pattern": r"(?:-|\s)?([0-9]+(?:\.[0-9]+)?)"}]),
      ["qwen@3"])
acase("is_date_only：三種日期形狀都要認"
      "（規格已指名 docs.x.ai 印的是沒有年份的「July 23」——只認一種形狀，"
      "那一家的側欄索引一條都擋不掉）",
      [_ml.is_date_only("July 24, 2026"), _ml.is_date_only("June 2026"),
       _ml.is_date_only("July 23"), _ml.is_date_only("July 30, 2026 起停用")],
      [True, True, True, False])
# 月份 regex 原本是 `(jan|feb|…)[a-z]*`，於是 Marketing = mar + keting。
# 在 is_date_only 這個消費者上，那代表**真的條目被當成目錄項丟掉**。
acase("日期：月份只認真的月份名，不是「三個字母開頭再任意接」"
      "（Marketing 2026 / Nova 2 / Decoder 2 都不是日期）",
      [_ml.is_date_only("Marketing 2026"), _ml.is_date_only("Nova 2"),
       _ml.is_date_only("Decoder 2"), _ml.is_date_only("Sept 3, 2026")],
      [False, False, False, True])
# 私用區碼位是 icon font 的字形，永遠不是內容；不剝掉的話它會讓
# is_date_only 對「\ue09a July 24, 2026」判 False——一個看不見的字元
# 讓整頁的日期標題全部變成條目（實測 124 條）。
acase("去標籤：icon font 的私用區字元要剝掉，尾端沒收尾的標籤碎片也要"
      "（`<div class=\"x\"` 沒有 `>`，去標籤的 regex 抓不到它）",
      [_ml.strip_tags("\ue09a July 24, 2026"),
       _ml.strip_tags("real text <div class=\"group relative")],
      ["July 24, 2026", "real text"])
# 條目不一定住在 <li> 裡，而另外三家的標記形狀還沒有人看過。
acase("整頁：條目在 <p>、同段另有導覽 <ul> 時，真條目要在、導覽不要在"
      "（第一版是二選一：有 <li> 就只看 <li>，於是真條目零列、導覽兩列）",
      [(r["lifecycle"], "Home" in r["text"], "Claude Opus 5" in r["text"])
       for r in _ml.rows_from_anchor_page(
           '<div id="july-24-2026">July 24, 2026</div>'
           '<p>We have launched Claude Opus 5, our most capable model.</p>'
           '<nav><ul><li>Home</li><li>Docs</li></ul></nav>', "u")],
      [(_ml.GA, False, True)])

acase("references/model-timeline.md 存在（這一層的規格書，紅線 9 先文件後碼）",
      os.path.isfile(os.path.join(_HERE, "..", "references",
                                  "model-timeline.md")), True)
# 紅線 1。這一層是使用者建議裡「用單一 LLM 做正規化」那一步被換掉的地方，
# 換掉的理由必須留在碼裡看得到，而不是只留在文件裡。
# 第一版這一條是「原始碼裡不得出現 openai / llm 這些字」——而它立刻紅了，
# 因為註解裡就在解釋為什麼**不**用 LLM。用字串出現與否代表「有沒有呼叫模型」，
# 是這份 repo 一路在抓的那隻病，我在守它的測試裡又寫了一次。
# 改成釘**進口**：這一層是純函式，連網路都不該 import，遑論模型。
_ml_src = open(os.path.join(_HERE, "lib", "modelline.py"), encoding="utf-8").read()
acase("紅線 1：modelline 是純函式層，不得 import 網路或任何客戶端"
      "（使用者建議的「用單一 LLM 做正規化」那一步被字面動詞表取代——"
      "「需要 LLM」與「我還沒去讀那些字」是兩件事）",
      [m for m in _re.findall(r"^\s*(?:import|from)\s+([a-z_][\w.]*)",
                             _ml_src, _re.M)
       if m.split(".")[0] not in ("html", "re", "datetime", "__future__")], [])

# ─────────────────── 對外站上那兩句假話（BACKLOG 總表最前面兩條）─────────
# 兩條都是「凍結／編造的值被當成事實」，兩條都不會讓任何東西變紅。

# 一、四個從未量測的傳播因子。實測 41 / 41 則已發布頁把它們印成粗體 0，
#     就在同一張卡片上寫著「未量測」的 heat 旁邊。
_sc_none = _scoring.score_event([80], 1, 2, [], 10)["factors"]
_sc_meas = _scoring.score_event(
    [80], 1, 2, [{"authors": 3, "tweets": 50, "platforms": ["x"], "regions": ["us"]}], 10)["factors"]
acase("傳播因子：沒有 metrics 時回 None 不回 0"
      "（0 是「量過了，一個都沒有」，None 是「從來沒量過」——"
      "lib/scoring.py 自己的話：0 看起來像量過了很冷，那是更難察覺的一種謊）",
      [_sc_none[k] for k in ("uniqueAuthors", "platformBreadth", "regionBreadth",
                             "velocity", "crossRegion")],
      [None, None, None, None, None])
acase("傳播因子：有 metrics 時照樣回數字（守到把自己關掉也是一種壞掉）",
      [_sc_meas["uniqueAuthors"], _sc_meas["platformBreadth"],
       _sc_meas["crossRegion"]], [3, 1, False])
# 2026-07-27 有一次「順手重算」把 55 則事件的 value 全部改掉。這一條釘住
# 這次的改動只動「怎麼回報量不到」，不動任何一個分數。
# 兩條都寫成**寫死的期望值**。第一版把兩邊都寫成 `score_event(...)` 的呼叫，
# 那是拿同一個東西跟自己比，不管碼怎麼寫都會過；第二版的
# `... if hasattr(_rmod, "x") else True` 更糟，函式不存在時直接回 True。
# 這是同一條分支上第六次寫出空斷言，而規則前一天才剛寫進 mutation-inventory：
# **斷言的右邊不准由待測的碼算出來。**
acase("傳播因子：改回報方式**不得**動到 confidence / heat / impact / value"
      "（2026-07-27 有一次「順手重算」把 55 則事件的 value 全部改掉）",
      [_scoring.score_event([80], 1, 2, [], 10)[k]
       for k in ("confidence", "heat", "impact", "value")],
      [74, None, 55, 70])
_fac_html = _rmod.score_grid_html({
    "confidence": 74, "heat": None, "impact": 55, "value": 70, "independent": 2,
    # 十格全給，只有那四格是 None——不然缺鍵的也會印「未量測」，
    # 數字對不上就分不出是「修好了」還是「fixture 漏了」。
    "score_factors": {"authority": 80, "corroboration": 40, "primaryEvidence": 50,
                      "independentSources": 2, "freshness": 90,
                      "propagationSignals": 0,
                      "uniqueAuthors": None, "platformBreadth": None,
                      "regionBreadth": None, "velocity": None},
})
# 2026-08-11：常數欄位全部下架之後，留下的四項都是會變、而且量得到的。
# 「未量測」這三個字仍然要守——它現在守的是**缺鍵**那一種：舊 note 的
# score_factors 少一格時，印 0 是編造，必須印「未量測」而且不畫比例條。
_fac_partial = _rmod.score_grid_html({
    "confidence": 74, "heat": None, "impact": 55, "value": 70, "independent": 2,
    "score_factors": {"corroboration": 40, "primaryEvidence": 50}})
acase("因子條：量不到的那幾格在**印出來的 HTML 裡**是「未量測」，而且不畫比例條"
      "（長度 0 的條子跟「量到 0」在畫面上一模一樣，那正是要修掉的誤會）",
      [_fac_partial.count("bar-unmeasured"),
       _fac_partial.count(">" + _rmod.HEAT_UNMEASURED + "</b>")],
      [2, 2])
# 缺鍵也算沒量到。舊 note 的 score_factors 若少一格，印 0 是編造。
acase("因子條：`score_factors` 缺鍵一律當成沒量到，不補 0",
      _rmod.score_grid_html({"confidence": 1, "heat": None, "impact": 1, "value": 1,
                             "independent": 1, "score_factors": {}}
                            ).count("bar-unmeasured"), len(_rmod.FACTOR_META))

# ── 2026-08-11：heat 與 value 從讀者看得到的地方下架 ────────────────────
# heat 從上線到現在沒有一天印過數字（四項傳播輸入沒有量測管道，scoring 一律回
# None），那一格每天講的都是「這一格沒有內容」；value 是內部排序用的合成分，
# 對讀者沒有可解釋的意義。**下架的是顯示，不是欄位也不是判準**——frontmatter、
# gate 的 unmeasured_heat / unsupported_heat、送給敘述層的「未量測」全部沒動。
# 規格 references/readiness-gate.md〈為什麼 heat 與 value 不對讀者顯示〉。
#
# 判準守的是**反向**：只刪不反轉的話，下一個人會把它當回歸再加回去。
_hero_html_811 = _rmod.score_grid_html({
    "confidence": 74, "heat": None, "impact": 55, "value": 70, "independent": 2,
    "score_factors": {"freshness": 90}})
acase("讀者頁面：詳情頁的 hero 只剩 confidence，heat / value / impact 都不在"
      "（heat 恆為未量測、value 是內部合成分、impact 86/86 都是 55 —— "
      "它是 score_event 的預設值，整條鏈沒有任何呼叫端傳過那個參數）",
      [_hero_html_811.count("<div class=\"sh\">"),
       "heat" in _hero_html_811, ">value<" in _hero_html_811,
       ">impact<" in _hero_html_811],
      [1, False, False, False])
# 常數欄位不上版面：一個在每一則上都相同的數字，看起來像量出來的，其實不帶資訊。
# 實測 86 則已發布事件：authority 1 種值、uniqueAuthors 1 種值（永遠 None）。
acase("讀者頁面：恆為常數的因子不畫在因子條上（authority 86/86 都是 90、"
      "uniqueAuthors 86/86 都是 None —— 看起來像量出來的，其實是常數）",
      sorted(k for k, _l, _c in _rmod.FACTOR_META
             if k in ("authority", "uniqueAuthors")),
      [])
# 反向：真的會變的那四項必須還在，否則「只顯示會變的」會退化成「什麼都不顯示」。
acase("讀者頁面：會變的那四項因子必須還在（不然這一塊就不再解釋任何東西）",
      sorted(k for k, _l, _c in _rmod.FACTOR_META),
      ["corroboration", "freshness", "independentSources", "primaryEvidence"])
# 首頁頭條的 byline 也印過 impact，同一個常數同一個問題。
acase("讀者頁面：首頁頭條的 byline 不再印「影響」（同一個常數，同一個問題）",
      [ln for ln in open(os.path.join(_HERE, "pulse-render.py"), encoding="utf-8")
       .read().splitlines() if "影響 <b>" in ln],
      [])
# 四項傳播輸入也一起下架：留著等於讓讀者看到四塊拼圖、卻看不到拼出來的圖。
acase("讀者頁面：四項傳播因子不再畫在因子條上（它們合成的 heat 已經下架）",
      sorted(k for k, _l, _c in _rmod.FACTOR_META
             if k in ("platformBreadth", "regionBreadth", "velocity", "propagationSignals")),
      [])
# 卡片那一行是 heat 出現頻率最高的地方——86 則事件、每一則一次。
_card_811 = _rmod.event_card if hasattr(_rmod, "event_card") else None
acase("讀者頁面：事件卡片的 score 行不再印 heat"
      "（那是它出現最多次的地方，一則一次）",
      [ln for ln in open(os.path.join(_HERE, "pulse-render.py"), encoding="utf-8")
       .read().splitlines()
       if 'class="score"' in ln and "heat" in ln],
      [])
# 對外資料檔跟畫面同一個標準：欄位存在就等同公開宣稱。
acase("讀者頁面：dist 的事件 JSON 不再帶 heat 欄位（對外欄位等同公開宣稱）",
      [ln for ln in open(os.path.join(_HERE, "pulse-render.py"), encoding="utf-8")
       .read().splitlines()
       if '"summary", "confidence"' in ln and "heat" in ln],
      [])
# 反向的另一半：欄位與判準**必須還在**。只斷言「畫面上沒有」的話，
# 把 scoring 的 heat 整個拔掉也會全綠——那是完全不同的一件事。
_pg_txt_811 = open(os.path.join(_HERE, "pulse-gate.py"), encoding="utf-8").read()
acase("下架的是顯示不是判準：gate 的兩條 heat 規則與敘述層的「未量測」都還在"
      "（只守畫面的話，把 heat 從 scoring 拔掉也會全綠——那是完全不同的一件事）",
      ['blockers.append("unmeasured_heat")' in _pg_txt_811,
       'blockers.append("unsupported_heat")' in _pg_txt_811,
       '"未量測" if fm.get("heat") is None' in _np_txt],
      [True, True, True])

# 二、判斷層的 rule-tag 曾經被烙進 prose、之後不再重算，而同一頁的警示框是
#     即時算的。實測 evt-2026-07-21-1bdb1a：內文「單一獨立來源」，
#     frontmatter `independent_sources: 2`。同一頁兩個相反的宣稱。
_jt = "這是一則重要發布。（單一獨立來源，暫標待證實）"
acase("判斷層：rule-tag 即時算，舊 note 裡凍結的那一份要被剝掉"
      "（判斷層不能有兩個時鐘）",
      ["（多來源佐證）" in _rmod.layer_html("判斷", _jt, 2),
       "單一獨立來源" in _rmod.layer_html("判斷", _jt, 2),
       "單一獨立來源" in _rmod.layer_html("判斷", _jt, 1)],
      [True, False, True])
# 這一條要用**帶括號、且不在結尾**的字串才測得到。第一版給的是沒有括號的
# 「本則只有單一獨立來源，因此保守處理。」——兩種寫法都不會動它，
# 所以拿掉結尾錨點照樣綠（M139 活下來）。
acase("判斷層：只剝**結尾**那一份，句中出現同樣字眼的不動"
      "（誤剝比不剝更難發現——它會刪掉作者真的寫的字）",
      [_rmod.strip_frozen_tag("（多來源佐證）這四個字是作者引用的，不是 tag。"),
       _rmod.strip_frozen_tag("本則只有單一獨立來源，因此保守處理。"),
       _rmod.strip_frozen_tag("結論。（多來源佐證）")],
      ["（多來源佐證）這四個字是作者引用的，不是 tag。",
       "本則只有單一獨立來源，因此保守處理。", "結論。"])
# 沒有這兩條 CSS，`bar-unmeasured` 會沿用 `.bar` 的灰色軌道——
# 跟「量到 0」在畫面上一模一樣，整個修正等於沒做。
acase("傳播因子：未量測那一格的 CSS 真的存在，且不是一條空的比例條"
      "（沿用 .bar 的灰軌道就跟「量到 0」長得一樣，修了等於沒修）",
      # 不寫 `if hasattr(...) else True` —— 那個 fallback 在函式不存在時直接
      # 讓斷言成立，是這條分支上重複第七次的空斷言形狀。CSS 常數就在那裡，
      # 不存在就該當場 AttributeError 而不是靜靜變綠。
      # 釘**宣告**不釘選擇器。第一版只查 `.factor .bar-unmeasured{` 這串字，
      # 而把規則整個掏空成 `{}` 之後那串字還在——M137 因此活下來。
      ["border-top:1px dashed" in _rmod.CSS.split(".factor .bar-unmeasured{")[1]
       .split("}")[0],
       "background:none" in _rmod.CSS.split(".factor .bar-unmeasured{")[1]
       .split("}")[0],
       # 而且要真的被寫出去：CSS 不在 index.html 裡，在 assets/app.css。
       "CSS, encoding" in open(os.path.join(_HERE, "pulse-render.py"),
                               encoding="utf-8").read()],
      [True, True, True])
acase("判斷層：enrich 端不再把 rule-tag 寫進 prose"
      "（寫進去就是再造一個凍結快照，剝與寫會互相追著跑）",
      "（單一獨立來源，暫標待證實）" in open(
          os.path.join(_HERE, "pulse-enrich-apply.py"), encoding="utf-8").read(),
      False)

# ── 2026-08-10：一行重複的標題，讓站上六天沒有新文章 ──────────────────
# 潤稿端把 `## 事實` 寫進了 fact 的**值**裡（runbook 的 schema 範例當時就那樣寫），
# apply 又加一次自己的標題，檔案裡於是有兩行一樣的標題。而 pulse-gate.section()
# 取「標題到下一個 ## 之間」——下一個 ## 正好是那個重複的，**抽出來 0 字**，
# 低於 thin_fact_min_chars，13 則事件全部掛 thin_fact 卡死，而四個警報全綠。
# 而且不會自癒：那幾則的 enriched 已是 true、佔位詞也沒了，prep 不會再挑它們。
# 經過見 references/incidents/2026-08-10-the-heading-that-emptied-the-fact.md。
_ea_spec = importlib.util.spec_from_file_location(
    "pulse_enrich_apply", os.path.join(_HERE, "pulse-enrich-apply.py"))
_ea = importlib.util.module_from_spec(_ea_spec)
_ea_spec.loader.exec_module(_ea)
acase("潤稿寫回：值開頭那一行自己的段落標題要剝掉"
      "（不剝的話檔案裡會有兩行標題，gate 抽 section 抽到 0 字，每一則都掛 thin_fact）",
      [_ea.strip_own_heading("事實", "## 事實\nNVIDIA 發表了新的東西。"),
       _ea.strip_own_heading("事實", "## 事實：\nNVIDIA 發表了新的東西。"),
       _ea.strip_own_heading("事實", "## 事實：NVIDIA 發表了新的東西。"),
       _ea.strip_own_heading("脈絡", "## 脈絡\n## 脈絡\n放在什麼背景才看得懂。")],
      ["NVIDIA 發表了新的東西。", "NVIDIA 發表了新的東西。",
       "NVIDIA 發表了新的東西。", "放在什麼背景才看得懂。"])
# 剝過頭比不剝更難發現：它會靜靜吃掉內容，而檔案看起來完全正常。
acase("潤稿寫回：沒有標題的值原樣不動，別段的標題與內文中間的 ## 都不能被吃掉"
      "（剝過頭會靜靜少一段，比不剝更難發現）",
      [_ea.strip_own_heading("事實", "NVIDIA 發表了新的東西。"),
       _ea.strip_own_heading("事實", "本則提到 ## 事實 這三個字但不在開頭。"),
       _ea.strip_own_heading("事實", "## 影響\n這是別段的標題，不該剝。")],
      ["NVIDIA 發表了新的東西。", "本則提到 ## 事實 這三個字但不在開頭。",
       "## 影響\n這是別段的標題，不該剝。"])
# 真正的判準：走完整條 apply → gate，斷言 gate 抽得到內容。純函式對而呼叫端
# 沒接，這一格等於不存在——M198 就是這樣活下來的。
_gate_spec2 = importlib.util.spec_from_file_location(
    "pulse_gate_eh", os.path.join(_HERE, "pulse-gate.py"))
_gm2 = importlib.util.module_from_spec(_gate_spec2)
_gate_spec2.loader.exec_module(_gm2)
with _tf2.TemporaryDirectory() as _td_eh:
    _ev_eh = Path(_td_eh) / "Events"
    _ev_eh.mkdir(parents=True)
    (_ev_eh / "e.md").write_text(
        "---\nid: evt-x\nstatus: review\n---\n\n"
        "## 事實\n待編輯\n\n## 證據\n- [[Sources/src-a|src-a]]\n\n"
        "## 脈絡\n待編輯\n\n## 影響\n待編輯\n\n## 判斷\n待編輯\n\n"
        "## 下一個訊號\n待編輯\n", "utf-8")
    (Path(_td_eh) / "r.json").write_text(_json.dumps({"evt-x": {
        "summary": "一句話摘要，長度要過門檻所以寫長一點點。",
        "fact": "## 事實：NVIDIA 在官方部落格宣布一座新的資料中心，規模與時程未揭露。",
        "context": "## 脈絡\n這是算力往新興市場擴張的一個案例。",
        "impact": "## 影響\n對區域算力供給的實質貢獻，證據不足以評估。",
        "judgment": "## 判斷\n目前只有單一來源，先當成有這件事。",
        "next_signal": "## 下一個訊號\n看有沒有第二個獨立來源描述同一件事。",
    }}, ensure_ascii=False), "utf-8")
    _rc_eh = _subprocess.run(
        [sys.executable, os.path.join(_HERE, "pulse-enrich-apply.py"),
         "--in", str(Path(_td_eh) / "r.json")],
        capture_output=True, text=True, env=dict(os.environ, VAULT_DIR=_td_eh))
    _body_eh = (_ev_eh / "e.md").read_text("utf-8").split("\n---", 2)[-1]
    _fact_eh = _gm2.section(_body_eh, "事實")
acase("潤稿寫回 → 門禁：走完整條鏈，gate 抽得到「事實」而不是 0 字"
      "（2026-08-10 就是這一格 0 字，13 則全部掛 thin_fact，站上六天沒有新文章）",
      [_rc_eh.returncode, _body_eh.count("## 事實"), len(_fact_eh) >= 20],
      [0, 1, True])
# runbook 的 schema 範例就是這次的源頭：它把標題寫進了值裡，而潤稿端照著填。
acase("潤稿 runbook：schema 範例的值裡不准出現段落標題（那是這次事故的源頭）",
      [ln.strip() for ln in open(
          os.path.join(_HERE, "enrich-runbook.md"), encoding="utf-8").read().splitlines()
       if _re.match(r'"(fact|context|impact|judgment|next_signal)":\s*"##', ln.strip())],
      [])

# ── 首頁頭條：先框時間窗口，再在窗口裡比信心 ────────────────────────
# 舊版是 `max(events, key=confidence)`，一個沒有時間邊界的全域極值。旁邊的註解
# 寫著「兩者在平常的日子重合，正好在有大事的那天分岔」——實測**不重合、也不是
# 偶爾分岔，是天天分岔**：頭條停在 2026-07-25（c100）八天沒動，而最新是 08-04。
# 原因是 confidence 上限就是 100、60 則裡只有一則到頂，而 54/60 擠在 73。
# 一個在九成事件上沒有鑑別力的數字，扛著全站最顯眼的 h1。
import datetime as _hdt  # noqa: E402


def _hev(day, conf, eid=None):
    return {"id": eid or f"{day}-{conf}", "date": day, "confidence": conf}


_H_TODAY = _hdt.date(2026, 8, 2)
# 窗口內：07-30 c80 勝過 07-27 c83 之外的；窗口外那則 c100 不該再壓著頭版。
_H_EVENTS = [_hev("2026-07-30", 80, "new-80"), _hev("2026-07-29", 73, "new-73"),
             _hev("2026-07-20", 100, "old-100")]
acase("首頁頭條：窗口外的高分事件不再壓著頭版"
      "（舊版是全域極值——實測讓一則 c100 停在 h1 八天，而 confidence 上限就是"
      " 100、60 則裡只有一則到頂，所以那不是「偶爾」，是「幾乎永遠」）",
      _rmod.pick_lead(_H_EVENTS, _H_TODAY)[0]["id"], "new-80")
# 窗口一加，同分就從罕見變成常態（窗口內大半是 73）。舊版同分取最新是**呼叫端
# 排序的副作用**（build_home 拿到的 events 剛好 date 新到舊），不是選法的決定——
# line 1574 那個 reverse=True 改掉，頭條會無聲變成同分裡最舊的那一則。
_H_TIE = [_hev("2026-07-28", 73, "older"), _hev("2026-08-01", 73, "newer")]
acase("首頁頭條：窗口內同分取最新，而且不依賴呼叫端的排序"
      "（同分在加了窗口之後是常態；靠 max() 取第一個極大值等於把決定權交給"
      "別人家的 sort，那行改掉頭條會無聲換人）",
      [_rmod.pick_lead(_H_TIE, _H_TODAY)[0]["id"],
       _rmod.pick_lead(list(reversed(_H_TIE)), _H_TODAY)[0]["id"]],
      ["newer", "newer"])
# 窗口空＝已經七天沒有新的已發布事件。退回的必須是**最新那一則**，不是「全體
# 信心最高」——後者正是這次要修掉的東西，而且頁面那句退回說明寫的是「目前最新
# 的一則」。第一版兩條路共用同一條 key，實跑才發現退回時選到八天前那則 c100。
acase("首頁頭條：窗口空 → 退回最新那一則並標記 stale，不是退回全體信心最高"
      "（退回全體信心最高就是繞回舊行為，而且跟頁面那句「目前最新的一則」"
      "當場對不起來）",
      [_rmod.pick_lead(_H_EVENTS, _hdt.date(2027, 1, 1))[0]["id"],
       _rmod.pick_lead(_H_EVENTS, _hdt.date(2027, 1, 1))[1],
       _rmod.pick_lead(_H_EVENTS, _H_TODAY)[1],
       _rmod.pick_lead([], _H_TODAY)],
      ["new-80", True, False, (None, False)])
# 版名底下那一行、左欄、右欄都宣稱了一個「日」。實測 2026-08-02 那天：屬於今天的
# Event 是 0 則，而左欄九則跨 07-29~08-04（六天）、右欄印的是累計 60。
# 只掃「讀者看得到的字串常數」——註解與 docstring 裡會提到舊標籤（為了解釋為什麼
# 改掉），拿整份原始碼去 grep 會打中那些解釋。同一條分支上第四次踩這個形狀了。
import ast as _ast_home  # noqa: E402
_R_SRC_HOME = "\n".join(
    _n.value for _n in _ast_home.walk(_ast_home.parse(open(
        os.path.join(_HERE, "pulse-render.py"), encoding="utf-8").read()))
    if isinstance(_n, _ast_home.Constant) and isinstance(_n.value, str))
acase("首頁：三個標籤不得再宣稱「今日／本日」"
      "（實測今天 0 則，而它們分別印著六天的清單與累計 60——"
      "又一次「一個比事實寬的東西掛著事實的名字」）",
      [w for w in ("今日索引", "本日計數", "今日頭版")
       if w in _R_SRC_HOME], [])

# ────────────────────────── 站台可讀性（字級級距、泳道、文案）──────────
_R_CSS = _rmod.CSS
acase("字級：CSS 裡不得再有硬寫的字級"
      "（改版前 24 個字級，11 個擠在 0.8–1.15rem——1.01 跟 1.02 沒人看得出差別，"
      "但每次改版都要猜該用哪一個）",
      sorted(set(_re.findall(r"\bfont(?:-size)?:\s*([0-9.]+(?:px|rem))", _R_CSS))), [])
acase("字級：級距十三級，最小級不小於 11px"
      "（9px 的中文與等寬字是用猜的不是用讀的，而改版前有 27 處在用 9/10px；"
      "九個內文級距 + 三個大標 + 報頭那一級）",
      # 這裡原本寫 `_R_CSS.split("color-scheme:dark")[0]`——深色版整組退場之後
      # 那個 split 是空操作，切點早就不存在了。留著會讓下一個人以為 CSS 裡還有
      # 一塊深色，而且它「看起來有在限縮範圍」其實沒有。拿掉。
      [len(_re.findall(r"--fs-[a-z0-9]+:", _R_CSS)),
       "--fs-micro:.6875rem" in _R_CSS], [13, True])

# ── 底色：預設是哪一張紙，只准有一個地方說了算 ──────────────────────
# 2026-07-29 預設從米色換成白色。換法有兩種：把白色搬進 :root，或者米色留在
# :root 再加一個 [data-theme=…] 的白色版蓋回去。後者會讓「預設長什麼樣」同時
# 寫在兩個地方，而這個 repo 已經數過很多次那個形狀：一個事實兩份說法，平常
# 兩份一致，改的那天分岔，然後沒有東西變紅。
# 所以這裡測的不是「預設是白的」而已，還有「白的只有一份定義」。
_CSS_NC = _re.sub(r"/\*.*?\*/", "", _R_CSS, flags=_re.S)   # 先拆註解：註解裡提到
# 的選擇器不是選擇器。少了這一步，上面那段說明文字自己會被當成 CSS 讀進來——
# 同一個坑 `_shell_conflicts` 已經踩過一次。


def _canvas_of(sel):
    m = _re.search(_re.escape(sel) + r"\{([^}]*)\}", _CSS_NC)
    v = _re.search(r"--canvas:\s*([^;}]+)", m.group(1)) if m else None
    return v.group(1).strip() if v else None


def _hex6(c):
    c = (c or "").strip().lstrip("#").lower()
    return "".join(ch * 2 for ch in c) if len(c) == 3 else c


acase("底色：預設（沒有 data-theme 的時候）是白紙，米色是切過去的那一張；"
      "而且白色只有 :root 這一份定義——多一個 [data-theme] 的白色版就是多一份說法",
      [_canvas_of(":root"),
       sorted(set(_re.findall(r":root\[data-theme=([A-Za-z-]+)\]", _CSS_NC))),
       _canvas_of(":root[data-theme=newsprint]")],
      ["#fff", ["newsprint"], "#f4f1e8"])
# theme-color 是**第二份**「預設底色是什麼」的說法：手機瀏覽器拿它去染工具列。
# 改了 CSS 忘了改它，工具列就跟頁面差一個色階，而頁面本身完全正常。
# 兩邊都改錯的情況由上面那一條擋（那一條把 #fff 寫死在測試裡）。
_meta_tc = _re.search(r'name="theme-color" content="(#[0-9a-fA-F]{3,8})"',
                      _rmod.build_home([], {}, "now"))
acase("底色：手機工具列的 theme-color 跟預設畫布是同一個顏色",
      _hex6(_meta_tc.group(1) if _meta_tc else "（頁面裡沒有 theme-color）"),
      _hex6(_canvas_of(":root")))
# 切換鈕只寫得出一個名字。切回白色是**把屬性拿掉**，不是設一個白色的名字——
# 設名字等於在 CSS 裡再開一個白色區塊，回到上面那條在擋的事情。
_JS_FLAT = _re.sub(r"\s+", "", _rmod.JS)
acase("底色：切換鈕只寫得出 newsprint 一個名字，切回白色靠移除屬性",
      [sorted(set(_re.findall(r"setAttribute\('data-theme','([a-z-]+)'\)", _JS_FLAT))),
       "removeAttribute('data-theme')" in _JS_FLAT],
      [["newsprint"], True])

# 泳道的縱軸選公司不選產品線，是量出來的：41 則裡 36 則 fingerprint 是 null。
acase("泳道：縱軸是公司，缺公司的歸「其他」而不是丟掉"
      "（丟掉就是讓那幾則從畫面上消失，而它們是通過檢查的已發布事件）",
      [_rmod.lane_key({"company": "NVIDIA"}), _rmod.lane_key({"company": ""}),
       _rmod.lane_key({})], ["NVIDIA", "其他", "其他"])

def _tl_ev(i, day, company, track_slug="model-research"):
    return {"id": f"e{i}", "slug": f"s{i}", "title": f"T{i}", "summary": "S",
            "date": day, "date_display": day, "company": company,
            "confidence": 80, "coverage": "observed", "category": "", "track": ""}

# 刻度寫死用月，實測整條軸塌成一欄（41 則全在 2026-07）。
# 一張只有一欄的泳道圖比不畫更糟——它看起來像有資訊。
_tl_1m = _rmod.build_timeline(
    [_tl_ev(1, "2026-07-27", "NVIDIA"), _tl_ev(2, "2026-07-07", "OpenAI")], "now")
_tl_1y = _rmod.build_timeline(
    [_tl_ev(1, "2026-07-27", "NVIDIA"), _tl_ev(2, "2026-01-05", "OpenAI")], "now")
acase("泳道：刻度跟著資料跨度走——跨度在兩個月內用「天」，更長用「月」"
      "（寫死用月，單月資料會塌成一欄）",
      [int(_re.search(r"--cols:(\d+)", _tl_1m).group(1)) > 5,
       int(_re.search(r"--cols:(\d+)", _tl_1y).group(1)) <= 12], [True, True])
# 中間的空格子本身是資訊：那幾天這家公司沒有動靜。
acase("泳道：日刻度用**連續**日期，中間沒事件的日子照樣留格"
      "（只印有事件的日子，每一家看起來都一樣忙）",
      int(_re.search(r"--cols:(\d+)", _tl_1m).group(1)), 21)
acase("泳道：每一則事件都畫得出一個點，一則都不能少",
      _tl_1m.count('class="lane-dot'), 2)

# ── 一格塞太多點就退成「幾則」的方塊。這是為了長期累積：今天一格最多 4 點，
#    半年後改用月刻度，一家公司一個月二十幾則會把格子撐爆——一堆擠在一起的點
#    既讀不出數量也點不到。
_tl_dense = _rmod.build_timeline(
    [_tl_ev(i, "2026-07-27", "NVIDIA") for i in range(7)]
    + [_tl_ev(90, "2026-07-20", "OpenAI")], "now")
acase("泳道：一格超過門檻就退成計數方塊，而且**數字要對**"
      "（擠成一團的點讀不出數量也點不到；印錯數字比不印更糟）",
      [_tl_dense.count('class="lane-dot'), ">7<" in _tl_dense,
       _rmod.LANE_DOT_MAX], [1, True, 3])
# 事件守恆：畫出來的點 + 方塊上的數字，要等於事件總數。
_dots = _tl_dense.count('class="lane-dot')
_many = sum(int(x) for x in _re.findall(r'lane-many[^>]*>(\d+)<', _tl_dense))
acase("泳道：點數 + 方塊上的數字 = 事件總數（少一則就是有事件從畫面上消失了）",
      _dots + _many, 8)

# hover 被裁掉的根因：tip 住在 overflow-x:auto 的捲動容器裡。
# CSS 規範：一軸不是 visible，另一軸的 visible 會算成 auto——z-index 救不了。
# 浮層拿掉了。逃出捲動容器只解決「被裁掉」，沒解決「蓋住東西」——
# 而它蓋住的正好是日期欄頭，也就是讀者當下最需要的座標。
# 浮層在密集格線上永遠會遮到某個東西，那不是位置算得夠不夠好的問題。
acase("泳道：詳情用固定在格線下方的判讀列，不用浮層"
      "（浮層往上彈就壓在日期欄頭上，而那是「這個點是哪一天」的唯一線索）",
      [_tl_1m.count('id="lane-readout"'), "lane-tip" in _tl_1m,
       _tl_1m.find('id="lane-readout"') > _tl_1m.find('class="lane-grid"')],
      [1, False, True])
acase("泳道：判讀列一開始就有話說，不是一塊空白"
      "（空的框讀者不知道要做什麼，而它佔著版面）",
      "滑過或用鍵盤選一個點" in _tl_1m, True)
# 說明句原本寫死「一格一個月」，而刻度是動態的——截圖那張其實是一天一格。
# 一句寫死的說明配一個會變的實作，就是在對讀者說一件當下不成立的事。
acase("泳道：說明句的刻度要跟實際畫出來的一致（寫死就會在另一種資料下說謊）",
      ["一格一天" in _tl_1m, "一格一個月" in _tl_1y], [True, True])
acase("泳道判讀列：帶得到回填標記（泳道是拿來掃視的，點進去才知道就太晚了）",
      'data-tip-c="回填"' in _tl_html, True)
acase("泳道：沒有 JS 時仍看得到內容（每個點都留 title）",
      _tl_1m.count("<a class=\"lane-dot") == _tl_1m.count(' title="'), True)

# 兩個 h2 在首頁上下緊鄰，改版前一個 27.2px 一個 24px。
_css_clamps = _re.findall(r"font-size:\s*clamp\([^)]*\)", _R_CSS)
acase("字級：大標也在級距上——font-size 的 clamp() 只准出現在 :root 的 token 定義裡"
      "（散在各處的 clamp 就是繞過級距，兩個緊鄰的標題因此差 3px 而沒有理由）",
      _css_clamps, [])
# 首頁改版前自成一套 .mh-*：eyebrow 字距 .3em vs kicker .18em、標題 weight
# 720 vs 680、字距 -.03em vs -.02em、副標等寬 vs 內文字體、統計一行文字 vs
# 三格 page-status——同一種東西（一頁的標頭）長成兩套，改一邊另一邊就分岔。
_HEAD_SRC = open(os.path.join(_HERE, "pulse-render.py"), encoding="utf-8").read()
acase("標頭：四頁共用同一個 hero 元件，首頁只差一個 lead 修飾詞"
      "（.mh-* 那一套整組退場，CSS 與 HTML 都不得再有）",
      [_c for _c in ("mh-title", "mh-eyebrow", "mh-sub", "mh-meta", "masthead")
       if _c in _R_CSS or _c in _HEAD_SRC.split('"""')[-1]], [])
# 2026-07-28 改成報紙版型：首頁不再是「放大版的其他頁」，它是頭版——h1 是
# 頭條標題，其他四頁的 h1 是頁首標題。兩者本來就該不一樣大，但**各走一個
# token**，不准在某一頁另開一組規則（那正是 .mh-* 那次的病）。
acase("字級：首頁頭條與其他四頁的頁首各走一個 token，兩個都在級距上",
      [".lead-story h1{font-family:var(--serif);font-size:var(--fs-display)" in _R_CSS,
       _R_CSS.count(".hero h1{font-family:var(--serif);font-size:var(--fs-h1)")],
      [True, 1])


# --- .shell 的置中不得被同框的規則蓋掉 ------------------------------------
# 上面那一條是綠的，而 2026-07-28 的首頁是壞的：整個 hero 貼齊左邊界（實測
# x=0，其他四頁 x=323），h1 的 color 還一起吃到 --muted。原因是 `lead` 這個
# 名字被兩個東西共用——事件摘要段落 `.lead` 與 hero 的尺寸修飾詞 `.hero.lead`
# ——而裸的 `.lead{margin:0}` 排在 `.shell{margin-inline:auto}` 之後、同權重。
#
# 上面那一條為什麼抓不到：它在 CSS 字串裡 grep `.hero.lead h1{...}`，那串字
# 一直都在。**在原始碼裡找字，不是在產出裡量**——這是這條分支上第九次同一個
# 形狀。所以這一條改成把規則跟產出**兜起來**算：
#
#   `.shell` 擁有 width 與 margin-inline。任何跟它出現在同一個元素上、
#   又會命中那個元素的「無組合子」規則，都不得再設 width 或 margin。
#
# 誠實的邊界：只看得懂「tag 與 class 組成、沒有組合子」的選擇器（`.a`、
# `p.a`、`.a.b`）。帶空白或 `>` 的後代選擇器一律跳過——那需要一個真的 CSS
# 引擎，這裡不假裝有。所以它擋得住這一次的形狀，擋不住所有形狀。
_SHELL_OWNS = _re.compile(r"(^|;)\s*(margin(?:-inline|-left|-right)?|width)\s*:")
_SIMPLE_SEL = _re.compile(r"^([a-z]+)?((?:\.[A-Za-z0-9_-]+)+)$")


def _shell_conflicts(css, pages):
    # 先拆註解再拆 @media 外殼。少了拆註解這一步，註解會被當成選擇器的一部分黏在
    # 後面那條規則前面，於是那條規則永遠比對不到——**檢查看起來全綠，其實根本沒
    # 看到它**。這一版第一次跑就是這樣過的，是下面那條反向測試把它揪出來的。
    flat = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)
    flat = _re.sub(r"@[a-z-]+[^{]*\{", "", flat)
    rules = []
    for sel, body in _re.findall(r"([^{}]+)\{([^}]*)\}", flat):
        if not _SHELL_OWNS.search(body):
            continue
        for one in (s.strip() for s in sel.split(",")):
            m = _SIMPLE_SEL.match(one)
            if not m or one == ".shell":
                continue
            rules.append((one, m.group(1) or "", set(m.group(2).split(".")[1:]), body))
    bad = set()
    for html in pages:
        for tag, attr in _re.findall(r'<([a-z]+)[^>]*\sclass="([^"]*)"', html):
            classes = set(attr.split())
            if "shell" not in classes:
                continue
            for sel, rtag, rcls, body in rules:
                if (not rtag or rtag == tag) and rcls <= classes:
                    bad.add(f'<{tag} class="{attr}"> 撞上 {sel}{{{body}}}')
    return sorted(bad)


# 四頁都要產一次：`shell` 的同框組合各頁不同（首頁 `hero lead shell`、
# 另外三頁 `compact hero shell`、領域趨勢多一個 `line-section section shell`）。
# 只產首頁的話，正好漏掉最多的那幾種。
_EV1 = {"id": "e1", "date": "2026-07-20", "date_display": "2026-07-20",
        "company": "OpenAI", "title": "T", "title_zh": "", "summary": "s",
        "track": "模型能力與研究", "confidence": 80, "heat": None, "impact": 50,
        "value": 60, "slug": "t", "coverage": "single", "independent_sources": 1,
        "independent": 1, "evidence": [], "status": "published",
        "category": "research", "keywords": [], "layers": {}}
_PAGES = [_rmod.build_home([_EV1], {}, "now"), _rmod.build_lines([_EV1], {}, "now"),
          _rmod.build_timeline([_EV1], "now"), _rmod.build_signals([], {}, "now")]
acase("版型：.shell 的置中不得被同框的規則蓋掉"
      "（`lead` 一個名字兩個用途，裸的 .lead{margin:0} 把首頁 hero 推到左邊界）",
      _shell_conflicts(_R_CSS, _PAGES), [])
# 反向：這個檢查真的抓得到那個形狀，不是永遠回空清單。
# 站上現在已經沒有「裸類別跟 .shell 同框」的例子了（p.lead 綁了 tag），所以
# 反向測試改餵一個合成的：檢查器本身要會紅，不能因為現況乾淨就永遠回空。
_FAKE_PAGE = '<section class="lede shell"><h1>x</h1></section>'
acase("版型：那個檢查真的會紅——餵一個同框又設 margin 的合成例子",
      len(_shell_conflicts(_R_CSS + "\n.lede{margin:0}", [_FAKE_PAGE])), 1)
acase("版型：而乾淨的現況不會誤報", _shell_conflicts(_R_CSS, [_FAKE_PAGE]), [])
# 五頁各恰好一個 h1，而且首頁那一個是頭條、不是頁首。
# 「一頁沒有 h1」是結構壞掉，不是內容比較少——空狀態也要有。
acase("版型：五頁各恰好一個 h1；首頁的 h1 在頭條裡，其他四頁在頁首裡",
      [[_p.count("<h1") for _p in _PAGES],
       bool(_re.search(r'class="lead-story"[\s\S]{0,600}?<h1', _PAGES[0])),
       _PAGES[0].count('class="hero'),
       _rmod.build_home([], {}, "now").count("<h1")],
      [[1, 1, 1, 1], True, 0, 1])
# kicker 是等寬、字距 .18em 的小標。中文在那個字距下會被拆開，
# 而且它跟旁邊的 h1 同語言、資訊重複。
# 點了導覽上的「關鍵變化」，落地那一頁的 h1 完全不含那四個字——讀者沒有辦法
# 確認自己到了。其他三頁的導覽字都出現在 h1 裡。
# 這一條第一版把 (導覽字, h1) 的對照**寫死在測試裡**——那是拿測試自己寫的字
# 去比對，碼怎麼改都會過（M152 因此活下來）。第八次同一個形狀。
# 改成真的產一次首頁、把 h1 抓出來，跟 NAV 裡的字比。
# 報紙版型下首頁的 h1 是頭條標題，不會含導覽那四個字——但原本的顧慮沒有變：
# 導覽反白只存在於導覽上，讀者往下捲之後只剩版面本身。所以那句話搬到版面
# 鑑別線（報紙的分區名），測試跟著搬，不是刪掉了事。
_home_rubric = _re.search(r'class="page-rubric">(.*?)</div>', _PAGES[0]).group(1)
acase("導覽：點了「關鍵變化」，落地那一頁自己要說得出它是哪一版"
      "（導覽的反白捲一下就看不到了）",
      [_rmod.NAV[0][1] in _home_rubric, _rmod.NAV[0][1]], [True, "關鍵變化"])

# ── 頭版：頭條由規則挑 ────────────────────────────────────────
# 改版前那一區叫「這幾則最值得看」，底下排的卻是時間——標題宣稱了一個排序，
# 實作用的是另一個。上面 pick_lead 那幾條釘的是判準本身；這幾條走**真的
# build_home()**，釘的是「呼叫端有沒有照著接」——判準對而接錯，畫面一樣是錯的。
#
# 日期用「相對今天」算，不寫死。第一版寫死 2026-07-01／07-20，加了時間窗口之後
# 那兩個日期落在窗口外，測試當場紅——但它紅的不是碼壞了，是**測試自己過期了**。
# 一個會隨時鐘漂掉的 fixture，遲早會在某個沒有人改碼的早上變紅。
_h_today = _clk.display_date(_clk.utc_now())
_h_day = lambda n: (_h_today - _dt_m.timedelta(days=n)).isoformat()
_EV_HI = dict(_EV1, id="hi", slug="hi", title="HI", title_zh="分數最高那則",
              confidence=95, date=_h_day(3), date_display=_h_day(3))
_EV_NEW = dict(_EV1, id="new", slug="new", title="NEW", title_zh="最新那則",
               confidence=60, date=_h_day(1), date_display=_h_day(1))
# 窗口外的高分那則：舊版的全域極值會把它擺上 h1，而它可能是一個月前的事。
_EV_OLD = dict(_EV1, id="old", slug="old", title="OLD", title_zh="窗口外那則",
               confidence=100, date=_h_day(40), date_display=_h_day(40))
_home_pick = _rmod.build_home([_EV_NEW, _EV_HI, _EV_OLD], {}, "now")  # 進來是新到舊
# 抓不到就回一句話，不要讓 re 丟 AttributeError 把整份 selftest 打斷：
# 崩潰只說「這裡爆了」，一個錯的答案才說「哪個判斷錯了」。
_pick = _re.search(r'class="lead-story"[\s\S]*?<h1[^>]*>[\s\S]*?>([^<]+)</a>', _home_pick)
acase("頭版：頭條由規則挑（窗口內信心最高），不是「最新那一則」、"
      "也不是「一個月前那則滿分的」（走真的 build_home，釘的是呼叫端有沒有照著接）",
      [_pick.group(1) if _pick else "（產出裡找不到頭條）",
       "lead-stale" in _home_pick],
      ["分數最高那則", False])

# ── 事件頁：長文版的兩條紅線延伸 ──────────────────────────────
_ev_pg = _rmod.build_event_page(
    dict(_EV1, title="English Title", title_zh="中文標題", tier=2,
         layers={"事實": "f", "判斷": "j"},
         evidence=[{"sid": "src-a", "url": "u1", "title": "T"}]),
    [], {}, {}, "now")
acase("事件頁：譯文旁邊永遠印得到原標題（讀者無法從一句中文回推它翻自什麼）",
      ["原標題：English Title" in _ev_pg, "中文標題" in _ev_pg], [True, True])
_ev_no_tier = _rmod.build_event_page(
    dict(_EV1, tier=None, layers={"事實": "f"}, evidence=[]), [], {}, {}, "now")
acase("事件頁：證據層級沒標時印「未標」不印問號"
      "（問號讀起來像壞掉了，未標讀起來才是實話）",
      ["未標" in _ev_no_tier, "Tier ?" in _ev_no_tier], [True, False])

# ── 鑑別線與頁首不得講同一句話 ────────────────────────────────
# 版面鑑別線接手了「這一版收什麼」之後，hero 的副標就是同一句話的第二份。
# 四頁各印兩份，改一邊另一邊分岔——這個 repo 抓過很多次的形狀，換到文案上。
def _deck_dupes(page):
    r = _re.search(r'class="page-rubric">[\s\S]*?<span>(.*?)</span>', page)
    h = _re.search(r'<section class="hero[\s\S]*?</section>', page)
    return bool(r and h and r.group(1).strip() and r.group(1) in h.group(0))


acase("版型：版面鑑別線那一句不得在頁首再印一次",
      [_deck_dupes(_p) for _p in _PAGES], [False, False, False, False])

# ── 朗讀順序＝頭條優先 ────────────────────────────────────────
# DOM 順序就是螢幕報讀器與「關掉 CSS」時的閱讀順序。索引排在頭條前面的話，
# 那些讀者拿到的第一段永遠是目錄，不是今天發生什麼。桌機的三欄位置改由
# grid-column 指定，視覺與朗讀因此可以不一樣——但**朗讀那一邊要是對的那一邊**。
# 用 find 不用 index：頭條整塊被拿掉的時候 index 會丟 ValueError，
# selftest 當場中斷——**一個崩潰會蓋掉一個判斷錯誤**，而崩潰只告訴你「這裡爆了」。
# 這是 2026-07-28 c2 那一輪學到的同一句話，第二次用上。
_front_pos = [_PAGES[0].find('class="%s"' % c)
              for c in ("lead-story", "idx", "tally-col")]
acase("頭版：DOM 裡頭條排在索引與側欄前面（報讀器與無 CSS 時的閱讀順序）",
      [all(x >= 0 for x in _front_pos), _front_pos == sorted(_front_pos)],
      [True, True])

# ── 報頭只有一份實作 ──────────────────────────────────────────
acase("報頭：五頁共用同一份實作，舊的那一套整組退場"
      "（同一種東西留兩份，改一邊另一邊就悄悄分岔——.mh-* 那次就是這樣）",
      [[('class="nameplate' in _p) for _p in _PAGES],
       _R_CSS.count(".nameplate{"),
       [_c for _c in ("mh-title", "mh-eyebrow", "mh-sub", "mh-meta",
                      "topbar", "brand-mark", "icon-btn")
        if _c in _R_CSS or _c in _HEAD_SRC.split('"""')[-1]]],
      [[True, True, True, True], 1, []])

# GitHub 動能那一頁原本是一整份手抄的 HTML：自己的 topbar、自己的 <style>、
# 自己的 hero。抄出來的東西會漂，而且已經漂了——手機上它完全沒有導覽。
_GH_SRC = open(os.path.join(_HERE, "pulse-github.py"), encoding="utf-8").read()
acase("GitHub 動能：那一頁走共用的 page_layout，不再自己抄一份 chrome"
      "（抄出來的那份沒有 mobile-nav：@media(max-width:720px) 會把 desktop-nav "
      "藏起來，手機讀者進去之後除了上一頁沒有出路）",
      ["page_layout(" in _GH_SRC, "<header class=\"topbar\">" in _GH_SRC,
       "GH_VIEW" in _GH_SRC], [True, False, False])
# 這一條第一版用 grep 原始碼查 `<style>`，結果打中的是**我自己寫在 docstring
# 裡解釋這件事的那句話**。同一個形狀這條分支上已經第七次：
# 判斷「產出裡有沒有這個東西」不能靠在原始碼裡找字。改成產一次頁面再看。
_gh_spec = importlib.util.spec_from_file_location(
    "pulse_github", os.path.join(_HERE, "pulse-github.py"))
_ghmod = importlib.util.module_from_spec(_gh_spec)
_gh_spec.loader.exec_module(_ghmod)
_GH_PAGE = _ghmod.gh_page("2026-07-28 08:00 台北時間")
acase("GitHub 動能：產出的頁面裡沒有自己的 <style>，樣式全走共用樣式表"
      "（六個硬寫字級、零個級距 token，而收字級那一輪它整份被跳過）",
      "<style>" in _GH_PAGE, False)
acase("GitHub 動能：產出的頁面帶得到手機導覽、頁尾、深淺色切換"
      "（手抄那份三個都沒有——手機讀者進去之後除了上一頁沒有出路）",
      [c for c in ("mobile-nav", "footer", "data-theme-toggle")
       if c not in _GH_PAGE], [])
acase("GitHub 動能：產出的頁面不再帶那兩句已經被換掉的宣稱"
      "（它不經過 pulse-render，所以四頁都改完了它還留著）",
      [w for w in ("0 LLM", "零 LLM") if w in _GH_PAGE], [])

# ── GitHub：竄升要兩個軸 ──────────────────────────────────────
# 只有絕對星速（Δ★/天）的時候，榜永遠是大 repo 的榜：同樣漲 200 顆，10 萬星的
# 專案是日常、2 千星的是暴動，而排序看不出差別。**用一個對大者有系統性優勢的
# 指標代表「誰在竄」**——這個 repo 一直在抓的形狀，這次長在排名上。
import datetime as _gdt  # noqa: E402

_g_now = _gdt.datetime(2026, 7, 29, tzinfo=_gdt.timezone.utc)
_g_prev_ts = (_g_now - _gdt.timedelta(days=1)).timestamp()


def _grepo(name, stars, created="2023-01-01"):
    return {"full_name": name, "name": name, "url": "u", "desc": "", "stars": stars,
            "language": "", "topics": [], "created": created, "pushed": "2026-07-28"}


# 大的漲 300（+0.3%/天），小的漲 200（+20%/天）——絕對輸、相對大贏。
_g_cur = {"big/repo": _grepo("big/repo", 100300),
          "small/repo": _grepo("small/repo", 1200),
          "tiny/repo": _grepo("tiny/repo", 150),
          "fresh/repo": _grepo("fresh/repo", 9000)}
_g_state = {"big/repo": {"stars": 100000, "ts": _g_prev_ts},
            "small/repo": {"stars": 1000, "ts": _g_prev_ts},
            "tiny/repo": {"stars": 100, "ts": _g_prev_ts}}
_g_top, _g_surge = _ghmod.rank(_g_cur, _g_state, _g_now, 10)

acase("GitHub：兩個榜的第一名不是同一個（絕對看量、相對看竄升——"
      "合成一個分數就等於再造一個代理指標，而權重沒有人答得出來）",
      [_g_top[0]["full_name"], _g_surge[0]["full_name"]],
      ["big/repo", "small/repo"])
acase("GitHub：首次觀測不給代理值——兩點才有斜率，一點沒有"
      "（舊版拿「星數÷建立至今天數」當動能，那是歷史平均不是現在的速度）",
      [_g_top[-1]["full_name"], _g_top[-1]["velocity"],
       "fresh/repo" in [x["full_name"] for x in _g_surge]],
      ["fresh/repo", None, False])
# tiny/repo 上一次是 100 顆（低於門檻）→ 不進榜；big/repo 雖然相對只有
# +0.3%/天，但它**有資格上這個榜**，只是排在後面——門檻擋的是低基數，不是大 repo。
acase(f"GitHub：低於 {_ghmod.SURGE_FLOOR} 顆星不進竄升榜，其餘照相對增量排"
      "（10 顆變 20 顆就是 +100%，那讀起來比任何真的竄升都猛）",
      [x["full_name"] for x in _g_surge], ["small/repo", "big/repo"])
acase("GitHub：兩榜互相標名次（同一個 repo 兩邊都上，本身就是資訊）",
      [_g_top[0].get("rank_velocity"), _g_surge[0].get("rank_surge"),
       _g_surge[0].get("rank_velocity")],
      [1, 1, 2])
acase("GitHub：頁面把兩個軸各自偏袒誰寫出來，門檻也印得到"
      "（一個沒有寫出來的門檻，跟沒有門檻一樣會誤導）",
      [w for w in ("偏袒大 repo", "id=\"floor\"", "竄升榜", "星速榜")
       if w not in _GH_PAGE], [])

# ── GitHub：名次變動（榜上那個「排序變動」圖示的資料層）────────────
# 這一格最容易壞的方式不是算錯名次，是把「量不到」跟「持平」印成同一個東西：
# 榜上一半是首次觀測的那天，一整排「持平」看起來會像「今天大家都沒動」，
# 而事實是今天根本沒有昨天可比。同一種形狀這個 repo 已經抓過好幾次
#（未量測的因子印 0、抓不到榜的那一班寫 0），所以這裡拆成六種、各自可判。
acase("GitHub 名次變動：六種狀態各回各的，而且沒有一種叫 0"
      "（把「量不到」跟「持平」擠成同一個值，等於這一格不存在）",
      [_ghmod.rank_move({"rank_velocity": 7}, "rank_velocity", 4),
       _ghmod.rank_move({"rank_velocity": 2}, "rank_velocity", 5),
       _ghmod.rank_move({"rank_velocity": 3}, "rank_velocity", 3),
       _ghmod.rank_move({"rank_velocity": None}, "rank_velocity", 6),
       _ghmod.rank_move(None, "rank_velocity", 6),
       _ghmod.rank_move({"stars": 1, "ts": 2}, "rank_velocity", 6)],
      [("up", 3, 7), ("down", 3, 2), ("flat", 0, 3), ("entered", None, None),
       ("first_seen", None, None), ("no_baseline", None, None)])
# 「榜外」跟「上一版根本沒記名次」長得很像，但差別在畫面上是致命的：判成
# entered 的話，這版碼上線的第一天整個榜會標「新進榜」——一個看起來很有內容、
# 實際上只是資料還沒長出來的畫面，而且沒有任何東西會讓它變紅。
acase("GitHub 名次變動：舊 schema（沒有名次欄位）判成「量不到」，不是「新進榜」"
      "（判成新進榜的話，這版上線第一天整榜都會標新進榜，而那是假的）",
      [_ghmod.rank_move({"stars": 1, "ts": 2}, "rank_velocity", 1)[0],
       _ghmod.rank_move({"stars": 1, "ts": 2, "rank_velocity": None},
                        "rank_velocity", 1)[0]],
      ["no_baseline", "entered"])
# 兩個榜共用同一批 dict 物件（rows 只建一次，by_velocity / by_surge 都指向它）。
# 欄位不帶軸名後綴的話，後算的那個榜會蓋掉前一個，而畫面上兩邊會顯示同一個變動。
_g_state2 = {"big/repo": {"stars": 100000, "ts": _g_prev_ts,
                          "rank_velocity": 2, "rank_surge": None},
             "small/repo": {"stars": 1000, "ts": _g_prev_ts,
                            "rank_velocity": 1, "rank_surge": 3},
             "tiny/repo": {"stars": 100, "ts": _g_prev_ts,
                           "rank_velocity": 3, "rank_surge": 1}}
_g_top2, _g_surge2 = _ghmod.rank(_g_cur, _g_state2, _g_now, 10)
_g_by2 = {r["full_name"]: r for r in _g_top2}
acase("GitHub 名次變動：兩個榜各算各的，欄位不互相覆蓋"
      "（同一個 repo 在星速榜上升、在竄升榜是新進榜——共用一組欄位的話"
      "兩邊會顯示後算的那一個）",
      [_g_by2["big/repo"].get("rank_move_velocity"), _g_by2["big/repo"].get("rank_places_velocity"),
       _g_by2["big/repo"].get("rank_move_surge"),
       _g_by2["small/repo"].get("rank_move_velocity"), _g_by2["small/repo"].get("rank_places_velocity"),
       _g_by2["small/repo"].get("rank_move_surge"), _g_by2["small/repo"].get("rank_places_surge")],
      ["up", 1, "entered", "down", 1, "up", 2])
# ── 名次位移不是「每天」的量，所以每一列要帶自己的基線年紀 ──────────
# 星速除以實際天數（days），名次位移沒有除以任何東西。兩者在每晚都抓得到的
# repo 上看起來一樣，正好在基線舊掉的那幾條上分岔——而那不是理論值：
# _github/state.json 每晚有幾條沒被搜到（實測 2026-07-26～31 每班 1～6 條），
# 它們的基線就這樣一天一天變老。一個 repo 掉出搜尋六天再回來，箭頭上的「3」
# 是六天的位移，而頁面第一版的圖例寫著「榜單一天更新一次」。
_g_state3 = {"big/repo": {"stars": 100000, "ts": (_g_now - _gdt.timedelta(days=6)).timestamp(),
                          "rank_velocity": 1, "rank_surge": None},
             "small/repo": {"stars": 1000, "ts": (_g_now - _gdt.timedelta(hours=2)).timestamp(),
                            "rank_velocity": 2, "rank_surge": None},
             "tiny/repo": {"stars": 100, "ts": _g_prev_ts, "rank_velocity": 3, "rank_surge": None}}
_g_by3 = {r["full_name"]: r for r in _ghmod.rank(_g_cur, _g_state3, _g_now, 10)[0]}
acase("GitHub 名次變動：每一列帶自己的基線年紀，六天前的基線不會被算成一天"
      "（名次位移沒有除以天數，所以「隔了幾天」只能一列一列說；"
      "寫死一個節奏就是把六天的位移講成昨天的）",
      [_g_by3["big/repo"]["baseline_days"], _g_by3["tiny/repo"]["baseline_days"],
       _g_by3["fresh/repo"]["baseline_days"]],
      [6.0, 1.0, None])
# days 有 max(..., 0.5) 的下限，那是**除法的護欄**——一天跑很多班時不讓 Δ 被除進
# 一個假的大數字。拿它當「隔了幾天」印給讀者看，同一天的第二班就會說「跟半天前
# 那一版比」，而基線其實是上一班（可能是昨天）的。護欄跟事實不是同一個數字。
acase("GitHub 名次變動：印給讀者的年紀是原始值，不是 days 那個 0.5 下限"
      "（護欄是為了讓除法不爆掉，不是為了描述事實——兩者只在同一天跑第二班時"
      "分岔，而那正是它會說錯話的那一班）",
      [_g_by3["small/repo"]["baseline_days"], _g_by3["small/repo"]["velocity"]],
      [0.1, 400.0])
acase("GitHub 名次變動：頁面把那一列的基線年紀印進說明"
      "（圖例不再宣稱任何節奏，天數變成每一列自己的事——"
      "沒有這一格，讀者只能假設是一天）",
      [w for w in ("上一版是 ", "baseline_days", "不是同一把尺") if w not in _GH_PAGE], [])

# 上面幾條釘的是判準。真正會騙人的是**呼叫端有沒有照著寫**——所以這條走真的
# main()：第一班寫基線，第二班讀回來。top_n=1 是為了讓「有量到但沒上榜」真的發生。
with tempfile.TemporaryDirectory() as _rmtd:
    _rmv = Path(_rmtd)
    (_rmv / "_config").mkdir()
    (_rmv / "_github").mkdir()
    (_rmv / "_config" / "github.yaml").write_text("top_n: 1\nsearches: []\n",
                                                  encoding="utf-8")
    _rm_ts = _dt_m.datetime.now(_dt_m.timezone.utc).timestamp() - 86400
    # 舊 schema：只有 stars / ts，一個名次欄位都沒有。
    (_rmv / "_github" / "state.json").write_text(_json.dumps({
        "big/a": {"stars": 99000, "ts": _rm_ts}, "big/b": {"stars": 49500, "ts": _rm_ts},
        "sml/x": {"stars": 500, "ts": _rm_ts}, "sml/y": {"stars": 210, "ts": _rm_ts}}),
        encoding="utf-8")
    _rm_collect, _rm_argv, _rm_env = _ghm2.collect, sys.argv[:], os.environ.get("VAULT_DIR")
    try:
        _ghm2.collect = lambda *a, **k: _U_REPOS
        os.environ["VAULT_DIR"] = str(_rmv)
        sys.argv = ["pulse-github.py", "--snapshot"]
        _ghm2.main()
        _rm_board1 = _json.loads((_rmv / "dist" / "data" / "github.json").read_text("utf-8"))
        _rm_state = _json.loads((_rmv / "_github" / "state.json").read_text("utf-8"))
        sys.argv = ["pulse-github.py"]      # 第二班：基線已經有名次了
        _ghm2.main()
        _rm_board2 = _json.loads((_rmv / "dist" / "data" / "github.json").read_text("utf-8"))
    finally:
        _ghm2.collect = _rm_collect
        sys.argv = _rm_argv
        if _rm_env is not None:
            os.environ["VAULT_DIR"] = _rm_env
acase("GitHub 名次變動：快照那一班把名次跟星數**一起**寫回 state.json"
      "（分兩次寫的話，頁面上的 ▲3 跟 +180★/天 量的是不同區間，"
      "而讀者沒有任何方式看得出來）",
      [_rm_state["big/a"].get("rank_velocity", "MISSING"),
       _rm_state["big/a"]["ts"] == _rm_ts],
      [1, False])
acase("GitHub 名次變動：有量到但沒上榜的 repo 寫 null，不是不寫這個欄位"
      "（不寫的話下一班讀到的是「舊 schema、量不到」，"
      "而事實是我們量過、它就是不在榜上——那兩句在畫面上是不同的說法）",
      [_rm_state["big/b"].get("rank_velocity", "MISSING"),
       "rank_velocity" in _rm_state["big/b"],
       _rm_state["sml/x"].get("rank_surge"), _rm_state["sml/x"].get("rank_velocity")],
      [None, True, 1, None])
acase("GitHub 名次變動：第一班（舊基線）整榜是「量不到」，第二班才量得到"
      "（走真的 main()，不 grep 原始碼：grep 只證明那段碼還在）",
      [_rm_board1["repos"][0].get("rank_move_velocity"),
       _rm_board1["repos"][0].get("rank_places_velocity"),
       _rm_board2["repos"][0].get("rank_move_velocity"),
       _rm_board2["surging"][0].get("rank_move_surge")],
      ["no_baseline", None, "flat", "entered"])
acase("GitHub 名次變動：頁面把「跟哪一版比」與圖例印出來"
      "（沒寫出來的話，讀者會把 ▲3 讀成「跟昨天比」——而基線是上一次快照）",
      [w for w in ('id="legend"', "名次底下那一格", "隔了幾天每一列不一樣",
                   "新進榜", "沒有上一版名次可比")
       if w not in _GH_PAGE], [])
acase("GitHub 名次變動：圖示走站上共用的 .ic 線條圖標，不用 ▲▼ 這種字元"
      "（那幾個字在不同平台會被 emoji 字型接管，大小與基線都不受控，"
      "而它就住在名次數字底下——歪一格整欄看起來就沒對齊）",
      [c for c in ("▲", "▼", "▴", "▾", "⬆", "⬇") if c in _GH_PAGE], [])
# 顏色是第二個管道，形狀是第一個。這幾條釘的不是「好不好看」，是**同一個顏色
# 不准掛兩種確定度**：第一版的綠同時給了 up（方向＋幅度都量到）跟 entered
#（方向確定、幅度量不到），而那正是這一整格存在的理由。灰那邊三種全是 --quiet，
# 只差實線／虛線與一層 opacity，11px 下等於同一個東西。
acase("GitHub 名次變動：四階顏色編碼的是「量到多少」，up 與 entered 不准同色"
      "（一個是量到的完整位移，一個是「一定往上但幾名量不到」——"
      "同色等於把這一格存在的理由抹掉）",
      [".gh-move.up{color:var(--fact)}" in _R_CSS,
       ".gh-move.entered{color:var(--forecast)}" in _R_CSS,
       ".gh-move.down,.gh-move.flat{color:var(--muted)}" in _R_CSS,
       ".gh-move.first_seen,.gh-move.no_baseline{color:var(--quiet)}" in _R_CSS,
       ".gh-move.up,.gh-move.entered" in _R_CSS],
      [True, True, True, True, False])
# 舊版把「量不到」那階再乘 0.7 透明度：等效色約 #a6aab1，對白底只有 2.4:1，
# 低於 WCAG 1.4.11 對非文字 UI 元件的 3:1 門檻。分階要靠 token 不靠透明度——
# 透明度會把「這一階比較淡」偷偷變成「這一階讀不到」。
# 判準只掃 .gh-move 那幾條規則，不掃整份樣式表：第一版寫 `"opacity:.7" in _R_CSS`
# 打中的是泳道那顆點的 `opacity:.75`——這條分支上第三次「判準抓到隔壁那一處」。
_GH_MOVE_RULES = "".join(_re.findall(r"\.gh-move[^{}]*\{[^}]*\}", _R_CSS))
acase("GitHub 名次變動：分階不用 opacity（--quiet 再乘 0.7 只剩 2.4:1，"
      "低於非文字元件的 3:1；四個 token 直接用就都過）",
      ["opacity" in _GH_MOVE_RULES, len(_GH_MOVE_RULES) > 0], [False, True])

acase("GitHub 名次變動：樣式住在共用樣式表，不是那一頁自己的 <style>"
      "（這一頁上一次自己抄一份樣式的下場，就是收字級那一輪它整份被跳過）",
      [".gh-move{" in _R_CSS, ".gh-legend{" in _R_CSS, "<style>" in _GH_PAGE],
      [True, True, False])

acase("標頭：四個 kicker 語言一致（全英文小標）",
      [_k for _k in _re.findall(r'hero\(\s*"([^"]+)"', _HEAD_SRC)
       if _re.search(r"[一-鿿]", _k)], [])
acase("字級：區塊標題與事件標題共用同一個 token（它們在首頁上下緊鄰）",
      [".section-head h2{font-size:var(--fs-h2)" in _R_CSS,
       "article.event h2{font-size:var(--fs-h2)" in _R_CSS], [True, True])

# 文案：站上不得再出現比事實寬鬆的宣稱。敘述那一層是有潤稿的。
# 用 ast 把註解與 docstring 拿掉，剩下的字串常數才是「讀者可能看得到的」。
# 第一版用 `split('"""', 3)[-1]` 這種切法猜位置，結果把模組 docstring 也算進去——
# 那句「純規則模板，零 LLM」講的是 renderer 自己，而且是對的。
# **判斷「這句話讀者看不看得到」不能靠字串位置的巧合。**
import ast as _ast  # noqa: E402
_R_SRC = open(os.path.join(_HERE, "pulse-render.py"), encoding="utf-8").read()
_R_TREE = _ast.parse(_R_SRC)
_R_DOCS = set()
for _n in _ast.walk(_R_TREE):
    if isinstance(_n, (_ast.Module, _ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
        _doc = _ast.get_docstring(_n, clean=False)
        if _doc:
            _R_DOCS.add(_doc)
_R_COPY = "\n".join(_n.value for _n in _ast.walk(_R_TREE)
                    if isinstance(_n, _ast.Constant) and isinstance(_n.value, str)
                    and _n.value not in _R_DOCS)
acase("文案：讀者看得到的地方不得寫「零 LLM」「不靠 LLM」這種整站級的宣稱"
      "（判斷那一層沒有模型，敘述那一層有——寫成整站就是把一半說成全部）",
      [w for w in ("0 LLM", "零 LLM", "不靠 LLM") if w in _R_COPY], [])
acase("文案：內部術語不外洩到讀者面前（門禁 / vault）",
      [w for w in ("門禁", "vault →") if w in _R_COPY], [])


# ------------------------------------------------------- 來源能力（capability）
# 規格：references/source-capabilities.md。三條判準都在這裡，不在文件裡——
# 執行計劃的〈修正三〉：「所有 running sources 都有 capability」寫成驗收條件的話，
# 它在通過的那天成立、在下一次有人加來源的那天失效，而且不會有任何東西變紅。
_SC_RAW = _yaml.safe_load(
    open(os.path.join(_HERE, "..", "_config", "sources.yaml"), encoding="utf-8"))
_SC_RUN = [s for s in _smod.iter_sources(_SC_RAW) if _smod.is_running(s)]
acase("sources.yaml: 會被抓的來源都要標 capabilities（缺了就是一塊看不見的盲區）",
      sorted(str(s.get("id")) for s in _SC_RUN if not (s.get("capabilities") or [])), [])
acase("sources.yaml: capabilities 的值必須在 lib/sources.CAPABILITIES 裡"
      "（開放詞彙表會長出 benchmarks / benchmark_result 這種同義異形，"
      "而覆蓋率矩陣會安靜地把它們算成不同格）",
      sorted({c for s in _smod.iter_sources(_SC_RAW)
              for c in (s.get("capabilities") or [])} - _smod.CAPABILITIES), [])
acase("sources.yaml: capabilities 不准有重複值（同一格算兩次，覆蓋率就虛胖）",
      sorted(str(s.get("id")) for s in _smod.iter_sources(_SC_RAW)
             if len(s.get("capabilities") or []) != len(set(s.get("capabilities") or []))), [])
# 詞彙表與 RUN_LIFECYCLES 都只准有一份，理由同上面那條 aggregator_sources 的禁令。
acase("scripts/: capability 詞彙表只准有一份"
      "（除 lib/sources.py 外不得再硬寫 'official_announcement'）",
      sorted(os.path.basename(p) for p in _glob.glob(os.path.join(_HERE, "**", "*.py"),
                                                     recursive=True)
             if os.path.basename(p) not in ("sources.py", "selftest.py")
             and "official_announcement" in open(p, encoding="utf-8").read()), [])
acase("scripts/: 可跑 lifecycle 只准有一份"
      "（2026-08-11 之前這個集合硬寫在四個檔案裡，漏改一處＝某一類 lifecycle "
      "在那支腳本眼裡不存在，而清單長度不變、沒有東西會紅）",
      sorted(os.path.basename(p) for p in _glob.glob(os.path.join(_HERE, "**", "*.py"),
                                                     recursive=True)
             if os.path.basename(p) not in ("sources.py", "selftest.py")
             and '"degraded", "probing"' in open(p, encoding="utf-8").read()), [])
acase("lib/sources.CAPABILITIES: 15 個值，且 procurement 在裡面"
      "（0 條來源宣稱它，正是它必須留在表上的理由——把沒有人做的那一格從表上拿掉，"
      "盲區就從清單裡消失了）",
      (len(_smod.CAPABILITIES), "procurement" in _smod.CAPABILITIES),
      (15, True))
# 消費者。一個沒有人讀的欄位等於不存在，所以這一行在落地當天就要有人印。
_CAP_LINE = _mm.capability_claims_line(_SC_RAW, {"src-openai-blog": 3})
acase("pulse-monitor: 宣稱／觀察對照行，零產出的來源要被點名（不是只給一個總數）",
      ("src-mistral-news" in _CAP_LINE, "procurement" in _CAP_LINE), (True, True))
acase("pulse-monitor: 對照行不回 bool（永遠是 False 的旗標就是假旋鈕；"
      "不觸警的理由見 references/source-capabilities.md）",
      isinstance(_CAP_LINE, str), True)
acase("lib/sources.capability_claims: 只算 running 的"
      "（把停用來源算進覆蓋率，盲區會看起來比實際小，而這一層存在就是為了指出盲區）",
      "src-arxiv-cs-cl" in sum(_smod.capability_claims(_SC_RAW).values(), []), False)

print("offline self-test\n" + "-" * 70)
fails = 0
for ok, name, detail, reason in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n         {detail} | {reason}")
    fails += 0 if ok else 1
print("-" * 70)
print(f"{len(results) - fails}/{len(results)} passed")
raise SystemExit(1 if fails else 0)
