#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-digest-apply.py — 每日精選的寫回層：機檢退件，然後才寫檔。

規格：references/digest-apply.md（上游是 references/digest-framework.md）。

吃一份 Cowork 依 schema 寫出來的分層 JSON，對照當日的 `_probe/digest-worklist.json`
逐條機檢；有任何一條退件就**不寫檔**、原樣印出退件理由、回離開碼 1。全過才
voice_clean 後寫 `Digests/<date>.md`。

這一支是**判斷層**（紅線 1）：退不退件由規則決定，不由寫的人自評。

為什麼沒有 `body` 這個欄位（規格〈一〉，這是整支的設計核心）：
    第一版想讓寫的人交「全文 + 每句標層的 claims[]」，機檢查 claims。那是假的守衛
    ——讀者讀的是全文，而全文裡完全可以多出一句沒登記的話，機檢會全綠因為它檢的
    是另一份文件。手寫那篇好看的原因，正好全在沒有證據的那幾句。
    所以這一版**文章由 sections 組出來**，claims 就是文章本身，兩者不可能分岔。
用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-digest-apply.py --in digest.json [--dry-run] [--force]
依賴：PyYAML。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from lib import clock  # noqa: E402  取日期的唯一入口，見 references/timezones.md
from lib import voice_clean  # noqa: E402
from lib.availability import WITHHELD  # noqa: E402  跟門禁同一份判準，不另寫一套
from lib.notes import dump_frontmatter  # noqa: E402

LAYERS = ("A", "B", "C", "D")

# 封閉式推論黑名單。**刻意窄**：這條規則誤殺的代價比漏抓大——被誤殺的人會改寫成
# 同義的句子繞過去，然後這條規則就只是在管字面。漏掉的那些由人審那一關接住。
CLOSED_INFERENCE = ("只有一種可能", "唯一的解釋", "唯一可能", "無庸置疑",
                    "毫無疑問", "不可避免地", "必然會")

# 「不是 A，是 B」。一篇一次是強調，三次是口頭禪。
_NOT_A_BUT_B = re.compile(r"不是[^。！？\n]{1,24}?，(?:而)?是")
_BOLD = re.compile(r"\*\*[^*\n]+\*\*")


def load_worklist(vault):
    """讀當日素材清單。**這一支不自己算可得性**——`availability` 由 prep 算好放在
    worklist 裡，跟門禁的 `thin_by_policy` 走同一份 `lib/availability`。
    在這裡另寫一份判準，就會有兩個地方對同一個來源給出不同答案。
    """
    p = vault / "_probe" / "digest-worklist.json"
    if not p.exists():
        return None
    return json.loads(p.read_text("utf-8"))


def prose(result):
    """機檢語言層時看的文字：sections 的正文 ＋ so_what。

    **不含 `question`**：那一句本來就是問句，把它算進設問密度等於處罰這個框架
    自己要求的東西。也不含 basis / counter——那兩格是給審的人看的，不是文章。
    """
    parts = [str(s.get("text") or "") for s in (result.get("sections") or [])]
    parts.append(str(result.get("so_what") or ""))
    return "\n\n".join(x for x in parts if x)


def _reject(rules, rule, where, why):
    rules.append({"rule": rule, "where": where, "why": why})


def check_structure(result, out):
    secs = result.get("sections") or []
    if not secs or not str(result.get("question") or "").strip() \
            or not str(result.get("so_what") or "").strip():
        _reject(out, "empty_article", "-", "sections / question / so_what 至少一個是空的")
    seen = set()
    for s in secs:
        sid = str(s.get("id") or "")
        if s.get("layer") not in LAYERS:
            _reject(out, "bad_layer", sid or "?",
                    f"layer={s.get('layer')!r}，不在 {'/'.join(LAYERS)}")
        if sid in seen:
            _reject(out, "duplicate_id", sid, "兩個 section 共用一個 id，support 會指到不確定的東西")
        seen.add(sid)
    for sid in (result.get("support") or []):
        if sid not in seen:
            _reject(out, "dangling_support", str(sid), "support 指到一個不存在的 section")


