#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""變異盤點：真的把碼改壞，看 selftest 會不會紅。

規格見 references/mutation-inventory.md。清單見 scripts/mutations.yaml。

為什麼要有這支：selftest 有幾條測試，跟「碼被改壞會不會被抓到」是兩件事。
2026-07-26 實測，把 pulse-monitor.py 的 `return rc` 改成 `return 0`——CI 紅不紅
就靠那個數字——selftest 224/224 全過。用「測試有幾條」代理「壞掉會不會被抓到」，
是這個 repo 那個老毛病的第五個實例。

用法：
    python3 scripts/mutate.py                 # 跑完整份清單
    python3 scripts/mutate.py --only M01,M02  # 只跑指定條目
    python3 scripts/mutate.py --list          # 只列清單，不跑

回傳碼：
    0  每一條的實測結果都跟 mutations.yaml 記的一樣
    1  有 regression / stale-record / stale-needle / crashed（四種都要有人管）
    2  拒跑（工作區髒、或還原失敗）
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INVENTORY = os.path.join(HERE, "mutations.yaml")
SELFTEST = os.path.join(HERE, "selftest.py")

# selftest 是一支平鋪的腳本：任何未捕捉的例外都會讓它印不出這一行。
# 「沒有這一行」＝這個變異讓碼崩潰了，那不是「測試抓到了」，是變異無效。
TAIL_RE = re.compile(r"^(\d+)/(\d+) passed$", re.M)

REQUIRED = ("id", "file", "find", "replace", "why", "survives")


def load_inventory(path=INVENTORY):
    """讀清單並驗基本形狀。形狀錯就直接炸——清單壞掉不該安靜地少跑幾條。"""
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    items = doc["mutations"]
    seen = set()
    for it in items:
        missing = [k for k in REQUIRED if k not in it]
        if missing:
            raise SystemExit(f"mutations.yaml: {it.get('id', '?')} 缺欄位 {missing}")
        if it["id"] in seen:
            raise SystemExit(f"mutations.yaml: id 重複 {it['id']}")
        seen.add(it["id"])
        if it["survives"] and not str(it.get("why", "")).strip():
            raise SystemExit(
                f"mutations.yaml: {it['id']} 記 survives: true 卻沒寫 why。"
                "已知的缺口掛著是誠實，沒有理由的存活是掩蓋。")
    return items


def needle_count(item):
    """`find` 在目標檔案裡出現幾次。不是 1 就代表清單過期（見規格：坑一）。"""
    p = os.path.join(HERE, item["file"])
    if not os.path.isfile(p):
        return None
    return open(p, encoding="utf-8").read().count(item["find"])


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _clean_pycache():
    """陳舊的 .pyc 會讓變異看起來沒生效——每一輪都清掉。"""
    for dirpath, dirnames, _ in os.walk(ROOT):
        if ".git" in dirpath.split(os.sep):
            continue
        for d in list(dirnames):
            if d == "__pycache__":
                subprocess.run(["rm", "-rf", os.path.join(dirpath, d)], check=False)


