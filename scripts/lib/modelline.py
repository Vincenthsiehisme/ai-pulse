#!/usr/bin/env python3
"""modelline.py — 模型演變時間線的純函式層。規格：references/model-timeline.md。

這個模組**只做三件事**，而且三件都是對字串的字面判斷、沒有網路、沒有 LLM：

  lifecycle_of(text)          條目在講哪一種版本異動（封閉集，逐字判）
  parse_entry_date(...)       條目日期 →（ISO、精度、年份哪來的）
  models_in(text, table)      條目提到哪些產品線（比對 _config/entities.yaml）

刻意**不做**的那一件：**HTML → 條目的切分。**
那一步要等 `verify-article-metadata.py --preset release-notes` 在 CI 上
帶回真的 bytes 之後才寫。對著想像的標記寫解析器，寫出來的東西會通過我自己編的
測試、然後在真頁面上失敗——那是把「我測過了」變成一個比事實寬鬆的說法，
而那正是這整層要修的病（規格第 5 節，步 3 刻意不先寫）。

紅線 1（熱迴圈 0 LLM）在這裡不是限制，是**已經夠用**的觀察：四家 changelog
用的是同一組動詞。「需要 LLM」與「我還沒去讀那些字」是兩件事。
"""
from __future__ import annotations

import html as _html
import re
from datetime import date

# ────────────────────────────────────────────────────── lifecycle（封閉集）
GA = "ga"
PREVIEW = "preview"
SHUTDOWN = "shutdown"
DEPRECATED = "deprecated"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"
LIFECYCLES = (GA, PREVIEW, SHUTDOWN, DEPRECATED, AMBIGUOUS, UNKNOWN)

# 動詞表。2026-07-27 從四家 changelog 的實際條目抄下來的，不是想像的清單。
LIFECYCLE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (SHUTDOWN, ("shut down", "shutdown", "retired", "turned down")),
    (DEPRECATED, ("deprecated", "deprecation")),
    # 「is available」曾經在這裡，拿真頁面一跑就看到它把
    # 「… is available as a research preview」判成 ga＋preview 兩票＝ambiguous。
    # 它不是發布動詞，是狀態描述——太鬆的針腳會把真答案洗成「不確定」。
    (GA, ("released as ga", "generally available", "general availability",
          "as ga versions", "ga version", "we've launched", "we have launched")),
    # 裸字 `beta` / `preview` / `experimental` 曾經在這裡。真頁面實測：
    # 42 條 ambiguous 裡 **34 條是被裸字 `beta` 打中的**，包括
    #   「… No beta header is required.」          ← 明說**不是** beta
    #   「We've retired the 1M token context window beta ( … )」 ← 只有一個宣稱
    # 而 `ambiguous` 的定義是「這條有兩種以上的宣稱」、規格說它是「要人看的那一格」。
    # 人工佇列比它命名的事實大六倍，桶子就是這樣變成靜音的。
    # 拿掉「is available」是因為它太鬆，然後在隔壁留了三個更鬆的——同一個錯，
    # 同一個 tuple，兩行之隔。改成片語錨定：beta/preview 要真的在講狀態。
    (PREVIEW, ("research preview", "public preview", "private preview",
               "in preview", "as a preview", "preview release",
               "in beta", "public beta", "private beta", "open beta",
               "as a beta", "beta release", "experimental release")),
)


def lifecycle_of(text: str) -> str:
    """→ LIFECYCLES 之一。純字面比對，比不到就 unknown、比到兩種以上就 ambiguous。

    **第一版用優先序解重疊，那是錯的。** 當時的理由寫著「下線類的宣稱比上線類
    的重」——聽起來合理，實際上是拿一個排序去代替一個我們沒有的答案。
    一條同時寫著「launched X」與「deprecated Y」的條目，真相是**它講了兩件事**，
    不是「它講的是下線」。挑一個寫進表裡，表看起來完整，而那一格是編的。

    `ambiguous` 因此是一個答案，不是一個失敗：它說「這條有兩種以上的宣稱，
    我們沒有辦法只用字面決定是哪一種」。它跟 unknown 分開計數
    （規格第 4 節），因為兩者要人做的事不一樣——unknown 要補動詞表，
    ambiguous 要更細的切分或人工判讀。

    這也順帶把優先序整個拿掉了：既然重疊會誠實地說出來，
    LIFECYCLE_MARKERS 的順序就不再攜帶任何判斷。
    """
    low = (text or "").lower()
    hit = []
    for state, needles in LIFECYCLE_MARKERS:
        if any(n in low for n in needles):
            hit.append(state)
    if not hit:
        return UNKNOWN
    return hit[0] if len(hit) == 1 else AMBIGUOUS


