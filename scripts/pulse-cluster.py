#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pulse-cluster.py — Sprint 3b：signals → Event（純規則，零 LLM）。

讀 _probe/<day>/signals-scored.jsonl（3a 產）+ _config/{sources,entities,gate}.yaml，
依「同 fingerprint+facet+時間窗 / 或標題相似度 ≥0.46」把 signals 聚成 Event，
綁定證據、算 confidence/heat/independent_sources/primary_evidence，
寫 Events/<id>.md（六層標題 + 待編輯佔位；prose 留給 3c enrich 填）。
跨日：會讀既有 Events/*.md，新 signal 可 attach 到昨天的 Event 並重評分。

紅線：獨立數用 distinct media_group（框架規則第 5 條），比 agent-pulse 原碼嚴。
用法：
  VAULT_DIR=/path/to/AI-Pulse python scripts/pulse-cluster.py [--day YYYY-MM-DD] [--dry-run]
依賴：PyYAML。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cluster, scoring  # noqa: E402
from lib.notes import PLACEHOLDER  # noqa: E402  單一來源，見 lib/notes.py
from lib.quality import authority_score_from_tier, parse_dt  # noqa: E402

import yaml  # noqa: E402


def load_sources(cfg):
    raw = yaml.safe_load((cfg / "sources.yaml").read_text("utf-8"))
    out = {}
    for key in ("official_sources", "kol_sources", "aggregator_sources"):
        for s in (raw.get(key) or []):
            if isinstance(s, dict) and s.get("id"):
                out[s["id"]] = s
    return out


def load_entities(cfg):
    """id → (canonical, term_type)。用於 Event 的 company 初判。"""
    p = cfg / "entities.yaml"
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text("utf-8")) or {}
    out = {}
    for key in ("companies", "product_lines", "products", "technologies", "policy"):
        for e in (raw.get(key) or []):
            if isinstance(e, dict) and e.get("id"):
                out[e["id"]] = (e.get("canonical") or e["id"], e.get("term_type"), e.get("parent"))
    return out


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(title):
    s = _SLUG_STRIP.sub("-", (title or "").lower()).strip("-")
    return s[:60] or "event"


def infer_company(entity_hits, entities):
    # 1) 直接命中 company 型別
    for hid in entity_hits or []:
        canon, ttype, _ = entities.get(hid, (None, None, None))
        if ttype == "company":
            return canon
    # 2) 命中 product_line/product → 往上解析到 parent 公司（例：gemini → Google DeepMind）
    for hid in entity_hits or []:
        canon, ttype, parent = entities.get(hid, (None, None, None))
        if parent:
            pcanon, pttype, _ = entities.get(parent, (None, None, None))
            if pttype == "company":
                return pcanon
    return "industry"  # 泛稱 → 會觸發 generic_entity blocker，待 enrich 修正


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[3:end]) or {}
    body = text[end + 4:]
    return fm, body


class Event:
    def __init__(self, eid, slug, title, happened_at, fingerprint=None, facet=None):
        self.id = eid
        self.slug = slug
        self.title = title
        self.happened_at = happened_at
        self.fingerprint = fingerprint
        self.facet = facet
        self.evidence = []  # list of {source_id, url, title, relevance}
        self.company = "industry"
        self.keywords = []
        self.dirty = True  # 需要寫檔
        self.scores = None
        self.path = None
        self.enriched = False   # 已 enrich（3c）→ 重寫時只更新 frontmatter 分數，不動 prose body
        self.orig_body = None   # reload 時保存的原 body（enriched 時用來保留潤好的 prose）
        self.fm = None          # reload 時保存的完整 frontmatter

    def add_evidence(self, source_id, url, title, relevance):
        if any(e["source_id"] == source_id and e["url"] == url for e in self.evidence):
            return
        self.evidence.append({"source_id": source_id, "url": url, "title": title, "relevance": relevance})
        self.dirty = True


def rescore(ev, sources, ref_now):
    authority_scores, tiers, media_groups, primary = [], [], set(), 0
    for e in ev.evidence:
        src = sources.get(e["source_id"], {})
        tier = src.get("tier")
        try:
            tier = int(tier)
        except (TypeError, ValueError):
            tier = 3
        authority_scores.append(authority_score_from_tier(tier))
        tiers.append(tier)
        mg = src.get("media_group") or e["source_id"]
        media_groups.add(mg)
        role = src.get("role")
        scat = src.get("source_category")
        if tier == 1 and role != "aggregator" and scat != "aggregator":
            primary += 1
    independent = len(media_groups)  # 紅線第 5 條：distinct media_group
    happened = parse_dt(ev.happened_at)
    age_hours = max(0.0, (ref_now - happened).total_seconds() / 3600.0) if (happened and ref_now) else 0.0
    ev.scores = scoring.score_event(authority_scores, primary, independent, metrics=[], age_hours=age_hours)
    ev.scores["tier_evidence"] = min(tiers) if tiers else None
    ev.scores["independent_sources"] = independent
    ev.scores["primary_evidence"] = primary


def event_markdown(ev):
    s = ev.scores
    hd = parse_dt(ev.happened_at)
    date_str = hd.date().isoformat() if hd else (ev.happened_at[:10] if ev.happened_at else None)
    fm = {
        "id": ev.id,
        "slug": ev.slug,
        "title": ev.title,
        "date": date_str,
        "happened_at": hd.isoformat() if hd else ev.happened_at,
        "status": "review",
        "category": None,          # enrich 填
        "company": ev.company,
        "track": None,             # 敘事 Track，enrich 填
        "fingerprint": ev.fingerprint,
        "facet": ev.facet,
        "tier_evidence": s["tier_evidence"],
        "independent_sources": s["independent_sources"],
        "primary_evidence": s["primary_evidence"],
        "confidence": s["confidence"],
        "heat": s["heat"],
        "impact": s["impact"],
        "value": s["value"],
        "score_factors": s["factors"],
        "blockers": [],            # 3d gate 填
        "warnings": [],
        "keywords": ev.keywords,
        "next_signal": "",
        "evidence": [{"source_id": e["source_id"], "url": e["url"], "relevance": e["relevance"]} for e in ev.evidence],
        "tags": ["event", "review"],
    }
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
    ev_lines = "\n".join(
        f"- [[Sources/{e['source_id']}|{e['source_id']}]] — {e['title']}（{e['url']}）"
        for e in ev.evidence
    )
    body = f"""
## 事實
{PLACEHOLDER}：一句話講清楚發生了什麼（enrich 依證據填、過 speak-human-tw）。

## 證據
{ev_lines}

## 脈絡
{PLACEHOLDER}：這件事放在什麼背景下才看得懂。

## 影響
{PLACEHOLDER}：對能力 / 成本 / 競爭結構的影響。

## 判斷
{PLACEHOLDER}（規則標註）：{'單一獨立來源 → 待證實' if ev.scores['independent_sources'] < 2 else '多來源佐證'}。

## 下一個訊號
{PLACEHOLDER}：接下來要觀察哪個可驗證訊號。
"""
    return f"---\n{front}\n---\n{body}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(os.environ["VAULT_DIR"])
    cfg = vault / "_config"
    probe = vault / "_probe"
    events_dir = vault / "Events"

    # 選日：預設用 _probe 下最新有 signals-scored 的那天
    if args.day:
        day = args.day
    else:
        days = sorted(p.name for p in probe.iterdir()
                      if p.is_dir() and (p / "signals-scored.jsonl").exists()) if probe.exists() else []
        day = days[-1] if days else None
    if not day:
        print("[fatal] 找不到 signals-scored.jsonl（先跑 pulse-score.py）", file=sys.stderr)
        return 2
    scored_path = probe / day / "signals-scored.jsonl"
    if not scored_path.exists():
        print(f"[fatal] 無 {scored_path}", file=sys.stderr)
        return 2

    sources = load_sources(cfg)
    entities = load_entities(cfg)

    signals = [json.loads(x) for x in scored_path.read_text("utf-8").splitlines() if x.strip()]
    ref_now = max([parse_dt(s.get("first_observed_at")) for s in signals if parse_dt(s.get("first_observed_at"))],
                  default=datetime.now(timezone.utc))

    # 讀既有 Events（跨日 attach）
    events = []
    existing_by_id = {}
    if events_dir.exists():
        for p in sorted(events_dir.glob("*.md")):
            fm, body = parse_frontmatter(p.read_text("utf-8"))
            if not fm.get("id"):
                continue
            happened = fm.get("happened_at") or ((str(fm.get("date")) + "T00:00:00Z") if fm.get("date") else "")
            ev = Event(fm["id"], fm.get("slug") or p.stem, fm.get("title") or p.stem,
                       happened, fm.get("fingerprint"), fm.get("facet"))
            ev.company = fm.get("company", "industry")
            ev.keywords = fm.get("keywords", [])
            ev.enriched = bool(fm.get("enriched"))   # 3c 已潤 → 重寫時保 prose
            ev.orig_body = body
            ev.fm = fm
            for e in (fm.get("evidence") or []):
                ev.evidence.append({"source_id": e.get("source_id"), "url": e.get("url"),
                                    "title": e.get("url"), "relevance": e.get("relevance", 0)})
            ev.dirty = False
            ev.path = p
            events.append(ev)
            existing_by_id[ev.id] = ev

    # 依 eventability 排序（高的先，能開新 Event）
    signals = [s for s in signals if (s.get("title") or "").strip()]
    signals.sort(key=lambda s: (eventability(s, sources), s.get("published") or ""), reverse=True)

    created = attached = deferred = 0
    for sig in signals:
        title = sig["title"]
        published = sig.get("published") or sig.get("first_observed_at") or ""
        ev = next((c for c in events if cluster.belongs_to_event(
            title, published, c.title, c.happened_at)), None)
        if ev is None:
            score = eventability(sig, sources)
            if score < 70:
                deferred += 1
                continue
            fp = sig.get("fingerprint")
            # id 用「事件發生日 + (fingerprint|facet) 雜湊」→ 跨日穩定、同鍵不同 facet 不撞
            hkey = f"{fp or title}|{sig.get('facet')}"
            h = hashlib.sha1(hkey.encode("utf-8")).hexdigest()[:6]
            hd = parse_dt(published)
            hdate = hd.date().isoformat() if hd else day
            eid = f"evt-{hdate}-{h}"
            if eid in existing_by_id:  # 同鍵同日 → 視為既有
                ev = existing_by_id[eid]
            else:
                slug = f"{slugify(title)}-{h[:4]}"
                ev = Event(eid, slug, title, published, fp, sig.get("facet"))
                ev.company = infer_company(sig.get("entity_hits"), entities)
                # 曾經是 list(cluster.title_tokens(title))[:8]，那是 set → 順序隨機，
                # 同一個標題每跑一次就換一組關鍵詞。理由與實測見 lib/cluster.py。
                ev.keywords = cluster.keyword_tokens(title, 8)
                events.append(ev)
                existing_by_id[eid] = ev
                created += 1
        else:
            attached += 1
        rel = int(round(cluster.title_similarity(title, ev.title) * 100))
        ev.add_evidence(sig["source_id"], sig.get("url", ""), title, rel)

    # rescore 所有動到的 Event
    changed = [e for e in events if e.dirty]
    for ev in changed:
        rescore(ev, sources, ref_now)

    # 摘要
    conf = [e.scores["confidence"] for e in changed if e.scores]
    print(f"pulse-cluster  day={day}  signals={len(signals)}")
    print(f"  created={created}  attached={attached}  deferred(eventability<70)={deferred}")
    print(f"  events changed={len(changed)}  (total in vault={len(events)})")
    if conf:
        import statistics
        print(f"  confidence: min={min(conf)} median={int(statistics.median(conf))} max={max(conf)}")
    multi = [e for e in changed if e.scores and e.scores['independent_sources'] >= 2]
    print(f"  ≥2 獨立來源的 Event: {len(multi)}/{len(changed)}")

    if args.dry_run:
        print("  [dry-run] 未寫檔")
        return 0
    events_dir.mkdir(parents=True, exist_ok=True)
    for ev in changed:
        out = ev.path or (events_dir / f"{ev.id}.md")
        if ev.enriched and ev.orig_body is not None and ev.fm is not None:
            out.write_text(rescored_enriched_markdown(ev), encoding="utf-8")  # 保 prose，只更新分數
        else:
            out.write_text(event_markdown(ev), encoding="utf-8")
    print(f"  → 寫入 {len(changed)} 個 Events/*.md")
    return 0


def rescored_enriched_markdown(ev):
    """已 enrich 的 Event 拿到新證據時：只更新分數與 evidence frontmatter，保留潤好的 prose body。"""
    s = ev.scores
    fm = dict(ev.fm)
    fm["tier_evidence"] = s["tier_evidence"]
    fm["independent_sources"] = s["independent_sources"]
    fm["primary_evidence"] = s["primary_evidence"]
    fm["confidence"] = s["confidence"]
    fm["heat"] = s["heat"]
    fm["impact"] = s["impact"]
    fm["value"] = s["value"]
    fm["score_factors"] = s["factors"]
    fm["evidence"] = [{"source_id": e["source_id"], "url": e["url"], "relevance": e["relevance"]} for e in ev.evidence]
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
    body = ev.orig_body if ev.orig_body.startswith("\n") else "\n" + ev.orig_body
    return f"---\n{front}\n---{body}"


def eventability(sig, sources):
    return cluster.eventability_score(sig, sources.get(sig.get("source_id")))


if __name__ == "__main__":
    sys.exit(main())
