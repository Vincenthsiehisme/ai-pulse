#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-digest-gate.py — 每日精選的人審那一關 + 收錄頁。規格：references/digest-review.md。

掃 `Digests/*.md`，算出每一份該落在哪一桶、寫回 frontmatter，並產
`_dashboards/digests.md` 讓人知道該審哪一份、還缺什麼。

**這一版擋不住任何東西，而那是要被說出來的。** `digest-framework` 給這一關的
職責是「三格沒填完就不 render」，而 `pulse-render.py` 今天不 render digest
（`daily` 這個字在它裡面出現 0 次）。所以它現在是一個狀態計算器。
理由與到期日寫在規格開頭那一節——`/daily/` 落地時要回去把它刪掉。

用法：VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-digest-gate.py [--dry-run]
依賴：PyYAML。
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import buckets as _buckets  # noqa: E402  對帳形狀的單一真相源
from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib.notes import dump_frontmatter, parse_note  # noqa: E402

# 這三個是收錄頁認得的 status。改這裡等於改對帳的定義，不要順手加。
# 「內容改過」不是第四個 status，是 draft 底下的一個標記（stale_at）——
# 多一個 status 就多一條「怎麼離開它」的路要設計，而那條路上一版差點變成
# 「叫人自己算一個雜湊」。理由見 references/digest-review.md。
STATUSES = ("draft", "reviewed", "rejected")
VERDICT_OK = "ok"
VERDICT_NO = "no"

# 文末那一段是給審的人看的附錄，不是文章。簽章只簽它前面的部分。
ARTICLE_END = "## 這篇的層次"


def article_text(body):
    """讀者會看到的那一段：文末〈這篇的層次〉附錄之前的全部。

    簽章簽這個而不是簽 frontmatter 裡的一份副本——複製一份正文進 frontmatter
    就是兩份會分岔的同一段話，而 `pulse-digest-apply.py` 整支的設計核心正是
    不要那個。附錄裡的 basis / counter 改了不會動到簽章，那是已知缺口，
    寫在規格〈二〉，不假裝有蓋到。
    """
    return body.split(ARTICLE_END, 1)[0].strip()


def article_signature(body):
    """文章的內容簽章。做法沿用 pulse-narrative-prep.signature()。"""
    return hashlib.sha1(article_text(body).encode("utf-8")).hexdigest()[:16]


def missing_reviews(fm):
    """三格還缺什麼。回 [(格名, 說明)]，空的＝齊了。

    後兩格**要點名不要打勾**：你列的段落 id 集合必須剛好等於這篇裡所有 B（或 C）
    級段落。你不打開檔案就列不出來，所以蓋章的成本被機械地拉高了。
    這擋不住「抄了 id 但沒讀內容」——那件事沒有規則抓得到，規格裡寫明了。

    空 list `[]` 跟 `None` 是兩件事：前者是「看過了，沒有東西要審」，
    後者是「還沒審」。把「沒有」跟「不知道」寫成同一個值，正是這個 repo
    一直在修的病（見 references/evidence-availability.md）。
    """
    out = []
    if "section_layers" not in fm:
        # **缺席不等於零。** 這一格是 2026-08-17 才有的；在那之前寫的 digest
        # 沒有它，而 `fm.get(...) or {}` 會讓 want 變成空集合——於是後兩格填 `[]`
        # 就過了，整個「點名」設計被繞開，而收錄頁會說它審完了。
        # 這正是這個 repo 一直在修的病（把「沒有」跟「不知道」寫成同一個值），
        # 而它出現在守那個病的這一支自己身上。
        return [("section_layers", "這一份沒有段落層次資料（2026-08-17 之前寫的）。"
                                   "人審那一關對它是空轉的——先跑一次回填，見 "
                                   "references/digest-review.md〈舊格式〉")]
    layers = fm.get("section_layers") or {}
    v = fm.get("review_question")
    if v not in (VERDICT_OK, VERDICT_NO):
        out.append(("review_question", f"要填 {VERDICT_OK} 或 {VERDICT_NO}，現在是 {v!r}"))
    for key, layer in (("review_background", "B"), ("review_counter", "C")):
        want = {str(sid) for sid, la in layers.items() if la == layer}
        got = fm.get(key)
        if got is None:
            out.append((key, f"還沒填（這篇有 {len(want)} 個 {layer} 級段落）"))
            continue
        if not isinstance(got, list):
            out.append((key, f"要填一串段落 id，現在是 {type(got).__name__}"))
            continue
        have = {str(x) for x in got}
        if have != want:
            miss = sorted(want - have)
            extra = sorted(have - want)
            bits = []
            if miss:
                bits.append("漏了 " + "、".join(miss))
            if extra:
                bits.append("多了 " + "、".join(extra) + "（不是這一層的段落）")
            out.append((key, "；".join(bits)))
    return out


def evaluate(fm, body):
    """這一份該落在哪一桶。回 (status, 還缺什麼, 內容改過了沒)。純函式。

    順序有意義：

      1. 退回（`review_question: no`）最優先，而且**一定要寫理由**——
         沒理由的退回跟資料不見了沒有區別（同 dropped 那條）。
      2. 內容改過蓋過「三格齊了」。反過來的話，一份審過之後被改掉的稿
         會維持 `reviewed`，而「審過」這件事就跟檔案裡的東西脫鉤了。
      3. 才輪到三格齊不齊。

    被退的那一份就算之後內容改過也維持 `rejected`：夜班不會重寫它
    （寫檔守衛擋著），所以內容會變只有一種可能——人動的。人動完自己改
    `review_question` 就好，不需要這一層替他決定。
    """
    old = str(fm.get("reviewed_sig") or "")
    stale = bool(old) and old != article_signature(body)
    if str(fm.get("review_question") or "") == VERDICT_NO:
        if not str(fm.get("review_note") or "").strip():
            return "draft", [("review_note", "退回一定要寫理由，不然沒有人知道該改什麼")], stale
        return "rejected", [], stale
    if stale:
        return "draft", [("reviewed_sig", "文章改過了，三格作廢，要重審")], True
    missing = missing_reviews(fm)
    if missing:
        return "draft", missing, False
    return "reviewed", [], False


