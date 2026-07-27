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

import json

from . import zhtext

STORE_REL = ("_github", "desc-zh.json")


def src_hash(desc: str) -> str:
    """英文原文 → 短雜湊。空描述也給得出穩定值。

    判準搬到 `lib/zhtext.py`（2026-07-27，Event 標題也要翻的時候）——這裡保留
    名字是為了不動既有呼叫端，**但只有一份實作**。
    """
    return zhtext.src_hash(desc)


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


# ------------------------------------------------------- 覆蓋率（機器讀得到的）
# 為什麼要有這一段：`pulse-github.py` 從第一天就會印
# 「中文描述=0/25」——**印在 CI 的 log 裡**。人看得到，機器讀不到，於是
# 「這個榜已經連續幾天沒有中文」沒有任何地方存著。
#
# 而潤稿端的 C2 段（翻描述）依 runbook 的規定是**失敗就整段跳過**：
# 「這步失敗就整個 C2 段跳過，不影響其他段——榜會維持上一晚的英文原文。」
# 跳過不留痕跡的後果很具體：**「跳過了」跟「沒有東西要翻」在 repo 這端印起來
# 一模一樣**——兩種情況下 `_github/desc-zh.json` 都不存在。
# 實測 2026-07-27：那個檔在整個 git 歷史裡從來沒有出現過，而沒有任何一天有人發現。
#
# 修法不是叫潤稿端更努力回報——**它失敗的時候本來就寫不進 repo**。
# 修法是讓**一定會跑的那條鏈**（Actions）每班量一次結果，寫進版控。
# 這跟「健康分沒有輸入」那次是同一句話：觀測要住在會跑的那一邊。
COVERAGE_REL = ("_github", "desc-coverage.json")


def coverage_path(vault):
    return vault.joinpath(*COVERAGE_REL)


def load_coverage(vault) -> dict:
    p = coverage_path(vault)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text("utf-8")) or {}
    except (ValueError, OSError):
        return {}


def next_coverage(prev: dict, day: str, ranked_n, with_zh_n, store_n: int) -> dict:
    """算出這一班的覆蓋率紀錄。純函式，不碰磁碟、不讀時鐘（day 由呼叫端給）。

    `last_with_zh_day` 是**黏的**：只有真的量到中文才更新。所以兩種情況分得出來——

      last_with_zh_day 是 null    → **從來沒有過**。這是缺工，不是故障。
      有值、而且離今天很遠        → **有過然後停了**。這才是故障。

    分不出來的話，這個數字只會逼出一個天天紅的警報（第一天就 0 條中文），
    而一個天天紅的 CI 跟一個永遠綠的一樣沒有資訊。

    `ranked_n` / `with_zh_n` 允許 None——榜單抓取失敗那一班量不到，
    **量不到就寫 null，不寫 0**（紅線 8）。`store_n` 一律量得到，它只是數檔案。
    """
    prev = prev or {}
    last = prev.get("last_with_zh_day")
    if with_zh_n:
        last = day
    return {
        "day": day,
        "ranked": ranked_n,
        "with_zh": with_zh_n,
        "store_entries": store_n,
        "last_with_zh_day": last,
    }


def days_without_zh(cov: dict, today: str):
    """→ 幾天沒有中文描述；從來沒有過回 None（**不是 0，也不是很大的數**）。

    回 None 是刻意的：「從來沒有」跟「昨天還有」是兩件事，用同一個數字表示，
    第一種就會被讀成第二種。
    """
    import datetime
    last = (cov or {}).get("last_with_zh_day")
    if not last:
        return None
    try:
        a = datetime.date.fromisoformat(str(last))
        b = datetime.date.fromisoformat(str(today))
    except ValueError:
        return None
    return (b - a).days
