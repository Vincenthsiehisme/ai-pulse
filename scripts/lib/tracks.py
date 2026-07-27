"""tracks.py — 六大主線的 slug / 顯示名 / 顏色。單一真相源。

為什麼要有這個檔：同一份對照表原本寫在**兩個地方**——
`pulse-narrative-prep.py` 的 `TRACKS` + `NAME2SLUG` + `ALIAS`，
以及 `pulse-render.py` 的 `TRACKS` + `TRACK_BY_NAME` + `TRACK_ALIASES`。
兩份連那個「Agent與軟體重構」少一個空白的別名修補都各寫了一次。

2026-07-27 要加第三個消費者（`Tracks/*.md` 節點頁）的時候，抄第三份是最省事的
作法。抄下去的失敗形態這個 repo 已經量過四次（`lib/sources.py`、`lib/entities.py`、
`lib/dictgaps.py`、那份手寫的未接線清單）：兩份在對照表沒動過的日子裡給一樣的
答案，正好在有人加了一條主線、或改了一個顯示名的那天分岔，而**不會有任何東西
變紅**——各自都跑得很順，只是一邊認得那條線、另一邊不認得。

顏色也放這裡：它今天只有 renderer 在用，但它跟名字是同一組事實，
分兩個地方放遲早會出現「有名字沒顏色」的第七條線。
"""
from __future__ import annotations

# 順序有意義：對外頁面照這個順序排。
TRACKS = [
    ("model-research",    "模型能力與研究",   "#9b8cff"),
    ("agent-refactor",    "Agent 與軟體重構", "#4ee4ba"),
    ("product-market",    "產品與商業驗證",   "#ff8b6b"),
    ("infra-cost",        "基礎設施與成本",   "#f2bf62"),
    ("capital-evolution", "資本與公司演化",   "#ad91ff"),
    ("global-map",        "全球創新版圖",     "#6fb1ff"),
]

SLUGS = [slug for slug, _, _ in TRACKS]
NAMES = [name for _, name, _ in TRACKS]
BY_SLUG = {slug: (slug, name, color) for slug, name, color in TRACKS}
BY_NAME = {name: (slug, name, color) for slug, name, color in TRACKS}
NAME2SLUG = {name: slug for slug, name, _ in TRACKS}

# 寫進 Event 的 track 值來自 enrich，空白不一定跟這裡一致（實測庫裡有
# 「Agent與軟體重構」，少一個空白）。別名表只收**實際出現過的寫法**，
# 不做模糊比對——模糊比對會把「產品與商業驗證」跟一條將來的新線混在一起。
ALIAS = {
    "模型能力與研究": "模型能力與研究",
    "Agent與軟體重構": "Agent 與軟體重構",
    "Agent 與軟體重構": "Agent 與軟體重構",
    "產品與商業驗證": "產品與商業驗證",
    "基礎設施與成本": "基礎設施與成本",
    "資本與公司演化": "資本與公司演化",
    "全球創新版圖": "全球創新版圖",
}


def canonical_name(track) -> str | None:
    """Event 上的 track 字串 → 正規顯示名。認不出就回 None，**不猜**。"""
    return ALIAS.get((track or "").strip())


def slug_of(track) -> str | None:
    """Event 上的 track 字串 → slug。認不出就回 None。"""
    name = canonical_name(track)
    return NAME2SLUG.get(name) if name else None
