#!/usr/bin/env python3
"""diag-robots.py — 找出 robots 檢查為何與手動請求結果不同。

用法（在 vault 根目錄）：
    python scripts\\diag-robots.py

只做讀取與列印，不寫任何檔案。
"""
import importlib.util
import sys
from pathlib import Path

import requests

TARGET = "http://export.arxiv.org/rss/cs.CL"
PROBE = Path(__file__).with_name("pulse-probe.py")


def load_probe():
    spec = importlib.util.spec_from_file_location("pp", PROBE)
    m = importlib.util.module_from_spec(spec)
    sys.modules["pp"] = m
    spec.loader.exec_module(m)          # main() 在 __main__ 保護下，不會執行
    return m


def hops(url: str, ua: str) -> None:
    """逐跳列出，模擬 safe_fetch 的 allow_redirects=False 行為。"""
    current = url
    for i in range(6):
        try:
            r = requests.get(current, headers={"User-Agent": ua}, timeout=15,
                             stream=True, allow_redirects=False)
        except Exception as e:
            print(f"  hop{i} {current} → 例外 {type(e).__name__}: {e}")
            return
        loc = r.headers.get("Location", "")
        print(f"  hop{i} [{r.status_code}] {current}"
              + (f"  → {loc}" if loc else ""))
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            current = requests.compat.urljoin(current, loc)
            continue
        body = r.raw.read(2048, decode_content=True).decode("utf-8", "replace")
        print(f"        body({len(body)}B): {body[:120]!r}")
        return
    print("  超過 6 跳")


def main() -> int:
    m = load_probe()
    ua = m.UA
    print(f"UA = {ua!r}\n")

    for scheme in ("http", "https"):
        print(f"[{scheme}] {scheme}://export.arxiv.org/robots.txt  逐跳：")
        hops(f"{scheme}://export.arxiv.org/robots.txt", ua)
        print()

    print("safe_fetch 的結果：")
    for scheme in ("http", "https"):
        url = f"{scheme}://export.arxiv.org/robots.txt"
        try:
            status, body, _ = m.safe_fetch(url)
            print(f"  {scheme}: status={status} body={ (body or '')[:60]!r}")
        except Exception as e:
            print(f"  {scheme}: 例外 {type(e).__name__}: {e}")

    print("\nrobots_allows 的結果：")
    for url in (TARGET, TARGET.replace("http://", "https://")):
        try:
            print(f"  {url} → {m.robots_allows(url)}")
        except Exception as e:
            print(f"  {url} → 例外 {type(e).__name__}: {e}")

    print("\n對照：requests 自動跟隨（你手動跑的那種）")
    r = requests.get("http://export.arxiv.org/robots.txt",
                     headers={"User-Agent": ua}, timeout=15)
    print(f"  [{r.status_code}] final={r.url} len={len(r.text)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
