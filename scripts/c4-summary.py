#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4-summary.py — 把 c4-report.json 變成貼得進設計文件的一段 Markdown。

**為什麼要有這支**：`verify-article-metadata.py` 的判決原本只活在一個
artifact 裡——要下載才看得到、預設 90 天後過期、repo 裡沒有任何一個字記得它。
而 C-4 是整個模型時間線層的閘（`references/model-timeline.md` 第 5 節步 2）：
C-3 動不動工、另外三家的切分器寫不寫，全部取決於它。

把一個 gate 的答案放在一個會過期、又讀不到的地方，跟這個 repo 一路在抓的
「量到了但沒人接得到」是同一個形態，只是這次的介面是 CI 與人之間。

輸出刻意**只含判決與欄位有無**，不含任何內文——留存的是標題、連結、日期，
正好就是 `license_note: titles + links only`（紅線 7）。原始 HTML 留在
artifact 裡，不進版控。

用法：
    python scripts/c4-summary.py c4-report.json <preset> <exit_code> >> $GITHUB_STEP_SUMMARY
"""
from __future__ import annotations

import json
import os
import sys

EXIT_MEANING = {
    "0": "全部拿到判決，且每一條都通過該 preset 的條件",
    "2": "**站方回答了，而答案是「不行」**（robots 明文 Disallow 或 4xx/5xx）",
    "3": "**站方回答了、我們也讀到了，但內容不合**這一組 preset 要的東西",
    "4": "**沒有判決**——關於我們自己，不是關於站方（control probe 沒過／"
         "egress 攔截／robots 取不到／傳輸層例外）",
}

KEYS = ("url", "verdict", "status", "bytes", "robots", "robots_reason", "note")


UNREGISTERED = "未登記的退出碼，當成沒有判決處理"


def render(path: str, preset: str, code: str) -> str:
    """→ 要印進 step summary 的 Markdown。

    **拉成函式是為了測得到。** 第一版只有 `main()`，補的測試寫成
    `EXIT_MEANING.get("99", "未登記…") ` ——那是在讀**測試自己寫的預設值**，
    不管碼怎麼寫都會過（M135 因此活下來）。這是同一條分支上第五次犯它。
    規則：**斷言裡不准出現 `X.get(k, 預設)`**——那個預設是你的，不是碼的。
    """
    out = [f"## C-4 判決：`{preset}`", ""]
    out.append(f"退出碼 **{code}** — {EXIT_MEANING.get(code, UNREGISTERED)}")
    out.append("")

    if not os.path.exists(path):
        out += ["_沒有產生 `c4-report.json`——control probe 就沒過。_",
                "",
                "**這種情況什麼都不要寫進設計。** 連 CI 都連不出去，代表問題在我們這邊，"
                "而不是關於那幾個站的任何事實。"]
        return "\n".join(out)

    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)

    cp = d.get("control_probe")
    out.append(f"control probe：`{cp}`" if cp else
               "**control probe 被跳過了（`--skip-control`）——這份報告不可引用。**")
    out.append("")
    out.append("| url | verdict | status | bytes | robots | note |")
    out.append("|---|---|---|---|---|---|")
    for r in d.get("results", []):
        cells = [str(r.get(k) if r.get(k) is not None else "—").replace("|", "\\|")[:110]
                 for k in ("url", "verdict", "status", "bytes", "robots", "note")]
        out.append("| " + " | ".join(cells) + " |")

    out += ["", "### 每一條抽到了什麼", ""]
    for r in d.get("results", []):
        f = r.get("fields") or {}
        if not f:
            out.append(f"- `{r.get('url')}` — 沒有讀到 HTML，沒有欄位可談")
            continue
        present = [k for k, v in f.items() if not k.startswith("_")
                   and k != "visible_date_count" and v]
        absent = [k for k, v in f.items() if not k.startswith("_")
                  and k != "visible_date_count" and not v]
        out.append(f"- `{r.get('url')}`")
        out.append(f"  - 可見文字 {f.get('_visible_text_chars')} 字"
                   f"（JS 空殼會接近零）；人看的日期 ×{f.get('visible_date_count')}")
        out.append(f"  - **有**：{', '.join(present) or '（無）'}")
        out.append(f"  - **ABSENT**：{', '.join(absent) or '（無）'}")

    out += ["", "---", "",
            "**上面這一段就是可以貼進 `references/model-timeline.md` 第 5′ 節的東西。**",
            "原始 HTML 在本次 run 的 artifact 裡（`raw-html/`），"
            "**它不進版控**——留存只到標題／連結／日期為止（紅線 7）。"]
    return "\n".join(out)


def main() -> int:
    print(render(sys.argv[1] if len(sys.argv) > 1 else "c4-report.json",
                 sys.argv[2] if len(sys.argv) > 2 else "?",
                 sys.argv[3] if len(sys.argv) > 3 else "?"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