# ─────────────────────────────────────────────────────────── 日期（含精度）
MONTHS = {m: i + 1 for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"))}

# 三種形狀，全部在 2026-07-27 的實測裡出現過：
#   "July 24, 2026" / "Jul 22, 2026"   Anthropic、OpenAI     → 日精度、年份明示
#   "June 2026"                        章節標題              → 月精度、年份明示
#   "July 23"                          docs.x.ai            → 日精度、**年份缺**
# `(?:st|nd|rd|th)?` 同樣是實測撞出來的：Anthropic 2024 年那批寫的是
# 「July 9th, 2024」。少了它，那些條目會落到 _D_MD、沒有 year_hint、回 None，
# 而 derived_year_rate 會從 0 跳到 0.49——**指標先叫，才發現解析器有洞。**
_ORD = r"(?:st|nd|rd|th)?"
_D_YMD = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})" + _ORD + r"\s*,?\s+(20\d{2})\b", re.I)
_D_YM = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(20\d{2})\b",
    re.I)
_D_MD = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})" + _ORD + r"\b", re.I)

# 封閉集，跟 coverage 三態同一個做法。
PRECISION_DAY, PRECISION_MONTH, PRECISION_NONE = "day", "month", "none"
YEAR_EXPLICIT, YEAR_SECTION, YEAR_NONE = "explicit", "section", "none"


def parse_entry_date(text: str, year_hint: int | None = None
                     ) -> tuple[str | None, str, str]:
    """→ (ISO 日期或 None, 精度, 年份哪來的)。

    `year_hint` 是呼叫端從章節標題帶進來的年份。它**不是預設值**——
    沒有 hint 時，缺年份的條目回 `(None, none, none)`，不會拿今年去補。

    為什麼不拿今年補：`docs.x.ai` 的條目最早到 2024-11，整頁都印
    「July 23」這種格式。用今年去補，2024 與 2025 的條目會全部堆到 2026，
    而時間線看起來完全正常——每個日期都是合法日期，只有它們跟事實的關係是錯的。
    （M78/M81 那一課：要能說出它是拿什麼跟什麼比的。）
    """
    s = text or ""

    m = _D_YMD.search(s)
    if m:
        mo, day, yr = MONTHS[m.group(1)[:3].lower()], int(m.group(2)), int(m.group(3))
        iso = _safe_iso(yr, mo, day)
        return (iso, PRECISION_DAY, YEAR_EXPLICIT) if iso else (None, PRECISION_NONE, YEAR_NONE)

    m = _D_YM.search(s)
    if m:
        mo, yr = MONTHS[m.group(1)[:3].lower()], int(m.group(2))
        return f"{yr:04d}-{mo:02d}", PRECISION_MONTH, YEAR_EXPLICIT

    m = _D_MD.search(s)
    if m:
        if year_hint is None:
            # 有月有日、就是沒有年。這不是解析失敗，是**來源真的沒寫**。
            return None, PRECISION_NONE, YEAR_NONE
        mo, day = MONTHS[m.group(1)[:3].lower()], int(m.group(2))
        iso = _safe_iso(int(year_hint), mo, day)
        return (iso, PRECISION_DAY, YEAR_SECTION) if iso else (None, PRECISION_NONE, YEAR_NONE)

    return None, PRECISION_NONE, YEAR_NONE


