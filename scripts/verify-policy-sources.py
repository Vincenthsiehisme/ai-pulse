#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-policy-sources.py

One-off verifier for candidate feed endpoints, before they are promoted
from `probing` in _config/sources.yaml.

Design notes
------------
* stdlib only. No feedparser, no requests, no LLM. Runs on a clean
  Python 3.9+ install on Windows.
* The robots check MUST use the same User-Agent string that the real
  probe declares when fetching content. The arXiv incident (2026-07-24)
  happened because robots.txt was requested with urllib's default UA
  while content was fetched with the system UA -- so the check was
  answering a question about a different client.
  Set PULSE_UA to the probe's real UA before running, or pass --ua.
* Unknown robots status is NEVER treated as permission. It returns None
  and the caller refuses to fetch. `robots_ok: null` in sources.yaml
  means "not yet established", not "fine".
* All console output is ASCII so it survives a cp950 Windows console.

Usage
-----
    set PULSE_UA=<your probe UA>
    python verify-policy-sources.py
    python verify-policy-sources.py --url https://example.org/feed.xml
    python verify-policy-sources.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

DEFAULT_UA = os.environ.get("PULSE_UA", "ai-pulse-tracker/0.1 (+probe; contact: set PULSE_UA)")
TIMEOUT = 30

# Candidates decided on 2026-07-24. Keep ids identical to sources.yaml.
CANDIDATES = [
    {
        "id": "src-consilium-press",
        "media_group": "EU-Council",
        "url": "https://www.consilium.europa.eu/en/rss/pressreleases.ashx",
    },
    {
        "id": "src-ep-itre",
        "media_group": "EU-Parliament",
        "url": "https://www.europarl.europa.eu/rss/committee/itre/en.xml",
    },
]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


# --------------------------------------------------------------------------
# robots
# --------------------------------------------------------------------------

