"""sources.yaml 的來源分節清單 —— 單一真相源。

為什麼要有這個檔：
    在此之前，`("official_sources", "kol_sources", "aggregator_sources")` 這個
    tuple 被硬寫在 **六個** 檔案裡（pulse-probe / pulse-score / pulse-cluster /
    pulse-render / pulse-monitor / pulse-robots-recheck），selftest 裡還有三處。
    新增一個分節（例如 2026-07-26 開的媒體線）要同時改九個地方，漏掉任何一個
    的後果都是靜默的：

      - 漏改 pulse-probe   → 整條媒體線不會被抓，報告不會少一行，只是永遠空白
      - 漏改 pulse-score   → 抓到了但評不到分，訊號全被當 missing_source
      - 漏改 pulse-cluster → 有分數但綁不到 source，tier 一律退回 3、獨立性算錯
      - 漏改 robots-recheck→ 這條線的 robots 永遠不重驗，403 假陰性永久化

    四種都不會讓任何東西變紅——跟 07-24 漏抓 Claude Opus 5 是同一個形態：
    鏈跑得很完美，只是它什麼都看不見。所以清單只准有一份。

    selftest 有一條測試釘住這件事：除了本檔以外，scripts/ 底下任何 .py 都不准
    再出現 "aggregator_sources" 字面值。再硬寫一次就會紅。

順序有意義嗎：
    對 pulse-probe 有。抓取按清單順序跑，官方線先跑，媒體線其次，KOL 線再次，
    聚合線最後——同一則事情，先讓一手發布佔住 first_fetch_at，lead_days 才量得
    到「被承認 vs 被談論」的正號差值。其餘消費端不依賴順序。
"""

SECTIONS = (
    "official_sources",   # 一手發布，可滿足 require_primary_evidence
    "media_sources",      # 媒體報導，Tier 2，永不滿足 primary，只補獨立佐證
    "kol_sources",        # 個人聲音，永不滿足 primary，貢獻 heat 與領先訊號
    "aggregator_sources",  # 只當候選與熱度提示，不作任何事實依據
)


def iter_sources(raw, skip_templates=True):
    """依 SECTIONS 順序走訪 sources.yaml 的所有來源條目。

    skip_templates：跳過 id 以 `<slug>` 結尾的樣板佔位條目。
    """
    for key in SECTIONS:
        for s in raw.get(key) or []:
            if skip_templates and str(s.get("id", "")).endswith("<slug>"):
                continue
            yield s