def _safe_iso(year: int, month: int, day: int) -> str | None:
    """2 月 30 日這種東西存在於自由文字裡。回 None 而不是丟例外——
    一則條目日期壞掉不該讓整頁解析中止。"""
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────── 產品線比對
# 版本號後綴。changelog 寫的是 `claude-opus-5`、`gemini-3.5-flash` 這種 id，
# 而 entities.yaml 的 canonical 是「Claude」「Gemini」。這裡只負責把
# **原文的 id 字串**撈出來，不做正規化——正規化就是在造一個新的代理值。
_MODEL_ID = re.compile(
    r"\b((?:claude|gpt|gemini|grok|llama|gemma|sora|veo|muse)"
    r"[a-z0-9]*(?:[-.][a-z0-9]+)+)\b", re.I)

# 2026-07-27 拿真頁面實測時，第一版把 `claude.com` 與 `claude.ai` 當成 model id
# 撈了進來——`.com` 完全符合 `[-.][a-z0-9]+`。**網域不是模型。**
# 兩條字面規則擋掉它，兩條都不是啟發式：
#   1. 最後一段是已知 TLD → 不是 model id
#   2. 整串**沒有任何數字** → 不是 model id（廠商 id 一律帶版本號）
# 規則 2 會漏掉 `grok-build` 這種沒有版本號的產品名。漏掉是刻意的：
# 漏一列比在時間線上多一列假的好（跟 lifecycle 優先序同一個取捨）。
_TLDS = frozenset(("com", "ai", "org", "net", "io", "dev", "co", "app",
                   "google", "cloud", "js", "py", "md", "html", "json"))


def model_ids_in(text: str) -> list[str]:
    """→ 條目裡出現的廠商 model id 原文，去重、保持出現順序。

    刻意回**原文**不回正規化後的字串：`claude-opus-4-5` 與 `claude-opus-4.5`
    在廠商那裡可能是兩個東西，也可能是同一個。我們不知道，所以不猜。
    """
    seen, out = set(), []
    for m in _MODEL_ID.finditer(text or ""):
        v = m.group(1)
        low = v.lower()
        if re.split(r"[-.]", low)[-1] in _TLDS:
            continue
        if not any(c.isdigit() for c in low):
            continue
        if low not in seen:
            seen.add(low)
            out.append(v)
    return out


# 「這條看起來在講某個版本」——用來當 unmatched_model_rate 的**分母**。
# 沒有這一步的話，分母會變成「全部條目」，而 changelog 裡大半條目本來就
# 不在講模型（實測 Anthropic 那頁 79% 是功能更新）。那樣算出來的
# 「對不上字典的比率」高得嚇人，但它量的是「有多少條不是在講模型」——
# 又一個比事實寬鬆的代理指標，而且是我自己在第一版寫進去的。
# **不寫死廠商名單。** 第一版寫死九個 token，而 `_config/entities.yaml` 有
# 二十三條產品線——於是 `Titan 3 … in public preview`、`DeepSeek-V4 is now
# generally available`、`Kimi K3 released as GA` 全都不算「在講版本」，
# 不會進分母。而這個比率存在的理由，規格寫得很清楚：
# 「高＝新產品線出現了而字典沒補」。
# **一條全新的產品線——正是它要偵測的那件事——永遠不會讓它動。**
# 平常的日子裡兩者一致，正好在有事的那天分岔。這隻病的教科書形狀。
_FALLBACK_TOKENS = ("claude", "gpt", "gemini", "grok", "llama", "gemma")


def versionish_re(product_lines=()) -> "re.Pattern":
    """→ 用 entities.yaml 的 canonical/alias 現場組出來的 pattern。

    給空清單時退回一個**只涵蓋六家**的名單，而且退回這件事是刻意可見的：
    呼叫端沒給字典，這個比率就只在那六家上有意義。
    """
    terms = []
    for line in product_lines or []:
        for t in [line.get("canonical"), *(line.get("aliases") or [])]:
            if t:
                terms.append(re.escape(str(t)))
    if not terms:
        terms = [re.escape(t) for t in _FALLBACK_TOKENS]
    terms.sort(key=len, reverse=True)
    # 詞尾**不加** `\b`：entities.yaml 的 canonical 有 `DeepSeek-V`，
    # 而原文寫的是 `DeepSeek-V4`——加了 `\b` 就永遠對不上自己的字典。
    # 少了詞尾邊界的代價很小，因為後面本來就要求 40 字內出現數字。
    return re.compile(r"\b(?:" + "|".join(terms) + r")[^.;]{0,40}?\d", re.I)