def check_evidence(result, items, cfg, out):
    """證據層。`items` 是 event_id → 當日 worklist 的那一則。"""
    secs = result.get("sections") or []
    by_id = {str(s.get("id") or ""): s for s in secs}
    counter_min = cfg.get("counter_min_chars", 15)

    referenced = set()
    for s in secs:
        sid = str(s.get("id") or "")
        layer = s.get("layer")
        ev = [str(x) for x in (s.get("evidence") or [])]
        referenced.update(ev)
        for eid in ev:
            if eid not in items:
                _reject(out, "unknown_event", sid,
                        f"引用的事件 {eid} 不在今天的 worklist 裡，讀者查不到、我們也查不到")
        if layer in ("A", "D") and not ev:
            _reject(out, "layer_needs_evidence", sid,
                    f"{layer} 級的意思就是「有證據」，evidence 卻是空的")
        if layer == "B" and not str(s.get("basis") or "").strip():
            _reject(out, "b_without_basis", sid,
                    "B 級是不在 vault 的背景知識，沒有 basis 讀者分不出它是不是編的")
        if layer == "C":
            counter = str(s.get("counter") or "").strip()
            if not counter:
                _reject(out, "c_without_counter", sid,
                        "C 級是推論，反例測試要求至少寫出一個別的解釋")
            elif len(counter) < counter_min:
                _reject(out, "counter_too_thin", sid,
                        f"counter 只有 {len(counter)} 字（門檻 {counter_min}）；"
                        "「也可能不是」不是反例")
        if layer == "D":
            url = str(s.get("source_url") or "").strip()
            urls = {str(r.get("url") or "")
                    for eid in ev for r in ((items.get(eid) or {}).get("evidence") or [])}
            if not url:
                _reject(out, "d_without_source_url", sid,
                        "D 級的意思是「原文有、我們沒取用」，沒有連結讀者補不了")
            elif url not in urls:
                _reject(out, "d_without_source_url", sid,
                        f"source_url {url} 不在它引用的事件證據列裡——"
                        "一條點到別的地方的連結比沒有連結更糟")

    # so_what 的支撐鏈：硬規則是**不能只靠 B＋C 撐**。
    support = [str(x) for x in (result.get("support") or [])]
    if not any((by_id.get(x) or {}).get("layer") == "A" for x in support):
        _reject(out, "so_what_unsupported", "so_what",
                "支撐鏈裡沒有任何 A 級——結論不能只靠背景知識與作者推論撐著")

    # 每一則素材都要有交代（跟 dashboard 的三桶對帳同一個道理）。
    dropped_ids = set()
    for d in (result.get("dropped") or []):
        did = str(d.get("id") or "")
        dropped_ids.add(did)
        if did not in items:
            _reject(out, "unknown_event", f"dropped:{did}",
                    "丟棄了一則不在今天 worklist 裡的事件")
        if not str(d.get("why") or "").strip():
            _reject(out, "dropped_without_reason", f"dropped:{did}",
                    "沒理由的丟棄跟資料不見了沒有區別")
    missing = sorted(set(items) - referenced - dropped_ids)
    if missing:
        _reject(out, "unaccounted_material", "-",
                "這幾則既沒被引用也沒被 dropped：" + "、".join(missing))

    # withheld_without_d：這是 references/evidence-availability.md 欠的那條線。
    # 2026-08-13 的 Grok Bot 那則寫「（證據不足，待補）」，而 https://x.ai/bot
    # 就躺在它自己的證據列裡。把「誠實」變成欄位，不靠寫的人記得。
    for eid in sorted(referenced & set(items)):
        item = items[eid]
        if not ((item.get("availability") or {}).get("needs_source_link")):
            continue
        held = {str(r.get("url") or "") for r in (item.get("evidence") or [])
                if r.get("availability") == WITHHELD}
        ok = any(s.get("layer") == "D" and eid in [str(x) for x in (s.get("evidence") or [])]
                 and str(s.get("source_url") or "") in held for s in secs)
        if not ok:
            _reject(out, "withheld_without_d", eid,
                    "這一則有來源是政策不取用的，文章欠讀者一條 D 級 claim 指向原文："
                    + "、".join(sorted(held)))


def check_language(result, cfg, out):
    text = prose(result)
    n = max(len(text), 1)
    for bad in CLOSED_INFERENCE:
        if bad in text:
            _reject(out, "closed_inference", bad,
                    "封閉式推論：把一個沒跑過反例的斷言講成唯一的答案")
    hits = len(_NOT_A_BUT_B.findall(text))
    if hits > cfg.get("not_a_but_b_max", 1):
        _reject(out, "not_a_but_b_overuse", f"{hits} 次",
                "「不是 A，是 B」一篇一次是強調，多了是口頭禪")
    dash = text.count("——") * 1000.0 / n
    if dash > cfg.get("dash_per_1k_max", 8):
        _reject(out, "dash_density", f"每千字 {dash:.1f} 個",
                "破折號密度過高（AI 腔最穩定的指紋之一）")
    bold = len(_BOLD.findall(text)) * 1000.0 / n
    if bold > cfg.get("bold_per_1k_max", 12):
        _reject(out, "bold_overuse", f"每千字 {bold:.1f} 個",
                "每一句都是重點等於沒有重點")
    q = text.count("？")
    if q > cfg.get("questions_max", 2):
        _reject(out, "question_density", f"{q} 個",
                "設問句過多；問題那一句已經有自己的欄位了")


