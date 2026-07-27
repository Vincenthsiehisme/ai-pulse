#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-entity-notes.py — 產生 `Tracks/*.md` 與 `Actors/*.md`。

規格見 references/obsidian-schema.md。改這裡之前先改那裡（紅線 9）。

為什麼要有這一支：帳號層 skill 的 vault 結構圖從第一天就畫著 `Tracks/` 與
`Actors/` 兩個資料夾，**repo 這端一直不存在**。於是這個 vault 的關聯圖只有
一維（Event → Source），而「backlink 天生就是那張圖」正是選 Obsidian 而不是
SQLite 的理由。規格說有、實作沒有、沒有任何東西會紅——同一個形態的第五次。

邊的方向是**維度頁 → Event**，不是反過來。理由寫在規格裡，一句話版本：
`company` / `track` 是四支碼在讀的機器欄位，改成 wikilink 字串會讓漏改的那個
安靜地少一半事件；而 Obsidian 的 graph 是無向的，這一邊畫跟那一邊畫同一張圖。

不碰網路、不跑子行程、不呼叫任何模型。0 LLM。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.atomicwrite import atomic_write_text  # noqa: E402
from lib import tracks as tracks_lib  # noqa: E402

import yaml  # noqa: E402

GENERIC_COMPANY = "industry"   # infer_company() 認不出實體時的兜底，不是一家公司
_FS_UNSAFE = re.compile(r'[/\\:*?"<>|]')


def _read(p: Path):
    return p.read_text("utf-8") if p.is_file() else None


def safe_name(name: str) -> str:
    """檔名用。只換掉檔案系統不接受的字元，**不做任何正規化**——
    正規化過的名字跟 frontmatter 裡的值就對不起來了，而那個對照沒有人在維護。
    """
    return _FS_UNSAFE.sub("-", (name or "").strip()) or "unnamed"


def load_events(vault: Path):
    """→ [{id, title, date, status, company, track, path}]，只讀 frontmatter。"""
    out = []
    d = vault / "Events"
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md")):
        text = p.read_text("utf-8")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end < 0:
            continue
        try:
            fm = yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            continue          # 壞掉的 Event 不該讓整批頁面產不出來
        if not fm.get("id"):
            continue
        out.append({"id": fm["id"], "title": fm.get("title") or fm["id"],
                    "date": str(fm.get("date") or ""), "status": fm.get("status"),
                    "company": fm.get("company"), "track": fm.get("track"),
                    "stem": p.stem})
    return out


def load_companies(vault: Path):
    """→ {canonical: {id, aliases}}，來自 _config/entities.yaml。"""
    raw = yaml.safe_load(_read(vault / "_config" / "entities.yaml") or "") or {}
    out = {}
    for c in raw.get("companies") or []:
        if isinstance(c, dict) and c.get("canonical"):
            out[c["canonical"]] = {"id": c.get("id"),
                                   "aliases": list(c.get("aliases") or [])}
    return out


def load_theses(vault: Path):
    """→ {slug: thesis}。只拿編輯層的 thesis，**不拿 now / next**：
    那兩段每夜重寫，抄過來會讓六個檔案每天生一次沒有新資訊的 diff，
    而且會出現兩份可能不一致的同一段話。
    """
    raw = yaml.safe_load(_read(vault / "_config" / "narratives.yaml") or "") or {}
    return {k: (v or {}).get("thesis") for k, v in (raw.get("tracks") or {}).items()}


def _event_line(e):
    status = e["status"] or "—"
    date = e["date"] or "—"
    return f"| {date} | [[Events/{e['stem']}\\|{e['title']}]] | {status} |"


def _event_table(events):
    if not events:
        return ["| （目前沒有） | | |"]
    rows = sorted(events, key=lambda e: (e["date"], e["id"]), reverse=True)
    return [_event_line(e) for e in rows]


def render_track(name, slug, color, thesis, events, day):
    counts = defaultdict(int)
    for e in events:
        counts[e["status"] or "—"] += 1
    lines = [
        "---",
        f"id: track-{slug}",
        "kind: track",
        f"slug: {slug}",
        f"color: '{color}'",
        f"generated_day: '{day}'",
        "generator: scripts/pulse-entity-notes.py",
        "tags: [track]",
        "---",
        "",
        f"# {name}",
        "",
    ]
    if thesis:
        lines += ["> " + thesis.replace("\n", " "), "",
                  "上面這句是 `_config/narratives.yaml` 的編輯層 `thesis`。"
                  "每夜重寫的 `now` / `next` **刻意不抄過來**——抄過來會出現兩份"
                  "可能不一致的同一段話，要讀就去看那個檔。", ""]
    else:
        lines += ["（`narratives.yaml` 還沒有這條線的 `thesis`。）", ""]
    lines += [f"事件 **{len(events)}** 則：" +
              ("、".join(f"`{k}` {v}" for k, v in sorted(counts.items())) or "（無）"),
              "",
              "| 日期 | 事件 | 狀態 |", "|---|---|---|"]
    lines += _event_table(events)
    lines += ["",
              "這一頁往外連 Event，Event 不往回連這一頁——graph 是無向的，"
              "兩邊畫出來是同一張圖。理由見 `references/obsidian-schema.md`。", ""]
    return "\n".join(lines)