_VERSIONISH_FALLBACK = versionish_re()


def mentions_version(text: str, product_lines=()) -> bool:
    """這條看起來在講某個**我們字典裡有的**產品線的版本。

    **這個限制不可以被忘記，所以寫在這裡而不是註解裡**：分母是字典綁定的。
    一條全新的產品線（`Introducing Titan 3, in public preview`）字典裡沒有，
    於是連分母都進不去，`unmatched_model_rate` 一動也不動。

    也就是說這個比率能回答的是**「已知產品線的新版本有沒有被接住」**，
    不是「有沒有全新的產品線出現」。後者是 `lib/dictgaps.py` 與
    `unknown_entity` 那一層的工作，兩者不可互相冒充。
    規格第 4 節的敘述已依此修正。
    """
    rx = versionish_re(product_lines) if product_lines else _VERSIONISH_FALLBACK
    return bool(rx.search(text or ""))


# ─────────────────────────────────────────── 版本衍生（_config 已寫、沒人實作）
# `_config/entities.yaml` 第 274-280 行把規則寫得很完整：
#   「標題/摘要命中 canonical 或 alias，且其後接上符合 version_pattern 的字串
#     → 產生衍生實體 id：<line_id>@<正規化版本號>」
# `_config/gate.yaml` 的 `version_derivation` 也寫著 `enabled: true`，
# 旁邊註解自己承認「⚠ 這個 true 沒有開啟任何東西」（BACKLOG `gate-未接線`）。
#
# 這裡實作的是**那條已經寫下來的規則**，消費者是時間線這一層。
# **不宣稱 `gate-未接線` 因此被關掉**——那條講的是聚類主鍵，是另一個消費者，
# 而「同一條規則多了一個實作」跟「那個消費者接上了」是兩件事。
# （把後者說成前者，就是這個 repo 一直在抓的那隻病。）
_SLUG_STRIP_V = re.compile(r"^v(?=\d)", re.I)


def _slugify(version: str, rules) -> str:
    s = version.strip()
    if "lowercase" in rules:
        s = s.lower()
    if "space_to_hyphen" in rules:
        s = re.sub(r"\s+", "-", s)
    if "strip_leading_v" in rules:
        s = _SLUG_STRIP_V.sub("", s)
    return s.strip("-")


def derive_versions(text: str, product_lines, slug_rules=(
        "lowercase", "space_to_hyphen", "strip_leading_v")) -> list[str]:
    """→ 依 entities.yaml 的規則衍生出的實體 id，如 `claude@opus-5`。去重、保序。

    只處理有 `version_pattern` 的產品線。沒有 pattern 的（ChatGPT、Codex…）
    本來就不是版本化的東西，硬套會生出假實體。
    """
    out, seen = [], set()
    for line in product_lines or []:
        pat = line.get("version_pattern")
        if not pat:
            continue
        terms = [line.get("canonical"), *(line.get("aliases") or [])]
        for term in [t for t in terms if t]:
            # `(?:…)` 包住設定裡的 pattern：現有的都沒有頂層 `|`，但只要有人
            # 加一個，`AB|C` 會變成「A 接 B，或者只要出現 C」——term 不再是必要條件。
            # `\b` 在前：沒有它，`claude-3-7-sonnet-20250219` 這串**廠商自己的
            # model id** 會被當成「Claude」後面接版本，衍生出 `claude@3`——
            # 一個不同世代的假實體，而 entities.yaml 說衍生實體是聚類主鍵。
            rx = re.compile(r"\b" + re.escape(str(term)) + r"(?:" + pat + r")", re.I)
            for m in rx.finditer(text or ""):
                version = " ".join(g for g in m.groups() if g).strip()
                if not version:
                    continue
                # 版本必須含數字。少了這一條，真設定跑出來的有
                # `command@a`（pattern 字面允許單一字母）這種東西。
                if not any(c.isdigit() for c in version):
                    continue
                eid = f"{line['id']}@{_slugify(version, slug_rules)}"
                if eid not in seen:
                    seen.add(eid)
                    out.append(eid)
    # `claude@3` 與 `claude@opus-3.7` 同時出現時，前者是從後者所在的那串
    # model id 裡切出來的碎片。**同一條文字裡，被別的衍生實體字首包含的裸數字
    # 版本一律丟掉**——它從來不是一個獨立的宣稱。
    bare = {e for e in out if re.fullmatch(r"[^@]+@\d+(?:\.\d+)?", e)}
    if bare and len(out) > len(bare):
        out = [e for e in out if e not in bare]
    return out


