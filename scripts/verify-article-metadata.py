#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-article-metadata.py — 回答 published-is-a-proxy 的 C-4，用生產的抓取器。

C-4 問的是三件事，而且只有在**與生產相同的 HTTP 路徑上**問才算數：

  1. plain GET 拿回來的 HTML 裡有沒有 `og:title`（決定「標題能不能修好」）
  2. 有沒有機器可讀的發布時間，以及有沒有人看的日期（決定「日期能修到什麼程度」）
  3. **文章路徑**的 robots 允不允許（現在 sources.yaml 的 `robots_ok: true`
     是對 sitemap 那條路徑說的，不是對 /news/<slug> 說的）

所以這支直接 import `pulse-probe.py` 的 `safe_fetch` 與 `robots_verdict`，
不自己寫一套 HTTP。自己寫一套就是在問另一個 client 的問題——
`verify-policy-sources.py` 的 docstring 已經為了 arXiv 那次事故寫過這句話。

---------------------------------------------------------------------------
這支存在的真正理由（2026-07-27，作者把自己犯的錯寫在這裡）
---------------------------------------------------------------------------
C-4 原本被回報成「已驗證，而且是否定的」：`safe_fetch` 對
`https://www.anthropic.com/news/claude-opus-5` 回 403，於是結論寫成
「Anthropic 的 WAF 擋掉生產抓取器，C-3 不成立」。

那個結論是錯的。403 的 body 是 104 bytes 的
`Host not in allowlist: www.anthropic.com.`，`x-deny-reason: host_not_allowed`
——擋人的是**執行環境的 egress allowlist**，不是站方。同一個容器對
`openai.com`、`deepmind.google` 也回一樣的東西，而那兩條來源在 CI 裡每天正常出貨。

犯錯的方式很具體：手寫了一支只呼叫 `safe_fetch` 的臨時腳本，跳過了
`verify-policy-sources.py`——而那支的 `control_probe()` docstring 一字不差地
寫著這個陷阱：「沒有它，公司代理或 egress allowlist 對每個 host 回 403，
看起來會跟『每個站都拒絕我們』一模一樣」。工具已經在了，我沒用它。

這支因此把那道防線做成**結構性的**而不是靠人記得：
  - 沒有 control probe 通過，一律不出判決（exit 4）。
  - 認得 egress 攔截的簽名，判 `no_verdict` 而不是 `site_refused`。
  - 只要有任何一條走到 `no_verdict`，退出碼就不是 0，CI 不會綠。

紅線 7 的那句話在這裡是可執行的，不是格言：**「我們讀不到」不等於「站方拒絕」。**

用法
----
    # 在 CI 跑（safe_fetch 真正跑的地方）
    python3 scripts/verify-article-metadata.py --preset sitemap-sources

    # 手動指定
    python3 scripts/verify-article-metadata.py --url https://www.anthropic.com/news/claude-opus-5

    # 落 JSON 供後續設計引用
    python3 scripts/verify-article-metadata.py --preset sitemap-sources --json /tmp/c4.json

退出碼
------
    0  全部拿到判決，且每一條都成功讀到 HTML
    2  有站方明文 Disallow 或 4xx/5xx（這是**站方的**答案，可以寫進設計）
    3  有讀到 HTML 但缺 og:title（C-3 的前提在該站不成立）
    4  沒有判決：control probe 失敗，或有 host 被 egress 攔截