def render_actor(name, info, events, day):
    counts = defaultdict(int)
    for e in events:
        counts[e["status"] or "—"] += 1
    in_dict = info is not None
    eid = (info or {}).get("id") or safe_name(name).lower().replace(" ", "-")
    aliases = (info or {}).get("aliases") or []
    lines = [
        "---",
        f"id: actor-{eid}",
        "kind: company",
        f"in_dictionary: {'true' if in_dict else 'false'}",
        "aliases: [" + ", ".join(f'"{a}"' for a in aliases) + "]",
        f"generated_day: '{day}'",
        "generator: scripts/pulse-entity-notes.py",
        "tags: [actor, company]",
        "---",
        "",
        f"# {name}",
        "",
    ]
    if not in_dict:
        lines += ["> ⚠ **字典裡沒有這家公司。** 它是從 Event 的 `company` 欄位"
                  "冒出來的，代表 `_config/entities.yaml` 少收了一條——"
                  "或者 `infer_company()` 推錯了。兩種都要人看一眼。", ""]
    lines += [f"事件 **{len(events)}** 則：" +
              ("、".join(f"`{k}` {v}" for k, v in sorted(counts.items())) or "（無）"),
              ""]
    if in_dict and not events:
        lines += ["字典收了它，但這段期間**一則事件都沒有**。這不代表它沒新聞——"
                  "也可能是沒有任何一條來源看得到它（對照 `_config/sources.yaml` 的"
                  "`coverage_watch`）。四態分離：收錄 ≠ 已觀測 ≠ 有效產出 ≠ 已發布。",
                  ""]
    lines += ["| 日期 | 事件 | 狀態 |", "|---|---|---|"]
    lines += _event_table(events)
    lines.append("")
    return "\n".join(lines)


def plan(vault: Path, day: str):
    """→ {相對路徑: 內容}。純函式，不寫磁碟，所以測得動。"""
    events = load_events(vault)
    companies = load_companies(vault)
    theses = load_theses(vault)

    by_track = defaultdict(list)
    unknown_track = []
    for e in events:
        name = tracks_lib.canonical_name(e["track"])
        if name:
            by_track[name].append(e)
        else:
            unknown_track.append(e)

    by_actor = defaultdict(list)
    no_company = []
    for e in events:
        c = (e["company"] or "").strip()
        if not c or c == GENERIC_COMPANY:
            no_company.append(e)
            continue
        by_actor[c].append(e)

    out = {}
    for slug, name, color in tracks_lib.TRACKS:
        out[f"Tracks/{safe_name(name)}.md"] = render_track(
            name, slug, color, theses.get(slug), by_track.get(name, []), day)

    for name in sorted(set(companies) | set(by_actor)):
        out[f"Actors/{safe_name(name)}.md"] = render_actor(
            name, companies.get(name), by_actor.get(name, []), day)

    out["Tracks/_未歸類.md"] = render_leftovers(unknown_track, no_company, day)
    return out


def render_leftovers(unknown_track, no_company, day):
    """認不出主線、或沒有歸屬到公司的事件。

    **不靜靜丟掉**是重點：這兩批在上面那些頁面上都不會出現，如果不另外列一頁，
    「六條線的事件加起來少於 Events/ 的總數」這件事沒有任何地方看得到。
    """
    lines = [
        "---",
        "id: track-unclassified",
        "kind: track",
        f"generated_day: '{day}'",
        "generator: scripts/pulse-entity-notes.py",
        "tags: [track, unclassified]",
        "---",
        "",
        "# 沒有進到任何維度頁的事件",
        "",
        "這一頁存在的理由只有一個：**六條主線頁的事件數加起來會少於 `Events/` 的"
        "總數，而少掉的那些如果沒有地方列，就沒有任何人會發現。**",
        "",
        f"## 認不出主線的事件（{len(unknown_track)} 則）",
        "",
        "`track` 的值不在 `lib/tracks.py` 的別名表裡。認不出來是 enrich 或別名表的"
        "問題，不是「這則不存在」。",
        "",
        "| 日期 | 事件 | `track` 原值 |", "|---|---|---|",
    ]
    lines += [f"| {e['date'] or '—'} | [[Events/{e['stem']}\\|{e['title']}]] | "
              f"`{e['track']}` |" for e in sorted(
                  unknown_track, key=lambda x: (x["date"], x["id"]), reverse=True)] \
        or ["| （無） | | |"]
    lines += [
        "",
        f"## 沒有歸屬到公司的事件（{len(no_company)} 則）",
        "",
        f"`company` 是空的、或是 `{GENERIC_COMPANY}`——後者是 `infer_company()` 認不出"
        "實體時的泛稱兜底，**不是一家公司**，所以不產 Actor 頁。這一批通常帶著"
        "`generic_entity` blocker 等人修。",
        "",
        "| 日期 | 事件 | `company` 原值 |", "|---|---|---|",
    ]
    lines += [f"| {e['date'] or '—'} | [[Events/{e['stem']}\\|{e['title']}]] | "
              f"`{e['company']}` |" for e in sorted(
                  no_company, key=lambda x: (x["date"], x["id"]), reverse=True)] \
        or ["| （無） | | |"]
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    day = datetime.now(timezone.utc).date().isoformat()
    pages = plan(vault, day)

    if args.dry_run:
        for rel in sorted(pages):
            print(f"--- {rel} ---")
        return 0

    written = 0
    for rel, text in pages.items():
        path = vault / rel
        # 內容沒變就不重寫：一天 12 班，六條線 + 幾十個 Actor 每班一個空 diff，
        # 真正的變化會被埋掉（references/vault-pages.md 的共同規則）。
        if _read(path) == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text)
        written += 1
    if not args.quiet:
        print(f"[ok] entity notes：{len(pages)} 頁，{written} 頁有異動")
    return 0


if __name__ == "__main__":
    sys.exit(main())