def check_robots(url: str, ua: str) -> tuple[object, str]:
    """Return (allowed, reason).

    allowed is True / False / None. None means undetermined -- the caller
    must not fetch. Branching mirrors pulse-probe.py's robots_allows().
    """
    parts = urllib.parse.urlsplit(url)
    robots_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))

    req = urllib.request.Request(robots_url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = ""
        deny = exc.headers.get("x-deny-reason") if exc.headers else None
        if deny:
            return None, (f"intercepted by local egress proxy (x-deny-reason: {deny}) "
                          "-- undetermined; this is NOT a refusal by the site")
        if status in (401, 403):
            return False, f"robots.txt returned {status} -- treated as refusal"
        if 400 <= status < 500:
            return True, f"robots.txt returned {status} (no robots file) -- allowed"
        return None, f"robots.txt returned {status} -- undetermined"
    except Exception as exc:  # noqa: BLE001 - network layer is genuinely open-ended
        return None, f"robots.txt fetch failed ({type(exc).__name__}: {exc}) -- undetermined"

    if status != 200:
        return None, f"robots.txt returned {status} -- undetermined"

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    allowed = parser.can_fetch(ua, url)
    crawl_delay = parser.crawl_delay(ua)
    reason = "robots.txt 200, path %s" % ("allowed" if allowed else "DISALLOWED")
    if crawl_delay:
        reason += f", crawl-delay {crawl_delay}s"
    return bool(allowed), reason


# --------------------------------------------------------------------------
# feed
# --------------------------------------------------------------------------

def _text(node, path, ns=None):
    if node is None:
        return None
    found = node.find(path, ns) if ns else node.find(path)
    if found is None:
        return None
    if found.text and found.text.strip():
        return found.text.strip()
    href = found.get("href")
    return href.strip() if href else None


def inspect_feed(url: str, ua: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    out: dict = {"url": url}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            out["status"] = resp.status
            out["content_type"] = resp.headers.get("Content-Type", "")
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        out["status"] = exc.code
        out["error"] = f"HTTPError {exc.code}"
        return out
    except Exception as exc:  # noqa: BLE001
        out["status"] = None
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    out["bytes"] = len(raw)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        out["error"] = f"XML parse error: {exc}"
        return out

    tag = root.tag.split("}")[-1]
    if tag == "rss":
        out["dialect"] = "rss"
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else []
        out["feed_title"] = _text(channel, "title")
        fields = {"title": "title", "link": "link", "date": "pubDate", "guid": "guid"}
        author_paths = ["author", "dc:creator"]
    elif tag == "feed":
        out["dialect"] = "atom"
        items = root.findall("atom:entry", NS)
        out["feed_title"] = _text(root, "atom:title", NS)
        fields = {"title": "atom:title", "link": "atom:link", "date": "atom:updated", "guid": "atom:id"}
        author_paths = ["atom:author/atom:name"]
    else:
        out["error"] = f"unrecognised root element <{tag}>"
        return out

    out["items"] = len(items)
    counts = {k: 0 for k in fields}
    counts["author"] = 0
    samples = []
    for it in items:
        for key, path in fields.items():
            val = _text(it, path, NS if out["dialect"] == "atom" else None)
            if val:
                counts[key] += 1
        for path in author_paths:
            if _text(it, path, NS):
                counts["author"] += 1
                break
        if len(samples) < 3:
            samples.append({
                "title": (_text(it, fields["title"], NS if out["dialect"] == "atom" else None) or "")[:90],
                "date": _text(it, fields["date"], NS if out["dialect"] == "atom" else None),
            })
    out["field_coverage"] = counts
    out["samples"] = samples
    out["link_fallback_needed"] = counts["link"] < len(items) and counts["guid"] > counts["link"]
    return out


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def verify(cand: dict, ua: str) -> dict:
    print(f"\n=== {cand.get('id', cand['url'])} ===")
    print(f"    url: {cand['url']}")
    allowed, reason = check_robots(cand["url"], ua)
    label = {True: "ALLOW", False: "DENY", None: "UNKNOWN"}[allowed]
    print(f"    robots: {label}  ({reason})")

    result = dict(cand)
    result["robots_ok"] = allowed
    result["robots_reason"] = reason

    if allowed is not True:
        print("    feed: not fetched (robots not established as permitting)")
        result["feed"] = None
        return result

    feed = inspect_feed(cand["url"], ua)
    result["feed"] = feed
    if "error" in feed:
        print(f"    feed: FAILED -- {feed['error']}")
        return result

    cov = feed["field_coverage"]
    n = feed["items"]
    print(f"    feed: HTTP {feed['status']} {feed.get('content_type','')} | {feed['dialect']} | {n} items")
    print(f"          title {cov['title']}/{n}  link {cov['link']}/{n}  date {cov['date']}/{n}  author {cov['author']}/{n}")
    if feed["link_fallback_needed"]:
        print("          NOTE: some items lack <link>; adapter needs guid fallback (same as src-hf-blog)")
    for s in feed["samples"]:
        print(f"          - [{s['date']}] {s['title']}")
    return result


def control_probe(ua: str, control_url: str) -> tuple[bool, str]:
    """Confirm the machine can reach the open internet at all.

    Without this, a corporate proxy or egress allowlist returning 403 for
    every host looks identical to 'every site refuses us', and sources get
    marked dormant for a reason that has nothing to do with the sources.
    """
    allowed, reason = check_robots(control_url, ua)
    return (allowed is not None), reason


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify candidate feed endpoints before promoting from probing.")
    ap.add_argument("--url", action="append", default=[], help="ad hoc URL to verify (repeatable)")
    ap.add_argument("--ua", default=DEFAULT_UA, help="User-Agent; MUST match the probe's real UA")
    ap.add_argument("--json", help="write full report to this path (UTF-8)")
    ap.add_argument("--control-url", default="https://github.com/robots.txt",
                    help="known-reachable URL used to prove the network is not the problem")
    ap.add_argument("--skip-control", action="store_true")
    args = ap.parse_args()

    cands = [{"id": f"adhoc-{i+1}", "url": u} for i, u in enumerate(args.url)] or CANDIDATES

    print("verify-policy-sources.py")
    print(f"  run at : {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"  UA     : {args.ua}")
    if "set PULSE_UA" in args.ua:
        print("  WARNING: PULSE_UA is not set. This check is only meaningful when the UA")
        print("           matches the one pulse-probe.py sends when fetching content.")

    if not args.skip_control:
        reachable, creason = control_probe(args.ua, args.control_url)
        print(f"  control: {'OK' if reachable else 'BLOCKED'} via {args.control_url}")
        if not reachable:
            print(f"           {creason}")
            print("\nABORT: this machine cannot reach the open internet, so no verdict")
            print("       about the candidate sources can be issued. Do NOT record")
            print("       robots_ok or change lifecycle based on this run.")
            return 4

    results = [verify(c, args.ua) for c in cands]

    today = datetime.now(timezone.utc).date()
    print("\n--- paste into _config/sources.yaml ---")
    for r in results:
        print(f"  # {r['id']}")
        if r["robots_ok"] is None:
            print(f"  # NO VERDICT ({r['robots_reason']}).")
            print("  # Leave the entry as-is and re-run once the cause is resolved.")
            continue
        n = (r.get("feed") or {}).get("items")
        if r["robots_ok"] is True:
            print(f"  robots_ok: true          # verified {today} with probe UA")
            print(f"  lifecycle: {'probing' if n else 'dormant'}"
                  f"{'' if n else '   # robots ok but feed yielded no items'}")
        else:
            print(f"  robots_ok: false         # verified {today} with probe UA")
            print("  lifecycle: dormant")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"ua": args.ua, "results": results}, fh, ensure_ascii=False, indent=2)
        print(f"\nreport written to {args.json}")

    undetermined = [r["id"] for r in results if r["robots_ok"] is None]
    denied = [r["id"] for r in results if r["robots_ok"] is False]
    if denied:
        return 2
    if undetermined:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