輸出一律 ASCII，理由同 verify-policy-sources.py（cp950 主控台）。
"""
from __future__ import annotations

import argparse
import importlib.util
import hashlib
import html as _html
import json
import os
import re
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def _load_probe():
    """import pulse-probe.py。檔名有連字號，只能走 importlib。"""
    path = os.path.join(_HERE, "pulse-probe.py")
    spec = importlib.util.spec_from_file_location("pulse_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------- egress 偵測
# 本地 egress proxy 攔截的簽名。它回 403 + 一小段 text/plain，跟站方的 403
# 在狀態碼上完全無法區分——區分它們是這支腳本存在的理由。
EGRESS_HEADER = "x-deny-reason"
EGRESS_BODY_MARKERS = (
    "not in allowlist",
    "network egress settings",
)


def is_egress_intercept(status, body, headers) -> str | None:
    """回攔截原因字串，或 None。只認簽名，不猜。"""
    hdr = {str(k).lower(): v for k, v in (headers or {}).items()}
    if EGRESS_HEADER in hdr:
        return f"{EGRESS_HEADER}: {hdr[EGRESS_HEADER]}"
    if status == 403 and body:
        low = body.lower()
        for m in EGRESS_BODY_MARKERS:
            if m in low:
                return body.strip()[:160]
    return None


def _is_proxy_error(exc: Exception) -> bool:
    """連 proxy 都沒建起來的情況。ProxyError 走這條，也是攔截不是拒絕。"""
    return "ProxyError" in type(exc).__name__ or "Tunnel connection failed" in str(exc)


# ------------------------------------------------------------------ 欄位抽取
# 全部是字面 regex。抽不到就是 ABSENT，不退而求其次、不從別處推導——
# 這支的整個重點就是把「有」跟「我們造得出來」分開。
# 引號用**反向參照**，不是 `[^"\']`。
# 第一版寫成 `content=["\']([^"\']+)`，於是
#   <meta property="og:title" content="Anthropic's Claude Opus 5">
# 抽出來的是 `Anthropic` ——而 C-3 的整個前提是「og:title 有，而且是真值」。
# 一個在雙引號屬性裡完全合法的撇號，把真值截成一個更短、看起來仍然像標題的字串，
# 然後那個字串會被寫進 c4-report.json，也就是設計文件說「可以引用的證據」。
# 這是本 PR 從頭到尾在講的那隻病，長在為了驗證它而寫的驗證器裡。
FIELD_PATTERNS = [
    # `[^>]*?` 而不是 `.*?`：非貪婪仍然會跨過 `>` 去找下一個引號。
    # 實測——`<meta property="article:published_time" content="…">` 後面接
    # `<meta content="X" property="og:title">` 時，rev 那條會從第一個 meta 的
    # content 一路吃到第二個 meta 的 property，抽出一大串含標籤的垃圾當標題。
    # 屬性值裡的 `>` 在合法 HTML 裡是 `&gt;`，所以把比對關在單一標籤內是安全的。
    ("og:title",
     r"""<meta[^>]+property=(["'])og:title\1[^>]*content=(["'])(?P<v>[^>]*?)\2"""),
    ("og:title(rev)",
     r"""<meta[^>]+content=(["'])(?P<v>[^>]*?)\1[^>]*property=(["'])og:title\3"""),
    ("<title>", r"<title[^>]*>(?P<v>[^<]{1,300})</title>"),
    ("article:published_time",
     r"""article:published_time(["'])[^>]*content=(["'])(?P<v>[^>]*?)\2"""),
    ("time@datetime", r"""<time[^>]+datetime=(["'])(?P<v>[^>]*?)\1"""),
    ("jsonld:datePublished", r'"datePublished"\s*:\s*"(?P<v>[^"]*)"'),
]

# 人看的日期。C-2 實測：Anthropic 印 "Jul 24, 2026"、Mistral 印 "July 8, 2026"，
# 都在標題下方的自由文字裡、**沒有標籤詞**、沒有時區。
# 抓得到不等於能用——精度只到日，這正是 C-3 逼出 published_precision 的理由。
VISIBLE_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"([0-9]{1,2}),?\s+(20[0-9]{2})\b")

_TAG_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_ANYTAG_RE = re.compile(r"<[^>]+>")


def visible_text(html: str) -> str:
    """去掉 script/style 與所有標籤後剩下的文字。用來判 JS 空殼。"""
    return _ANYTAG_RE.sub(" ", _TAG_RE.sub(" ", html or ""))


def _content_group(m) -> str:
    """→ 具名群組 `v` 的內容。

    引號改用反向參照之後，編號群組裡混進了引號字元本身。第一版寫「取最後一個
    非 None 的群組」——對 og:title 正確，對 `og:title(rev)`（content 在前、
    property 在後）回的是那個 `"`。**一個永遠非空、於是永遠判 ok 的值**，
    正是這支腳本存在的理由的反面。
    改成具名群組：哪一組是內容變成寫在 pattern 裡的事實，不是位置的巧合。
    """
    return m.group("v") or ""