def check(result, items, cfg):
    """全部退件規則。回一串 dict（空的＝可以寫）。純函式：不讀磁碟、不讀時鐘。"""
    out = []
    check_structure(result, out)
    check_evidence(result, items, cfg, out)
    check_language(result, cfg, out)
    return out


def overwrite_verdict(path, force=False):
    """要不要讓這一天的稿被寫回。回 None＝可以寫；回字串＝拒絕的理由。

    跟 `pulse-enrich-apply.overwrite_verdict()` 同一道守衛，理由也一樣，但方向相反：
    那一支守的是「已經潤過的不要再潤」，這一支守的是**審過的稿不可以被隔天的班蓋掉**。
    Digest 的生成語意跟 Tracks / Actors 相反——那兩種每次重新生成，這一種生成一次
    就定稿（references/digest-framework.md §五）。

    逃生口是 `--force`，而且 **runbook 的自動化那一節不准出現它**（selftest 機械檢查）：
    寫進無人值守的那一端，等於把這道守衛關掉，而那一端最沒有能力判斷「這次覆寫是對的嗎」。
    """
    if not path.exists():
        return None
    if force:
        return None
    return (f"{path.name} 已經存在。digest 生成一次就定稿，"
            "隔天的班蓋掉一份審過的稿，沒有人會發現")


def render(result, mode, cleaned):
    """組出 Digests/<date>.md 的 frontmatter 與 body。

    文章本身讀起來要乾淨，所以層次標記不寫進正文，改成文末一段〈這篇的層次〉——
    那一段是給審的人看的（`pulse-digest-gate.py` 要的三格在 frontmatter）。
    """
    fm = {
        "kind": "digest",
        "date": result["date"],
        "title": result.get("title") or result["date"],
        "mode": mode,
        # 這一期用掉了哪幾則事件。**`pulse-digest-prep.load_featured()` 讀這一格**，
        # 空日規則靠它排除用過的素材。2026-08-16 之前這一格沒有人寫，於是
        # `already_featured` 恆為空集合，每一個空日都會挑到同一則（實測：NVIDIA Vera，
        # 41 天，而它等的那個訊號永遠不會被滿足）。近 30 天有 47% 是空日。
        # 規格 references/digest-observability.md〈三〉。
        "sources": sorted({e for sec in result["sections"]
                           for e in (sec.get("evidence") or [])}),
        "status": "draft",
        # 人審三格。三個都還是 null 就不 render，見 references/digest-apply.md〈四〉。
        "review_question": None,
        "review_background": None,
        "review_counter": None,
        "generator": "pulse-digest-apply.py",
        "generated_at": clock.utc_stamp(),
    }
    lines = [f"# {fm['title']}", ""]
    if mode == "retrospective":
        # 空日的稿必須在開頭明說（digest-framework §四）。**由這一支寫，不靠寫的人記得**
        # ——「今天沒事」跟「今天沒跑」長得一模一樣，只有這句話分得出來。
        lines += ["> 今天沒有新上線的事件，這一篇是回頭看。", ""]
    lines += [f"> 今天的問題：{result['question']}", ""]
    for s in result["sections"]:
        lines += [s["text"], ""]
    lines += ["## 所以呢", "", result["so_what"], ""]
    lines += ["## 這篇的層次", ""]
    for s in result["sections"]:
        bits = [f"- `{s['id']}` **{s['layer']}**"]
        if s.get("evidence"):
            bits.append("證據：" + "、".join(f"[[Events/{e}|{e}]]" for e in s["evidence"]))
        if s.get("basis"):
            bits.append("背景出處：" + s["basis"])
        if s.get("counter"):
            bits.append("別的解釋：" + s["counter"])
        if s.get("source_url"):
            bits.append("原文：" + s["source_url"])
        lines.append("　".join(bits))
    lines.append("")
    if result.get("dropped"):
        lines += ["## 今天沒用的素材", ""]
        for d in result["dropped"]:
            lines.append(f"- `{d['id']}` — {d['why']}")
        lines.append("")
    if cleaned:
        lines += ["## 機械清理", "",
                  "voice_clean 動過的地方（中國用語與半形標點，零容忍無歧義的那些）：", ""]
        for where, ch in cleaned:
            detail = "、".join(f"{kind} {a}→{b}" for kind, a, b in ch)
            lines.append(f"- {where}：{detail}")
        lines.append("")
    return fm, "\n".join(lines)


def clean_result(result):
    """把 voice_clean 套到會進文章的每一格，回 [(哪一格, 改了幾處)]。

    洗了什麼要印出來，不要靜靜改掉——這是 `pulse-enrich-apply.py` 已經在做的事，
    這裡照做。清理在**機檢之後**：先退件再洗，不然語言層檢查的是洗過的文字，
    而寫的人拿回的退件理由會對不上他自己寫的東西。
    """
    changed = []
    for s in result.get("sections") or []:
        s["text"], ch = voice_clean.clean(s.get("text") or "")
        if ch:
            changed.append((f"section {s.get('id')}", ch))
    for key in ("so_what", "question"):
        result[key], ch = voice_clean.clean(result.get(key) or "")
        if ch:
            changed.append((key, ch))
    return changed


