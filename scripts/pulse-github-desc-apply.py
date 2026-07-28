#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-github-desc-apply.py — 星速榜中文描述的寫回（確定性，零 LLM）。

吃潤稿端產出的 `{"<owner/repo>": "中文描述", ...}`，逐條過機械檢查與 voice_clean，
寫進 `_github/desc-zh.json`，並就地補進 `dist/data/github.json`（免得為了一句翻譯
再打一次 GitHub API）。

**這一層不產生任何文字，只驗章與搬運。** 檢查全部是機械的、可測的、無語意判斷的：

  1. 對得上原文     譯文必須綁在「當下這句英文」上。潤稿端拿到 worklist 之後上游
                    如果改了描述，就讓它落榜重譯——寧可空著，不可掛一句在講舊版本的中文。
  2. 真的有中文     一個 CJK 字都沒有 ＝ 英文原樣貼回來，這不叫翻譯。擋掉。
  3. 長度封頂       榜是一行字的版面，超過就不是描述是段落。預設 60 字。
  4. 罩詞黑名單     「值得關注」「無限可能」「隨著…的發展」這類 AI 腔套話，一律退回。
                    speak-human-tw 的規則寫在潤稿端，這裡只兜零容忍的那幾個底。
  5. voice_clean    中國用語 + 半形標點，跟 enrich 走同一支後洗。

不通過的不是靜靜丟掉，是**印出來並列進退件清單**。靜默丟棄是這個系統最危險的失敗模式。

英文原文從哪來：榜（`dist/data/github.json`）讀得到就用榜的；**讀不到就用
`_probe/github-desc-worklist.json`**——榜不進版控，潤稿端 clone 下來根本沒有它。
兩邊都讀不到才是量不到，那時候非零離開，不是靜靜把每一條都退掉。

用法：
  VAULT_DIR=... python scripts/pulse-github-desc-apply.py --in github-desc-result.json --dry-run
  VAULT_DIR=... python scripts/pulse-github-desc-apply.py --in github-desc-result.json
依賴：無（voice_clean 是本地模組）。

離開碼：0＝有東西過關（或結果檔本來就是空的）；2＝結果檔格式不對／量不到
        （榜與 worklist 都讀不到）；3＝**收到了但一條都沒過關**。
        3 跟 0 一定要分得開：全數退件是這條鏈壞掉的樣子，而潤稿端的收尾摘要
        照離開碼寫。上一版一律回 0，所以 2026-07-28 那次 3/3 退件在摘要上長得
        跟「今晚沒有東西要翻」一模一樣。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ghdesc, zhtext  # noqa: E402

MAX_LEN = 60

# 判準（黑名單、CJK 檢查、後洗）搬到 lib/zhtext.py：2026-07-27 起 Event 標題也走
# 同一套。抄第二份會在有人往黑名單加一個字的那天分岔，而且不會有任何東西變紅。
# 上限留在這裡，因為它是**版面**決定的不是語言決定的——榜是一行字。


WORKLIST_REL = ("_probe", "github-desc-worklist.json")

# 退件訊息按「英文原文是哪來的」分開寫。上一版兩種情況共用同一句，而那正是
# 2026-07-28 查出來的錯：訊息說「榜換過了」，實際上榜一次都沒換，是根本沒讀到。
MISSING_NOTE = {
    "board": "不在目前榜單上（榜換過了，下次 prep 會再排進來）",
    "worklist": "不在這一班的待譯清單上（榜讀不到，只能拿 worklist 比對）",
}


def read_json(path):
    """→ 讀得到就回物件，讀不到／壞掉回 None。**不回空容器。**

    回 `{}` 或 `[]` 會讓「我讀不到」跟「裡面是空的」在呼叫端長得一模一樣，
    而這支腳本上一版就是這樣壞的。
    """
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def english_source(board, worklist):
    """→ (full_name → 英文原文, 這份原文哪來的)。兩邊都沒有回 (None, "none")。

    為什麼要有這一層：榜（`dist/data/github.json`）不進版控（.gitignore 第 12 行），
    潤稿端 clone 下來**沒有這個檔**。上一版在這裡寫 `else {"repos": []}`——把
    「我讀不到榜」代理成「榜上沒有這條」，於是每一條譯文都被退件、理由是「榜
    換過了」，而榜一次都沒換。2026-07-28 在乾淨 clone 上實測：3/3 退件、離開碼
    0、潤稿端收尾摘要照著寫會變成「C2 完成，25 條全退，因為榜換過了」——三句
    裡兩句錯，而且把人指向沒有問題的 GitHub 榜單。

    worklist 進版控，而且每一條都帶著 prep 當班的 `desc`。拿它綁雜湊是**對的**，
    不是將就：潤稿端翻的就是那一句英文，上游之後改了描述，`attach()` 會拿當班
    榜單去比對而自動作廢——驗章的嚴格度一格都沒鬆。
    """
    repos = board.get("repos") if isinstance(board, dict) else None
    # `measured is False` 是 pulse-github.py 抓取全失敗時留下的佔位檔，跟 prep
    # 同一個判準：那一班沒量到，它的 repos 不能當「現在的榜」用。
    if isinstance(repos, list) and board.get("measured") is not False:
        return {r.get("full_name"): (r.get("desc") or "") for r in repos}, "board"
    if isinstance(worklist, list):
        return {w.get("full_name"): (w.get("desc") or "") for w in worklist}, "worklist"
    return None, "none"