def extract(html: str) -> dict:
    out = {}
    for label, pat in FIELD_PATTERNS:
        m = re.search(pat, html or "", re.I)
        # 解 entity：`Claude&#x27;s new tool` 存成原樣，就是把來源的編碼
        # 當成標題的一部分。lib/modelline.py 在同一個 PR 裡為了同一件事修過
        # （M113），這支在兩百行外犯一樣的。
        out[label] = _html.unescape(_content_group(m)).strip() if m else None
    text = visible_text(html)
    out["_visible_text_chars"] = len(" ".join(text.split()))
    hits = VISIBLE_DATE_RE.findall(text)
    out["visible_date"] = (f"{hits[0][0]} {hits[0][1]}, {hits[0][2]}") if hits else None
    out["visible_date_count"] = len(hits)
    return out


# ------------------------------------------------------------------ 單條驗證
def save_html(directory: str, url: str, body: str) -> str:
    """把整頁原始 bytes 落到磁碟，供 CI 當 artifact 帶回來。

    這不是除錯輸出，是**下一步的輸入**：release-notes 那一組的解析器
    刻意還沒寫，因為對著想像的標記寫解析器會通過自己編的測試、
    然後在真頁面上失敗（references/model-timeline.md 第 5 節）。
    """
    os.makedirs(directory, exist_ok=True)
    # 截斷 + 把所有非英數壓成連字號，會讓 `x.ai/news` 與 `x.ai/news/` 塌成
    # 同一個檔名，後寫的蓋掉先寫的——而 r["html_path"] 仍然指著它，
    # 於是一份報告會說「這是 A 的 bytes」而檔案裡是 B 的。
    # 加完整 URL 的 sha1 前 10 碼：檔名仍然看得懂，碰撞不再靜音。
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:100]
    path = os.path.join(directory, f"{slug}-{digest}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body or "")
    return path


# 兩種通過條件，因為兩組 preset 問的是兩個不同的問題。
# 用同一個判準去問兩個問題，正是這個 repo 一直在拆的那件事：
#   article  文章頁——要的是 og:title（C-3 的前提）
#   page     整頁——要的是「不是 JS 空殼、而且看得到日期」（時間線步 3 的輸入）
MODE_ARTICLE, MODE_PAGE = "article", "page"
PRESET_MODE = {"sitemap-sources": MODE_ARTICLE, "list-pages": MODE_ARTICLE,
               "release-notes": MODE_PAGE}
# 空殼門檻。真的 changelog 頁有數萬字；React 空殼是幾百字的 nav。
# 這個數字是門檻不是真理，所以它印在輸出裡，讓人看得到自己在跟什麼比。
SHELL_TEXT_CHARS = 2000


def verdict_for(mode: str, fields: dict) -> str:
    if mode == MODE_ARTICLE:
        return "ok" if (fields.get("og:title") or fields.get("og:title(rev)")) \
            else "no_og_title"
    if fields.get("_visible_text_chars", 0) < SHELL_TEXT_CHARS:
        return "js_shell"
    return "ok" if fields.get("visible_date_count") else "no_dates"


def probe_one(pp, url: str, html_dir: str | None = None,
              mode: str = MODE_ARTICLE) -> dict:
    r = {"url": url, "verdict": None, "robots": None, "robots_reason": None,
         "status": None, "bytes": None, "fields": None, "note": None,
         "html_path": None}

    allowed, reason = None, "not checked"
    try:
        allowed, reason = pp.robots_verdict(url)
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"
        if _is_proxy_error(exc):
            r.update(verdict="no_verdict", robots_reason=reason,
                     note="egress proxy blocked robots.txt")
            return r
    r["robots"], r["robots_reason"] = allowed, reason

    # robots **不是印出來給人看的，是要擋住這一支自己的**。
    # 第一版算了、存了、印了，然後無條件往下抓——紅線 7 的整條規矩在這裡是
    # 一個沒有消費者的欄位，而這支腳本的 docstring 第 3 個問題就是它。
    # 姊妹支 verify-policy-sources.py:216 一直是對的：
    #   `if allowed is not True: 「feed: not fetched」`
    # 三種非 True 分成兩種判決，因為它們要人做的事不一樣：
    #   False  站方明文 Disallow ＝ **站方的答案**，可以寫進設計（exit 2）
    #   None   我們讀不到 robots ＝ **我們的問題**，什麼都不要寫（exit 4）
    # 只有 `disallow`（200 + 認得出是 robots.txt + 明文擋這條路徑）才是站方的答案。
    # `unavailable_403` 也回 False，但它的意思是**我們讀不到那份 robots.txt**——
    # pulse-probe.py 的 run_source 早就為了這一格特別開了分支，寫著
    # 「robots.txt 回 401/403，取不到內容，保守跳過（非站方拒絕）」。
    # 只看布林值就會把它讀成拒絕，而那正是這一整個 PR 在修的那句話。
    if allowed is False and reason == "disallow":
        r["verdict"] = "robots_disallow"
        r["note"] = "站方 robots.txt 明文 Disallow 這條路徑，不抓"
        return r
    if allowed is not True:
        r["verdict"] = "no_verdict"
        r["note"] = f"robots 未確立（{reason}），未知一律不當成許可（紅線 7）"
        return r

    try:
        status, body, headers = pp.safe_fetch(url)
    except Exception as exc:  # noqa: BLE001
        # 第一版把非 proxy 的例外歸成 fetch_error → exit 2，而設計文件把 2
        # 解釋成「站方 4xx/5xx…這是站方的答案，可以寫進設計」。
        # 但 SSLError / DNS 黑洞 / ReadTimeout **都不是站方的答案**，
        # 它們是「我們讀不到」。歸成 2 就是把我們自己的問題寫成站方的回覆——
        # 紅線 7 那句話的第三種犯法。全部歸 no_verdict。
        r["note"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        r["verdict"] = "no_verdict"
        return r

    intercepted = is_egress_intercept(status, body, headers)
    if intercepted:
        r.update(status=status, bytes=len(body or ""), verdict="no_verdict",
                 note=f"egress intercept -- {intercepted}")
        return r

    r["status"] = status
    r["bytes"] = len(body or "")
    if status != 200:
        r["verdict"] = "site_error"
        return r

    if html_dir:
        r["html_path"] = save_html(html_dir, url, body or "")
    r["fields"] = extract(body or "")
    r["verdict"] = verdict_for(mode, r["fields"])
    return r


# ------------------------------------------------------------- control probe
CONTROL_URL = "https://api.github.com/rate_limit"


def control_probe(pp, url: str) -> tuple[bool, str]:
    """證明這台機器連得出去。沒有這一關，整份報告都不該被引用。

    刻意不看狀態碼是不是 200——GitHub 對未認證請求回 403 也算「連到了」。
    要區分的是「有沒有走到對方的伺服器」，不是「對方喜不喜歡我們」。
    """
    try:
        status, body, headers = pp.safe_fetch(url)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:160]}"
    intercepted = is_egress_intercept(status, body, headers)
    if intercepted:
        return False, f"egress intercept -- {intercepted}"
    return True, f"HTTP {status}"


