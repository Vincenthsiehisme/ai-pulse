"""history.py — append-only 狀態帳本的讀寫。單一真相源。

這個 repo 有兩層在記「某個欄位從什麼變成什麼」：

    _probe/source-history.jsonl      來源層（robots_ok / lifecycle）
    _probe/narrative-history.jsonl   判斷層（主線的 now / next / thesis）

在這個檔出現之前，append 那四行被**抄在兩支腳本裡**
（`pulse-robots-recheck.py`、`pulse-source-health.py`），而讀取端的容錯只有
`pulse-source-health.py` 有一份。判斷層要接上來的時候，抄第三份是最省事的作法。

抄下去的失敗形態這個 repo 已經量過五次（`lib/tracks.py` 的 docstring 列了四次，
加上那份手寫的未接線清單）：**兩份在格式沒動過的日子裡給一樣的答案，正好在有人
改了欄位、或加了一個原因碼的那天分岔，而不會有任何東西變紅**——各自都跑得很順，
只是一邊認得那筆異動、另一邊不認得。

所以這裡收成一份，兩層共用。

## 一筆的形狀

```json
{"at": "<UTC ISO8601>", "id": "<誰>", "field": "<哪一格>",
 "from": <舊值>, "to": <新值>, "reason": "<為什麼>"}
```

`from` / `to` 是任意 JSON 值：來源層放的是 `null` / `true` / `"dormant"`，
判斷層放的是整段散文。**兩層都存 `from` 與 `to`**，理由見
`references/narrative-layer.md`〈為什麼 `to` 也要存〉：每一行自足，而且同一個
`(id, field)` 的第 N 行 `to` 應該等於第 N+1 行的 `from`——不相等就代表有人
繞過寫入路徑動了那個檔。

## 為什麼是 jsonl 不是一個大 JSON

append 不是原子的（`open("a")` 寫到一半被砍會留下半行）。jsonl 的半行只損失
**那一筆**，讀取端跳過就好；一個大 JSON 的半份是**整份讀不起來**。
這條分界線與 `references/atomic-writes.md` 是同一句話的兩面：那一份講的是
「壞掉之後會不會被當成事實讀回去」，這裡講的是「壞掉之後還剩多少讀得回來」。

所以 `read()` 對解析不了的行**一律跳過、不炸**——但也因此，
**這個模組不保證帳本是完整的**，只保證它是可讀的。
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED = ("at", "id", "field", "from", "to", "reason")


def append(path, rows) -> int:
    """把 rows append 進 path（jsonl），回實際寫了幾筆。目錄不存在會建。

    rows 是空的就什麼都不做——**連檔案都不建**。建一個 0 bytes 的帳本會讓
    「還沒開始記」跟「記過、只是這一班沒有異動」在下游眼裡長得一樣，
    而那兩件事要人做的事完全不同（紅線 8）。
    """
    rows = list(rows)
    if not rows:
        return 0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            # 一筆一次 write：分兩次寫的話，被砍在中間留下的是一行看起來合法、
            # 內容卻是兩筆黏在一起的東西——那比半行更難發現。
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def latest(rows, field=None):
    """→ {id: 最後一筆}。append-only 帳本的**現值是最後一筆，不是每一筆**。

    2026-08-11 加。在此之前覆蓋缺口矩陣是把每一筆 `unanswerable_reason` 都數進去
    的——26 則一次答完的時候，那跟數最後一筆給的答案一樣，所以它看起來是對的。
    而它會在**第一次有人改答案的那天**開始靜靜多算一筆，且沒有任何東西會變紅。

    這正是這個帳本存在的理由：`from` / `to` 是為了讓「改過」看得見。
    下游如果不分現值與歷史，那個設計就白做了。

    `field` 給值就只看那一格（同 `read()` 的過濾語意）。
    """
    out = {}
    for r in rows:
        if field is not None and r.get("field") != field:
            continue
        out[r.get("id")] = r
    return out


def read(path, *, id=None, field=None):  # noqa: A002 — id 是欄位名，跟 builtin 同名是刻意的
    """讀回帳本（list，依檔案順序）。檔案不存在回 []。

    解析不了的行跳過（見模組 docstring）。少了必填欄位的行也跳過：一筆缺 `field`
    的紀錄進到下游會被當成「某個欄位」處理，而它其實是壞的。
    """
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or any(k not in row for k in REQUIRED):
            continue
        if id is not None and row["id"] != id:
            continue
        if field is not None and row["field"] != field:
            continue
        out.append(row)
    return out


def change(at, id, field, old, new, reason):  # noqa: A002
    """組一筆。`from` 是保留字，所以只能用 dict literal 建——集中在這裡建一次，
    呼叫端就不會有人把它拼成 `from_`（那會產生一份下游讀不到的帳本）。"""
    return {"at": at, "id": id, "field": field, "from": old, "to": new, "reason": reason}
