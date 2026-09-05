"""「這兩個網址是不是同一顆」的判準 —— 規格見 references/attach-rule.md〈同一顆 URL 二次進站〉。

只回答一個問題：兩個 URL 指的是不是**同一個資源**。它**不是** canonical URL——
`pulse-probe.canonical_url()` 還處理 tracking query string、參數排序，結果寫進
語料的 `url_canonical` 欄位；這裡的結果不進任何 frontmatter，算完即丟。

去的東西：scheme、`www.`、fragment、結尾斜線；host 轉小寫。
**query string 留著。** 實測語料裡帶 query 的網址（2026-09-04，16,409 筆裡 66 筆），
最多的三種是 HN 的 `item?id=`、YouTube 的 `watch?v=`、`qwen.ai/blog?id=`——
query 就是資源本身，去掉之後兩篇不同的 HN 討論串會變成「同一顆 URL」，
而這支函式的下游是「同一顆 URL 就直接 attach、不看標題」。
代價是 utm 那類 tracking 參數在這裡不處理：同一篇文章兩次觀測帶不同 utm
會認不出來——那跟 `Event.add_evidence()` 逐字元去重是同一個邊界，這裡不比它寬。

fragment 去掉是有實例的：simonwillison 的 feed 同一篇文章有 `…/` 與
`…/#atom-everything` 兩種寫法，庫裡兩則 Event 各躺著這樣一對證據。

兩支腳本共用（`pulse-cluster.attach_by_url()`、`pulse-backlog-status` 的
「同一顆 URL 落在幾則 Event」量測）。放進 lib/ 是為了只有一份判準——
兩份判準遲早會給出不同的答案。
"""
from urllib.parse import urlsplit

__all__ = ["loose_key"]


def loose_key(url) -> str:
    """URL → 判斷「同一顆」用的鍵。空值回空字串，不拋例外。"""
    if not url:
        return ""
    s = urlsplit(str(url).strip())
    host = s.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = s.path.rstrip("/") or "/"
    return f"{host}{path}?{s.query}" if s.query else f"{host}{path}"