# ───────────────────────────────────── HTML → 條目（只對已驗過的形狀動手）
# 規格第 5 節說步 3 要等真 bytes。2026-07-27 `verify-article-metadata.py
# --preset release-notes --save-html` 在**這台機器上**對
# platform.claude.com 拿到 1,436,122 bytes 的完整 HTML（其餘三家被 egress
# 擋住，維持未驗）。所以底下這一支只對**已經看過的那個形狀**動手：
#
#   <h3><div id="july-24-2026"> … <div>July 24, 2026</div> … </div></h3>
#   <ul><li>條目</li><li>條目</li></ul>
#
# 錨點 id 本身就是機器可讀的日期，比解析標題文字穩。實測整頁 124 個。
# **其他三家不套用這支**——它們的錨點形狀還沒有人看過。
# `\d{1,2}(?:st|nd|rd|th)?` 這半截是拿真頁面撞出來的，不是防禦性寫法。
# 第一版寫成 `-\d{1,2}-`，於是 2024 年那批 `id="july-9th-2024"` 一條都沒配到。
# 後果不是「少了那些條目」——是**全部被吞進最後一個配到的錨點**，
# 於是 2024-05 到 2025-04 的每一條都被蓋上 `2025-05-01`。
# 每個日期都是合法日期，只有它們跟事實的關係是錯的（M81 那一課的第三次）。
# `anchor_gap()` 就是為了讓下一次這種漏配不必靠人眼發現。
_ANCHOR = re.compile(
    r'id="((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*'
    r'-\d{1,2}(?:st|nd|rd|th)?-20\d{2})"', re.I)
_LI = re.compile(r"<li\b[^>]*>(.*?)</li>", re.S | re.I)
_STRIP = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")


def strip_tags(html: str) -> str:
    """去標籤 **並且解 HTML entity**。

    第一版沒解 entity，真頁面一跑就看到 `We&#x27;ve launched`——
    而動詞表裡寫的是 `we've launched`。一個撇號讓整類發布條目判成 unknown，
    **而且 unknown_lifecycle_rate 會忠實地把它印出來**，所以它撐不過一次實測。
    這正是那三個比率存在的理由。
    """
    t = _TAGS.sub(" ", _STRIP.sub(" ", html or ""))
    return " ".join(_html.unescape(t).split())