def run_selftest(in_flight=""):
    """跑 selftest → (fails, total) 或 None（＝崩潰，沒印出結尾那行）。

    `in_flight` 是**正在被注入**的那條 id。selftest 有一條在數每個 `find` 在目標
    檔案裡出現幾次；注入期間那一條的針腳正被換掉，當然數到 0。不把它排除的話，
    這條檢查會在每一次注入都紅——**每一條變異都會「被殺」**，kill 訊號變成常數，
    整層就只剩下在量「這條檢查還在不在」。2026-07-26 第一次跑就踩到：四條已知的
    存活者（M01/M02/M03/M11）全被誤判成 killed。基準線那一輪不設這個值。
    """
    _clean_pycache()
    env = dict(os.environ, VAULT_DIR=ROOT)
    env["MUTATE_IN_FLIGHT"] = in_flight
    p = subprocess.run([sys.executable, SELFTEST],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    m = TAIL_RE.search(p.stdout)
    if not m:
        return None
    passed, total = int(m.group(1)), int(m.group(2))
    return total - passed, total


def apply_one(item):
    """注入一條變異，跑 selftest，**一定**還原。回傳 (verdict, detail)。"""
    path = os.path.join(HERE, item["file"])
    before = open(path, encoding="utf-8").read()
    n = before.count(item["find"])
    if n != 1:
        return "stale-needle", f"`find` 在 {item['file']} 出現 {n} 次（要剛好 1 次）"
    sha_before = hashlib.sha256(before.encode("utf-8")).hexdigest()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(before.replace(item["find"], item["replace"], 1))
        got = run_selftest(in_flight=item["id"])
    finally:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(before)
    if _sha(path) != sha_before:
        raise SystemExit(f"[FATAL] {item['file']} 還原失敗，不要 commit 這棵樹")
    if got is None:
        return "crashed", "selftest 沒有印出 `N/M passed`——這個變異讓碼崩潰了，不算數"
    fails, total = got
    killed = fails > 0
    survived = not killed
    detail = f"{total - fails}/{total} passed（{fails} 條紅）"
    if survived and not item["survives"]:
        return "regression", detail + " ← 沒有任何測試在守這裡"
    if killed and item["survives"]:
        return "stale-record", detail + " ← 已經有測試守住了，清單該更新"
    return ("survived-as-recorded" if survived else "killed"), detail


def parse_shard(spec):
    """"k/n" → (k, n)。壞掉的規格一律拒跑，不猜。

    猜的話最糟的結果是**只跑了一部分卻報成全部跑過**——而這支腳本的整個價值
    就是「清單上的每一條都還守得住」。少跑一片而沒有人知道，比整支掛掉更糟。
    """
    try:
        k, n = (int(x) for x in str(spec).split("/", 1))
    except (TypeError, ValueError):
        raise SystemExit(f"--shard 要寫成 k/n，收到：{spec!r}")
    if n < 1 or not (1 <= k <= n):
        raise SystemExit(f"--shard 超出範圍：{spec!r}（要 1 ≤ k ≤ n，n ≥ 1）")
    return k, n


def shard(items, k, n):
    """把清單切成 n 片，回第 k 片（1-based）。

    切法是**依索引取模**，不是依檔案分組：同一個檔的變異會散到不同片，
    每片的耗時才會接近。依檔案分組的話，`pulse-render.py` 那 57 條會擠在同一片，
    那一片跑的時間跟不切幾乎一樣。

    這個切法是確定性的：同一份清單、同一個 n，每一條永遠落在同一片。
    分片必須是一個**分割**（不重不漏），selftest 有一條釘住這件事——
    一條變異因為切片邏輯而從來沒被跑過，是這支腳本最糟的失敗方式：
    清單看起來很完整，而其中一格從來沒有人驗過。
    """
    return [it for i, it in enumerate(items) if i % n == (k - 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="逗號分隔的 id")
    ap.add_argument("--shard", help="k/n —— 只跑第 k 片（1-based），共 n 片")
    ap.add_argument("--list", action="store_true", help="只列清單")
    args = ap.parse_args()

    items = load_inventory()
    if args.shard:
        items = shard(items, *parse_shard(args.shard))
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        unknown = want - {i["id"] for i in items}
        if unknown:
            raise SystemExit(f"--only 指到不存在的 id：{sorted(unknown)}")
        items = [i for i in items if i["id"] in want]

    if args.list:
        for it in items:
            mark = "存活" if it["survives"] else "被殺"
            print(f"{it['id']}  [{mark}]  {it['file']}  — {it['title']}")
        return 0

    # 護欄一：目標檔案已經髒了就拒跑。已經髒的樹出事時分不清哪些改動是誰的。
    targets = sorted({i["file"] for i in items})
    porcelain = subprocess.run(["git", "status", "--porcelain", "--"]
                               + [os.path.join("scripts", t) for t in targets],
                               capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if porcelain:
        print("[拒跑] 目標檔案有未提交的改動：\n" + porcelain, file=sys.stderr)
        print("這支會真的改原始碼再還原，髒樹上出事分不清是誰的改動。", file=sys.stderr)
        return 2

    base = run_selftest()
    if base is None or base[0] != 0:
        print(f"[拒跑] 沒動任何東西時 selftest 就不是全綠：{base}", file=sys.stderr)
        return 2
    print(f"基準線 {base[1]}/{base[1]} passed\n" + "-" * 70)

    bad, results = [], []
    for it in items:
        verdict, detail = apply_one(it)
        results.append((it, verdict, detail))
        flag = verdict in ("regression", "stale-record", "stale-needle", "crashed")
        if flag:
            bad.append((it, verdict, detail))
        print(f"[{verdict:>20}] {it['id']}  {it['title']}\n"
              f"{'':>23}{detail}")

    print("-" * 70)
    killed = sum(1 for _, v, _ in results if v == "killed")
    alive = sum(1 for _, v, _ in results if v == "survived-as-recorded")
    print(f"{len(results)} 條：{killed} 被殺、{alive} 存活（清單有記）、{len(bad)} 要人管")

    if alive:
        print("\n已知守不住的地方（清單裡記著，各自有出處）：")
        for it, v, _ in results:
            if v == "survived-as-recorded":
                print(f"  {it['id']}  {it['why']}")

    if bad:
        print("\n要人管的：")
        for it, v, d in bad:
            print(f"  [{v}] {it['id']} {it['title']}\n        {d}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