def write_trace(vault, dry_run, **fields):
    """每次執行都留一份紀錄。**包含退件與拒寫那幾條路。**

    `Digests/<date>.md` 只有成功才存在，所以「今晚沒素材」跟「今晚有素材但沒寫」
    在 git 裡長得一模一樣——一個沒有辦法帶理由的表達方式，違反紅線 8。
    這一份就是那個理由的落點：它證明 apply 被呼叫過、結果是什麼。

    **它不能證明「該跑而沒跑」**——那要靠 pulse-monitor 比對天數。兩件事分開量，
    因為要人做的動作不同：退件去看理由改稿，沒跑去看排程。
    規格 references/digest-observability.md〈一〉。
    """
    if dry_run:
        return
    p = vault / "_probe" / "digest-apply-last.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": clock.utc_stamp()}
    rec.update(fields)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="覆寫已存在的 digest。不要寫進 runbook 的自動化那一節。")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    result = json.loads(Path(args.infile).read_text("utf-8"))
    work = load_worklist(vault)
    if work is None:
        print("[fatal] 找不到 _probe/digest-worklist.json，先跑 pulse-digest-prep.py", file=sys.stderr)
        # 這一條沒有 worklist 可以留日期，但「有人叫過 apply 而它連清單都找不到」
        # 本身就是要被看見的事。
        write_trace(vault, args.dry_run, date=str(result.get("date") or ""),
                    outcome="no_worklist", material=0, mode=None, problems=[])
        return 2
    if str(result.get("date") or "") != str(work.get("date") or ""):
        print(f"[fatal] 稿子寫的是 {result.get('date')}，而 worklist 是 {work.get('date')}"
              "——素材對不上，機檢會全部誤判", file=sys.stderr)
        write_trace(vault, args.dry_run, date=str(work.get("date") or ""),
                    outcome="date_mismatch", material=len(work.get("items") or []),
                    mode=work.get("mode"), problems=[],
                    draft_date=str(result.get("date") or ""))
        return 2

    gate = yaml.safe_load((vault / "_config" / "gate.yaml").read_text("utf-8")) or {}
    cfg = gate.get("digest") or {}
    items = {str(e["id"]): e for e in (work.get("items") or []) if e.get("id")}

    # **先洗再檢。** 反過來的話，半形問號可以繞過設問密度：`?` 不是 `？`，
    # 而 voice_clean 會把緊鄰 CJK 的半形標點轉全形——先檢的版本看到的是
    # 一篇沒有問號的文章，洗完寫進檔案的卻有三個。判準要看讀者看到的那一版。
    cleaned = clean_result(result)
    problems = check(result, items, cfg)
    if problems:
        print(f"pulse-digest-apply  退件 {len(problems)} 條  未寫檔", file=sys.stderr)
        for p in problems:
            print(f"  [{p['rule']}] {p['where']}：{p['why']}", file=sys.stderr)
        write_trace(vault, args.dry_run, date=result["date"], outcome="rejected",
                    material=len(items), mode=work.get("mode"), problems=problems)
        return 1

    out = vault / "Digests" / f"{result['date']}.md"
    refusal = overwrite_verdict(out, args.force)
    if refusal:
        print(f"pulse-digest-apply  [拒寫] {refusal}", file=sys.stderr)
        write_trace(vault, args.dry_run, date=result["date"], outcome="refused",
                    material=len(items), mode=work.get("mode"),
                    problems=[{"rule": "already_exists", "where": out.name, "why": refusal}])
        return 1

    fm, body = render(result, work.get("mode") or "normal", cleaned)
    if not args.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"---\n{dump_frontmatter(fm)}\n---\n\n{body}", encoding="utf-8")

    write_trace(vault, args.dry_run, date=result["date"], outcome="written",
                material=len(items), mode=work.get("mode"), problems=[],
                sections=len(result["sections"]))
    print(f"pulse-digest-apply  {result['date']}  機檢全過  "
          f"段落={len(result['sections'])}  引用={len({e for s in result['sections'] for e in (s.get('evidence') or [])})} 則  "
          f"dropped={len(result.get('dropped') or [])} 則"
          f"{'  [dry-run]' if args.dry_run else '  → ' + str(out.relative_to(vault))}")
    if cleaned:
        print("  ── voice_clean 動過 ──")
        for where, ch in cleaned:
            print(f"    {where}: " + "、".join(f"{kind} {a}→{b}" for kind, a, b in ch))
    print("  status: draft — 三格人審填完才會 render（pulse-digest-gate.py）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