def split_entries_by_anchor(html: str) -> list[tuple[str, str]]:
    """→ [(錨點 id, 該日期底下的純文字)]，依出現順序。

    切法：兩個錨點之間的 HTML 就是前一個錨點的內容。最後一個到檔尾。
    **不去猜哪些 `<li>` 屬於哪一天**——錨點之間的區間本來就是答案，
    而猜巢狀結構會在改版時安靜地錯位（M81 那一課：每個值都對，關係錯了）。
    """
    marks = [(m.group(1).lower(), m.start()) for m in _ANCHOR.finditer(html or "")]
    out = []
    for i, (anchor, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(html)
        out.append((anchor, strip_tags(html[pos:end])))
    return out


def anchor_gap(html: str) -> dict:
    """→ 錨點日期集合 vs 內文日期集合的差集大小。

    錨點漏配的失敗方式是**安靜的**：漏掉的區間會被併進上一個配到的錨點，
    於是那些條目全部蓋上一個錯的日期，而列數、解析率、日期格式全都正常。
    2026-07-27 實測就撞到——`july-9th-2024` 因為 `th` 沒被配到，
    2024-05 至 2025-04 的每一條都被蓋成 `2025-05-01`。

    **第一版比的是「錨點個數 vs 日期出現次數」，那個比法沒有用。**
    真頁面健康時是 (124, 261)——因為同一個日期在標題、索引、內文各出現一次，
    2.1 倍的「落差」是常態。而把錨點規則改壞（M112）之後是 (91, 261)：
    **健康時看起來很糟，壞掉時看起來只是稍微更糟。** 一個永遠在叫的警報，
    跟沒有警報是同一件事——這個 repo 已經為了 heat 印 0 記過這一課。

    改成比**集合**：內文裡出現、而沒有任何錨點對應的日期，才是漏配的證據。
    同一份真頁面上：健康 4 / 128，錨點規則壞掉 37 / 128。九倍的分離度。

    仍然不下判決、只給數字——門檻該由呼叫端連同它自己的頁面形狀一起決定。
    """
    anchors = {a.lower() for a in _ANCHOR.findall(html or "")}
    anchor_dates = {d for d in (parse_entry_date(a.replace("-", " "))[0]
                                for a in anchors) if d}
    text_dates = set()
    for mo, day, yr in _D_YMD.findall(strip_tags(html or "")):
        iso = parse_entry_date(f"{mo} {day}, {yr}")[0]
        if iso:
            text_dates.add(iso)
    return {"anchor_dates": len(anchor_dates),
            "text_dates": len(text_dates),
            "orphan_dates": len(text_dates - anchor_dates)}


def is_date_only(text: str) -> bool:
    """整條就只是一個日期字串——那是目錄／側欄的連結，不是變更條目。

    這條規則是拿真頁面撞出來的，而且它擋掉的量很大：Anthropic 那頁在文末
    有一份「全部日期」的索引清單，**124 條**，全部落在最後一個錨點之後，
    於是全部被蓋上 `2024-05-10`。不擋的話，時間線有三分之一是同一天的假列，
    而每一列的日期都是合法日期。

    判準刻意只認「整條**就是**日期」，不認「開頭是日期」——後者會誤殺
    「July 30, 2026 起 X 將停用」這種真條目。
    """
    t = (text or "").strip()
    # 三種形狀都要認。第一版只認 `_D_YMD`（July 24, 2026），而規格第 1 節
    # 已經指名 `docs.x.ai` 印的是 **沒有年份的「July 23」**——那一家的側欄
    # 索引一條都不會被擋掉，於是最後一個錨點之後的每一項都變成一列，
    # 全部蓋上同一天。**這個函式就是為了防那件事寫的，而它防不到規格已經
    # 寫明會出現的那個形狀。**
    return bool(_D_YMD.fullmatch(t) or _D_YM.fullmatch(t) or _D_MD.fullmatch(t))


def entry_items(chunk_html: str) -> list[str]:
    """→ 一段 HTML 裡每個 <li> 的純文字，去掉目錄項。"""
    return [t for t in (strip_tags(m.group(1)) for m in _LI.finditer(chunk_html or ""))
            if t and not is_date_only(t)]


def rows_from_anchor_page(html: str, source_url: str, product_lines=()) -> list[dict]:
    """整頁 HTML → 時間線的列。**逐 `<li>` 判，不是逐日判。**

    第一版是逐日判的，拿真頁面一跑就看到後果：2026-07-24 那天同時有
    「Claude Opus 5 …」與一條含 preview 字樣的別的更新，整天被判成
    `preview`。**一條的字樣汙染了同一天的其他條。**
    這跟 M81 是同一個形狀——每個值都對，只有它們的歸屬錯了。
    """
    rows: list[dict] = []
    marks = [(m.group(1).lower(), m.start()) for m in _ANCHOR.finditer(html or "")]
    for i, (anchor, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(html)
        chunk = html[pos:end]
        iso, precision, year_source = parse_entry_date(anchor.replace("-", " "))
        # `or [strip_tags(chunk)]` 這個退路會把 `is_date_only` 剛擋掉的東西
        # 整段接回來（外加一截從標籤中間切開的 `id="…">` 碎片）。
        # 有 `<li>` 卻全被過濾＝那一段本來就沒有條目，正確答案是零列。
        has_li = bool(_LI.search(chunk))
        items = entry_items(chunk) if has_li else [strip_tags(chunk)]
        is_tail = (i == len(marks) - 1)
        for text in items:
            if not text:
                continue
            ids = model_ids_in(text)
            derived = derive_versions(text, product_lines)
            rows.append({
                "happened_on": iso,
                "date_precision": precision,
                "date_year_source": year_source,
                "lifecycle": lifecycle_of(text),
                "model_ids": ids,
                "derived_entities": derived,
                "versionish": mentions_version(text, product_lines),
                # 最後一個錨點的區間一路吃到檔尾，所以頁尾的導覽、版權、
                # 「這頁有幫助嗎」全部會被算成它那一天的條目。`is_date_only`
                # 只擋得住純日期的那些。擋不住的就**標記出來**——
                # 消費端可以決定要不要信，但不能假裝不知道。
                "tail_chunk": is_tail,
                "text": text,
                "source_url": source_url,
                "source_tier": 1,
            })
    return rows


def rates(rows: list[dict]) -> dict:
    """→ 規格第 4 節那三個比率。**沒有列的時候回 None 不回 0。**

    0 的意思是「量過了，沒問題」；None 的意思是「沒東西可量」。
    印成 0 就是 `lib/scoring.py` 註解裡那句「0 看起來像量過了，很冷」，
    在這一層換個位置重演。
    """
    rows = rows or []
    # 「時間線真的會留下的列」＝有模型的列（規格第 5′ 節）。lifecycle 那兩個
    # 比率**必須以它為母體**，因為它們是關於時間線的宣稱。
    #
    # 第一版用全部條目當母體，而 unmatched 那一格已經因為同一個理由修過一次
    # （M118，0.79→0.044）——同一個函式裡的另外幾格原封不動留著。
    # 實測代價：真頁面 248 列裡只有 86 列有模型；若動詞表對每一列模型都失效，
    # 印出來的 unknown 從 0.4677 走到 0.7016（+0.23），而真相是 0.33 → 1.00。
    # **一次全面崩壞，在頁首被稀釋成看起來像小幅上升。**
    mrows = [r for r in rows if r.get("model_ids") or r.get("derived_entities")]
    # 分母是「看起來在講某個版本」的條目，不是全部條目。理由見 mentions_version()。
    vrows = [r for r in rows if r.get("versionish")]

    def _rate(hits, pop):
        # 母體是 0 時回 None 不回 0——0 的意思是「量過了，沒問題」。
        # 第一版在 rows 為空時直接回一個**少了 ambiguous 那把鑰匙**的 dict，
        # 消費端一取就 KeyError。誠實的空值要每一格都在。
        return round(hits / len(pop), 4) if pop else None

    return {
        "rows": len(rows),
        "model_rows": len(mrows),
        "versionish_rows": len(vrows),
        # 名字裡說得出分母是誰，不然下一個人只會看到一個小數。
        "unknown_lifecycle_rate": _rate(
            sum(1 for r in mrows if r.get("lifecycle") == UNKNOWN), mrows),
        "ambiguous_lifecycle_rate": _rate(
            sum(1 for r in mrows if r.get("lifecycle") == AMBIGUOUS), mrows),
        # `!= explicit` 把「年份是推的」跟「根本沒有日期」算成同一件事，
        # 而那兩件事要人做的動作完全不同。拆成兩格。
        "section_year_rate": _rate(
            sum(1 for r in rows if r.get("date_year_source") == YEAR_SECTION), rows),
        "no_date_rate": _rate(
            sum(1 for r in rows if not r.get("happened_on")), rows),
        "unmatched_model_rate": _rate(
            sum(1 for r in vrows
                if not (r.get("model_ids") or r.get("derived_entities"))), vrows),
    }
