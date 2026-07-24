# -*- coding: utf-8 -*-
"""ghdesc.py — GitHub 動能榜的中文描述儲存層（確定性，零 LLM）。

背景：星速榜的 repo 描述直接來自 GitHub API，是英文一行字。榜是給中文讀者看的，
描述卻要人自己翻——但**翻譯是敘述，不是判斷**，所以它走潤稿端（Cowork + speak-human-tw），
不進每晚的確定性抓取鏈。抓取鏈永遠自己跑得完，中文晚一步到，這是設計不是缺陷。

這一層只做三件事，都是機械的：

  1. 存：`_github/desc-zh.json`，`full_name → {zh, src_hash, at}`。
  2. 綁：`src_hash` 是**當下那句英文原文**的雜湊。上游改了描述 → 雜湊對不上 → 中文
     自動失效退回原文，並重新排進待譯清單。少了這一步，repo 改版之後榜上會掛著
     一句看起來很合理、其實在講舊版本的中文——那比沒有中文糟得多。
  3. 附：`attach()` 把有效的中文掛回榜單。原文一律保留在 `desc`，前台兩行都印。
     這不是版面潔癖，是紅線 2 的延伸：譯文是二手的，讀者要能一眼看到一手的那句。

紅線：本檔不產生任何文字，只搬運與驗章。翻譯由潤稿端寫、由 voice_clean 後洗。
"""
from __future__ import annotations

import hashlib
import json

STORE_REL = ("_github", "desc-zh.json")


def src_hash(desc: str) -> str:
    """英文原文 → 短雜湊。空描述也給得出穩定值。"""
    return hashlib.sha1((desc or "").strip().encode("utf-8")).hexdigest()[:12]


def store_path(vault):
    return vault.joinpath(*STORE_REL)


def load(vault) -> dict:
    p = store_path(vault)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text("utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def save(vault, store: dict) -> None:
    p = store_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True),
                 encoding="utf-8")


def attach(repos, store):
    """把有效中文掛進 repo dict（就地修改並回傳）。

    有效＝存過、非空、且 src_hash 對得上當下的英文原文。
    對不上就當沒有——寧可顯示英文，不可顯示對不上原文的中文。
    """
    for r in repos:
        entry = store.get(r.get("full_name")) or {}
        zh = (entry.get("zh") or "").strip()
        r["desc_zh"] = zh if zh and entry.get("src_hash") == src_hash(r.get("desc")) else ""
    return repos


def pending(repos, store):
    """→ 還沒有有效中文的 repo（待譯清單）。順序沿用榜單順序＝重要的先譯。"""
    out = []
    for r in repos:
        entry = store.get(r.get("full_name")) or {}
        zh = (entry.get("zh") or "").strip()
        if zh and entry.get("src_hash") == src_hash(r.get("desc")):
            continue
        out.append({
            "full_name": r.get("full_name"),
            "desc": r.get("desc") or "",
            "language": r.get("language") or "",
            "topics": r.get("topics") or [],
            "stars": r.get("stars"),
            "url": r.get("url"),
            # 舊譯文附上去，讓潤稿端知道這條是「上游改描述所以要重譯」而不是全新的。
            "stale_zh": zh if zh else None,
        })
    return out