def exit_code(n_received: int, n_ok: int) -> int:
    """→ 離開碼。3＝收到了但一條都沒過關；0＝有東西過關，或本來就沒東西要翻。

    上一版一律回 0，於是「全數退件」跟「今晚沒有東西要翻」在離開碼上沒有差別
    ——而潤稿端的收尾摘要正是照離開碼寫的。
    """
    return 3 if n_received and not n_ok else 0


def validate(raw, src_desc, missing_note):
    """→ (清理後的中文, 退件原因, 後洗紀錄)。過關時原因為 None。

    `missing_note` 沒有預設值是刻意的：找不到原文有兩種完全不同的成因，給了
    預設值等於允許呼叫端不表態，而不表態的那一版就是上一版。
    """
    return zhtext.validate(
        raw, MAX_LEN, src_present=src_desc is not None,
        len_note="（榜是一行字的版面）", missing_note=missing_note)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--board", default="dist/data/github.json")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    board_path = vault / args.board
    board = read_json(board_path)
    src_by_name, origin = english_source(board, read_json(vault.joinpath(*WORKLIST_REL)))
    if src_by_name is None:
        print(f"[fatal] 榜單（{args.board}）與待譯清單（{'/'.join(WORKLIST_REL)}）都讀不到，"
              f"沒有英文原文可以綁。這不是「沒有東西要翻」，是量不到——"
              f"先確認 Actions 那班有沒有備好清單。", file=sys.stderr)
        return 2
    if origin == "worklist":
        print(f"[note] 讀不到 {args.board}（它不進版控），改用 "
              f"{'/'.join(WORKLIST_REL)} 的原文比對。這是潤稿端的正常路徑，不是錯誤。",
              file=sys.stderr)
    # 不寫 `board["repos"]`：那等於信任 english_source 回的 origin 跟 board 一定
    # 對得上。變異測試打這一層的時候，錯的 origin 會讓這裡丟 TypeError 而不是
    # 印出錯的結果——一個崩潰掩蓋掉一個判斷錯誤，測試就永遠看不到那個判斷錯誤。
    repos = ((board or {}).get("repos") or []) if origin == "board" else []

    result = json.loads(Path(args.infile).read_text("utf-8"))
    if not isinstance(result, dict):
        print("[fatal] 結果檔必須是 {\"owner/repo\": \"中文描述\"} 的 dict", file=sys.stderr)
        return 2

    store = ghdesc.load(vault)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ok, rejected = [], []

    print(f"pulse-github-desc-apply  收到 {len(result)} 條譯文\n")
    for full_name, raw in result.items():
        src = src_by_name.get(full_name)
        zh, why, changes = validate(raw, src, MISSING_NOTE[origin])
        washed = ("；後洗：" + "、".join(f"{a}→{b}" for _, a, b in changes)) if changes else ""
        if why:
            rejected.append((full_name, why, zh))
            print(f"  [退件] {full_name}\n         {why}\n         「{zh}」{washed}")
            continue
        before = store.get(full_name, {}).get("zh")
        store[full_name] = {"zh": zh, "src_hash": ghdesc.src_hash(src), "at": stamp}
        ok.append(full_name)
        tag = "重譯" if before else "新增"
        print(f"  [{tag}] {full_name}\n         「{zh}」{washed}")

    ghdesc.attach(repos, store)
    n_zh = sum(1 for r in repos if r.get("desc_zh"))
    code = exit_code(len(result), len(ok))

    print(f"\n  過關 {len(ok)}／退件 {len(rejected)}；"
          + (f"榜上中文覆蓋 {n_zh}/{len(repos)}" if origin == "board"
             else "榜讀不到，這一班算不出覆蓋率（下一班 Actions 會算）"))
    if rejected:
        print("  退件的不會靜靜消失——下次 prep 會原樣排回待譯清單。")
    if code:
        print(f"  [fail] 收到 {len(result)} 條、一條都沒過關。這跟「今晚沒有東西要翻」"
              f"不是同一件事，所以離開碼是 {code} 不是 0。")

    if args.dry_run:
        print("  [dry-run] 未寫入 _github/desc-zh.json，也未動 github.json")
        return code

    ghdesc.save(vault, store)
    if origin == "board":
        board = dict(board or {}, repos=repos)
        board_path.parent.mkdir(parents=True, exist_ok=True)
        board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  已寫入 _github/desc-zh.json 並就地更新 dist/data/github.json")
    else:
        # 榜讀不到就**不要生一份出來**。上一版在這裡照寫，於是乾淨 clone 上會落下
        # 一個 {"repos": []} 的假榜單，而 prep 下次讀到它會印「今晚沒有東西要翻」
        # ——同一個病往下再傳染一層。
        print("  已寫入 _github/desc-zh.json。榜讀不到，不生一份假的 "
              "dist/data/github.json——真正生效是下一班 Actions 從 desc-zh.json 掛回去。")
    return code


if __name__ == "__main__":
    sys.exit(main())