def apply_verdict(fm, status, stale, now):
    """把判定寫回 frontmatter。回「改了哪幾格」，沒改回空 list。

    進 stale 時**把三格清成 null**：那三個答案是對改之前那一版文章給的，
    留著會讓收錄頁把它算成「審過」。清掉之後人重填一次，簽章自然重算——
    這是唯一一條不需要人自己算雜湊的回頭路。
    """
    changed = []
    if fm.get("status") != status:
        changed.append(f"status {fm.get('status')} → {status}")
        fm["status"] = status
    if stale and not fm.get("stale_at"):
        fm["stale_at"] = now
        fm["stale_from_sig"] = fm.get("reviewed_sig")
        for k in ("review_question", "review_background", "review_counter", "reviewed_sig"):
            fm[k] = None
        changed.append("內容改過 → 三格作廢")
    if status == "reviewed":
        if fm.get("stale_at"):
            fm["stale_at"] = None
            changed.append("重審通過")
        changed.append("蓋上簽章")
    return changed


def index_page(rows, generated):
    """_dashboards/digests.md。rows = [(檔名, fm, status, missing, stale)]。"""
    def label(fm, p):
        return f"[[Digests/{p[:-3]}|{fm.get('title') or p[:-3]}]]"

    waiting = [r for r in rows if r[2] == "draft" and not r[4] and not r[1].get("stale_at")]
    restale = [r for r in rows if r[2] == "draft" and (r[4] or r[1].get("stale_at"))]
    ready = [r for r in rows if r[2] == "reviewed"]
    sent_back = [r for r in rows if r[2] == "rejected"]

    out = ["---", "kind: dashboard", f"generated: {generated}", "---", "",
           "# 每日精選", "",
           "> 這一頁由 `pulse-digest-gate.py` 產生，不要手改。",
           "> 要審就直接開那一份 digest，把 frontmatter 的三格填了。",
           "> 判準與怎麼填見 `references/digest-review.md`。", ""]

    def block(title, items, with_missing=False, with_note=False):
        out.append(f"## {title}（{len(items)}）")
        out.append("")
        if not items:
            out.append("（無）")
            out.append("")
            return
        for p, fm, _s, missing, _st in items:
            n = len(fm.get("section_layers") or {})
            out.append(f"- **{label(fm, p)}** — {fm.get('date')} · {n} 段")
            if with_missing and missing:
                for key, why in missing:
                    out.append(f"  - `{key}`：{why}")
            if with_note and fm.get("review_note"):
                out.append(f"  - 退回理由：{fm['review_note']}")
        out.append("")

    block("等你審", waiting, with_missing=True)
    block("內容改過，要重審", restale, with_missing=True)
    block("已審可發", ready)
    block("退回重寫", sent_back, with_note=True)
    out += ["---", "",
            "**「已審可發」現在不會發到任何地方。** `pulse-render.py` 還沒有 "
            "`/daily/`，所以這一關算得出狀態、擋不住東西。理由與到期日見 "
            "`references/digest-review.md` 開頭那一節。", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    digests = vault / "Digests"
    now = clock.utc_stamp()
    rows = []
    if digests.exists():
        for p in sorted(digests.glob("*.md")):
            fm, body = parse_note(p.read_text("utf-8"))
            status, missing, stale = evaluate(fm, body)
            changed = apply_verdict(fm, status, stale, now)
            if status == "reviewed":
                fm["reviewed_sig"] = article_signature(body)
                fm["reviewed_at"] = now
            if changed and not args.dry_run:
                p.write_text(f"---\n{dump_frontmatter(fm)}\n---{body if body.startswith(chr(10)) else chr(10) + body}",
                             encoding="utf-8")
            rows.append((p.name, fm, status, missing, stale))

    # 對帳：每一份都要落在某一桶。落不進去的是壞掉的檔，不是一種狀態。
    leftover = _buckets.unbucketed([(n, fm.get("status")) for n, fm, _s, _m, _st in rows],
                                   STATUSES)
    page = index_page(rows, now)
    if not args.dry_run:
        (vault / "_dashboards").mkdir(parents=True, exist_ok=True)
        (vault / "_dashboards" / "digests.md").write_text(page, encoding="utf-8")

    hist = {}
    for _n, _fm, s, _m, _st in rows:
        hist[s] = hist.get(s, 0) + 1
    print("pulse-digest-gate  " + "  ".join(f"{k}={hist.get(k, 0)}" for k in STATUSES)
          + f"  共 {len(rows)} 份" + ("  [dry-run]" if args.dry_run else "  → _dashboards/digests.md"))
    for n, fm, s, missing, _st in rows:
        if s == "draft" and missing:
            print(f"  ── {n} ──")
            for key, why in missing:
                print(f"    {key}: {why}")
    if leftover:
        print(f"[fatal] {len(leftover)} 份 digest 的 status 不屬於 "
              f"{'/'.join(STATUSES)}，它們不在收錄頁的任何一段裡：", file=sys.stderr)
        for n, s in leftover:
            print(f"  {n}  status={s!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
