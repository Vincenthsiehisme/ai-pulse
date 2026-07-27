#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性遷移：把證據標題從 note 內文補回 frontmatter 的 `evidence[].title`。

為什麼要有這支：`evidence[].title` / `.published` 是 2026-07 才加的欄位，加之前
建立的 Event 沒有。而發展歷程的標題與日期原本只查 `_corpus/`——語料的保留期由
`corpus-累積` 那個**還沒拍板的決定**控制，改成滾動視窗的那天，所有舊事件的證據
標題會靜靜變成「未留存」。

好消息是標題沒有真的遺失，只是在 body 不在 frontmatter：note 的〈證據〉區每一條
都帶著它（`- [[Sources/x|x]] — 標題（url）`）。**不需要網路、不需要語料。**

`published` 走另一條路：body 沒有存日期，只能從**現存語料**補。所以這支同時做兩件
事，而兩件事的時效不同——標題永遠補得回來（body 一直在），日期只補得到語料還在的
那些。補不到就留空，由 render 印「日期未留存」：量不到就說量不到（紅線 8），
不拿事件日頂替。

規格：references/event-timestamps.md〈第三個現場：呈現層〉的〈遷移〉。

一次性，不留成排程：它問的是「舊資料缺一格」，不是每班都要回答的問題。
跑完之後新建的 Event 由 pulse-cluster 自己帶上這兩格。

用法：
  VAULT_DIR=/path/to/AI-Pulse python3 scripts/migrate-2026-07-27-evidence-titles.py [--apply]
預設是 dry-run。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.notes import dump_frontmatter, parse_note  # noqa: E402

#: body 的〈證據〉那一行，由 pulse-cluster.evidence_line() 產生：
#:   `- [[Sources/<sid>|<sid>]] — <標題>（<url>）`
#: 標題缺席時它印的是 `（標題未留存）<url>`——**那不是標題**，不能補進去，
#: 否則畫面上會出現一筆標題就叫「（標題未留存）」的證據，而那比空著更糟：
#: 空著時 render 知道要印「標題未留存」，補了假值之後它會以為自己有標題。
_EV_LINE = re.compile(r"^-\s*\[\[Sources/([^|\]]+)\|[^\]]*\]\]\s*—\s*(.*)$")
_NO_TITLE = "（標題未留存）"


def titles_from_body(body):
    """→ `{url: 標題}`。**用 URL 配對，不用位置。**

    第一版是 `{source_id: [標題, ...]}` 再依序取用——同一條來源的第 i 條 body 行
    配第 i 個空欄位。那個作法在兩種情況下會把 A 的標題貼到 B 的網址上：
    某一筆已經有標題（游標不前進，下一筆就拿到前一筆的行），或某一行印的是
    「（標題未留存）」（該行被丟掉，後面全部錯位）。兩種都在單元層重現過。

    2026-07-27 實測 main 上沒有真的錯配（URL 逐筆比對 64 筆全對），但那是資料
    剛好沒踩到，不是機制守得住。body 行本來就帶著 URL，用它當鍵，整類問題消失。
    """
    m = re.search(r"^## 證據\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
    out = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        hit = _EV_LINE.match(line.strip())
        if not hit:
            continue
        rest = hit.group(2).strip()
        # 「（標題未留存）」是佔位不是標題。補進去比空著更糟：空著時 render 知道
        # 要印「標題未留存」，補了假值之後它會以為自己有標題。
        if rest.startswith(_NO_TITLE) or not rest.endswith("）"):
            continue
        title, _, url = rest.rpartition("（")
        title, url = title.strip(), url.rstrip("）").strip()
        if title and url:
            out[url] = title
    return out


def corpus_dates(vault):
    """→ `{url: published}`。同時用 `url` 與 `url_canonical` 建鍵，跟 render 的
    `load_corpus_index()` 一樣——只用其中一個，命中率會掉一大截。"""
    idx = {}
    corpus = vault / "_corpus"
    if not corpus.is_dir():
        return idx
    for day in sorted(corpus.iterdir()):
        if not day.is_dir():
            continue
        for f in sorted(day.glob("*.jsonl")):
            for line in f.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pub = r.get("published")
                if not pub:
                    continue
                for u in (r.get("url"), r.get("url_canonical")):
                    if u:
                        idx.setdefault(u, pub)
    return idx


def backfill(fm, body, dates=None):
    """→ (補了幾個標題, 補了幾個日期)。只補**空的**格，不覆蓋既有值。"""
    ev = fm.get("evidence") or []
    by_url = titles_from_body(body)
    nt = nd = 0
    for e in ev:
        if not e.get("title"):
            found = by_url.get(e.get("url"))
            if found:
                e["title"] = found
                nt += 1
        if not e.get("published"):
            pub = (dates or {}).get(e.get("url"))
            if pub:
                e["published"] = pub
                nd += 1
    return nt, nd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真的寫檔（預設 dry-run）")
    args = ap.parse_args()
    vault = Path(os.environ["VAULT_DIR"])
    files = sorted((vault / "Events").glob("*.md"))
    dates = corpus_dates(vault)
    touched = f_title = f_date = 0
    no_title = no_date = 0
    for p in files:
        fm, body = parse_note(p.read_text("utf-8"))
        if fm is None:
            continue
        nt, nd = backfill(fm, body, dates)
        for e in (fm.get("evidence") or []):
            no_title += 0 if e.get("title") else 1
            no_date += 0 if e.get("published") else 1
        if not (nt or nd):
            continue
        touched += 1
        f_title += nt
        f_date += nd
        if args.apply:
            b = body if body.startswith("\n") else "\n" + body
            p.write_text(f"---\n{dump_frontmatter(fm)}\n---{b}", encoding="utf-8")
    verb = "補上" if args.apply else "可補"
    print(f"evidence 回填：{len(files)} 則 Event，{touched} 則有缺、"
          f"{verb}標題 {f_title} 筆、日期 {f_date} 筆（語料索引 {len(dates)} 筆）")
    # 印出來給人看：0 也要印。補不到的那些不是失敗——標題是 body 裡本來就沒有
    # （evidence_line 當時印的是「（標題未留存）」），日期是語料裡已經查不到。
    # 它們會繼續由 render 誠實地印「未留存」，不會被塞一個看起來合理的值。
    print(f"  補完仍沒有標題: {no_title} 筆｜仍沒有日期: {no_date} 筆"
          f"（維持誠實空著，render 印「未留存」）")
    if not args.apply:
        print("  [dry-run] 未寫檔；加 --apply 才會動")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
