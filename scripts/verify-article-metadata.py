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
FIELD_PATTERNS = [
    ("og:title",
     r"""<meta[^>]+property=["']og:title["'][^>]*content=["']([^"']+)"""),
    ("og:title(rev)",
     r"""<meta[^>]+content=["']([^"']+)["'][^>]*property=["']og:title["']"""),
    ("<title>", r"<title[^>]*>([^<]{1,300})</title>"),
    ("article:published_time",
     r"""article:published_time["'][^>]*content=["']([^"']+)"""),
    ("time@datetime", r"""<time[^>]+datetime=["']([^"']+)"""),
    ("jsonld:datePublished", r'"datePublished"\s*:\s*"([^"]+)"'),
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


def extract(html: str) -> dict:
    out = {}
    for label, pat in FIELD_PATTERNS:
        m = re.search(pat, html or "", re.I)
        out[label] = m.group(1).strip() if m else None
    text = visible_text(html)
    out["_visible_text_chars"] = len(" ".join(text.split()))
    hits = VISIBLE_DATE_RE.findall(text)
    out["visible_date"] = (f"{hits[0][0]} {hits[0][1]}, {hits[0][2]}") if hits else None
    out["visible_date_count"] = len(hits)
    return out


# ------------------------------------------------------------------ 單條驗證
def probe_one(pp, url: str) -> dict:
    r = {"url": url, "verdict": None, "robots": None, "robots_reason": None,
         "status": None, "bytes": None, "fields": None, "note": None}

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

    try:
        status, body, headers = pp.safe_fetch(url)
    except Exception as exc:  # noqa: BLE001
        r["note"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        r["verdict"] = "no_verdict" if _is_proxy_error(exc) else "fetch_error"
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

    r["fields"] = extract(body or "")
    r["verdict"] = "ok" if r["fields"].get("og:title") or r["fields"].get("og:title(rev)") \
        else "no_og_title"
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
}

VERDICT_EXIT = {"no_verdict": 4, "site_error": 2, "fetch_error": 2,
                "no_og_title": 3, "ok": 0}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Answer C-4 with the production fetcher: og:title, dates, robots.")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--json")
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
        r = probe_one(pp, url)
        results.append(r)
        print(f"    robots  : {r['robots']}  ({r['robots_reason']})")
        print(f"    fetch   : status={r['status']} bytes={r['bytes']}")
        if r["note"]:
            print(f"    note    : {r['note']}")
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
            json.dump({"ua": pp.UA, "results": results}, fh, ensure_ascii=False, indent=2)
        print(f"\nreport written to {args.json}")

    # 最壞的那一條決定退出碼。no_verdict 排最前面：沒有判決比壞判決更該讓 CI 紅，
    # 因為壞判決至少是關於站方的，沒有判決是關於我們自己的。
    return max((VERDICT_EXIT.get(r["verdict"], 2) for r in results), default=0)


if __name__ == "__main__":
    sys.exit(main())