# ------------------------------------------------------------------ presets
# 這三條就是 published-is-a-proxy 第 1 節表格裡 adapter=sitemap 的全部來源。
PRESETS = {
    "sitemap-sources": [
        "https://www.anthropic.com/news/claude-opus-5",
        "https://x.ai/news/grok-4-5",
        "https://mistral.ai/news/leanstral-1-5",
    ],
    # C-5：Mistral 的列表頁本身就同時列出真標題與日期。若 plain GET 看得到，
    # 一次抓列表頁就同時解決兩件事。跟 C-4 一起驗，但不因為它省就先選它。
    "list-pages": [
        "https://www.anthropic.com/news",
        "https://x.ai/news",
        "https://mistral.ai/news",
    ],
    # 模型演變時間線的甲類來源（references/model-timeline.md 第 1 節）。
    # 這一組要的不是 og:title——是**整頁的原始 bytes**，因為 HTML → 條目的
    # 切分刻意還沒寫（規格第 5 節，步 3）。所以跑這一組時務必加 --save-html。
    "release-notes": [
        "https://platform.claude.com/docs/en/release-notes/api",
        "https://developers.openai.com/api/docs/changelog",
        "https://ai.google.dev/gemini-api/docs/changelog",
        "https://docs.x.ai/developers/release-notes",
    ],
}

# 3 與 2 是**兩種不同的壞消息**，不是嚴重度的兩格：
#   2  站方回答了，而答案是「不行」（Disallow / 4xx / 5xx）
#   3  站方回答了、我們也讀到了，但內容不合這一組 preset 要的東西
#   4  沒有答案。這是關於我們自己的，所以排最前面。
VERDICT_EXIT = {"no_verdict": 4,
                "site_error": 2, "robots_disallow": 2,
                "no_og_title": 3, "js_shell": 3, "no_dates": 3,
                "ok": 0}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Answer C-4 with the production fetcher: og:title, dates, robots.")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--json")
    ap.add_argument("--save-html", metavar="DIR",
                    help="把整頁原始 bytes 落到這個目錄（release-notes 那組必加："
                         "解析器要等真 bytes 才寫）")
    ap.add_argument("--control-url", default=CONTROL_URL)
    ap.add_argument("--skip-control", action="store_true",
                    help="ONLY for testing this script itself. Never in CI.")
    args = ap.parse_args()

    urls = list(args.url) + list(PRESETS.get(args.preset or "", []))
    if not urls:
        ap.error("give --url or --preset")

    pp = _load_probe()
    print("verify-article-metadata.py")
    print("  run at : " + datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print("  UA     : " + pp.UA)

    if not args.skip_control:
        ok, why = control_probe(pp, args.control_url)
        print(f"  control: {'OK' if ok else 'BLOCKED'} via {args.control_url}  ({why})")
        if not ok:
            print("")
            print("ABORT: this machine cannot reach the open internet, so no verdict")
            print("       about these pages can be issued. Do NOT record any conclusion")
            print("       about og:title, dates, or robots from this run.")
            return 4

    results = []
    for url in urls:
        print("")
        print("=== " + url)
        r = probe_one(pp, url, args.save_html, PRESET_MODE.get(args.preset, MODE_ARTICLE))
        results.append(r)
        print(f"    robots  : {r['robots']}  ({r['robots_reason']})")
        print(f"    fetch   : status={r['status']} bytes={r['bytes']}")
        if r["note"]:
            print(f"    note    : {r['note']}")
        if r["html_path"]:
            print(f"    saved   : {r['html_path']}")
        f = r["fields"] or {}
        if f:
            print(f"    visible : {f['_visible_text_chars']} chars of text "
                  f"(a JS shell would be near zero)")
            for label, _ in FIELD_PATTERNS:
                v = f.get(label)
                print(f"      {label:24s} = {(v[:90] if v else 'ABSENT')}")
            vd = f.get("visible_date")
            print(f"      {'visible date (human)':24s} = "
                  f"{vd or 'ABSENT'}  (x{f['visible_date_count']})")
        print(f"    VERDICT : {r['verdict']}")

    print("")
    print("--- summary ---")
    for r in results:
        print(f"  {r['verdict']:12s}  {r['url']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            # `control_probe` 這個欄位不是紀錄用的裝飾。少了它，
            # 一份 --skip-control 跑出來的報告與一份驗過的報告在位元組上
            # 完全一樣——而設計文件說「那份 JSON 才是可以引用的證據」。
            json.dump({"ua": pp.UA,
                       "control_probe": None if args.skip_control else args.control_url,
                       "preset": args.preset,
                       "results": results}, fh, ensure_ascii=False, indent=2)
        print(f"\nreport written to {args.json}")

    # 最壞的那一條決定退出碼。no_verdict 排最前面：沒有判決比壞判決更該讓 CI 紅，
    # 因為壞判決至少是關於站方的，沒有判決是關於我們自己的。
    return max((VERDICT_EXIT.get(r["verdict"], 2) for r in results), default=0)


if __name__ == "__main__":
    sys.exit(main())
