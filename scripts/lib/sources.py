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


# 會被抓的 lifecycle。規格見 references/source-lifecycle.md〈五個狀態〉。
#
# 2026-08-11 搬到這裡。在那之前這個集合被硬寫在**四個**檔案裡：pulse-probe、
# pulse-monitor、pulse-source-notes，以及 pulse-source-health（在那裡叫 RUNNABLE）。
# 跟上面 SECTIONS 是同一個病、同樣是靜默的：漏改一處的後果是「某一類 lifecycle
# 在這支腳本眼裡不存在」，而清單長度不會變、沒有東西會紅。
#
# 搬家的觸發點是 capability 判準要用到這個集合（references/source-capabilities.md）。
# 寫第五份會讓判準自己變成病的一部分，所以先搬再用。
RUN_LIFECYCLES = frozenset({"active", "degraded", "probing"})

# capability 封閉詞彙表。規格與每個值的語意見 references/source-capabilities.md。
#
# 為什麼在 lib/ 不在 _config/：`_config/` 放的是操作者可以調的旋鈕，
# 詞彙表不是旋鈕是結構——改它等於改資料模型，該走 PR 不該改一行 YAML。
#
# 為什麼封閉：開放詞彙表半年後會長出 benchmarks / benchmark_result /
# third-party_validation 這種同義異形，而覆蓋率矩陣會安靜地把它們算成不同格。
# selftest 有一條釘住：值不在這裡就紅。
CAPABILITIES = frozenset({
    "official_announcement",   # 官方承認某件事發生了
    "product_release",         # 有東西可以用了
    "research_release",        # 方法／模型／論文本身
    "benchmark",               # 有人跑了數字
    "third_party_validation",  # 不是發布方的人說了話
    "research_replication",    # 有人試著重現
    "enterprise_adoption",     # 有組織真的在用
    "procurement",             # 有人真的付錢買了（2026-08-11：0 條來源宣稱）
    "supply_chain",            # 晶片／機櫃／電力實際流動
    "infrastructure",          # 機房、算力、網路蓋起來了
    "financial_impact",        # 錢的方向變了
    "policy_execution",        # 法規從紙上變成執行
    "social_signal",           # 圈子在談
    "developer_feedback",      # 用的人回報了什麼
})


# `unanswerable` 的原因碼 ＝ 能力詞彙表 ＋ 一個 other。**衍生，不抄寫。**
#
# 規格 references/source-capabilities.md〈同一份詞彙表的第二個用途〉。
# PRD 把 reason 與 capability 寫成兩份不同的清單（11 vs 14），但 §19 的
# Gap × Capability 矩陣要求兩者能直接比較——用兩份清單 join，會有些 Demand 的列
# 永遠對不到 Source、有些 Source 的列永遠沒有 Demand，而那不是量出來的洞，
# 是詞彙表的洞。
#
# 更根本的：「這個訊號我回答不了」的理由本來就是一個**能力請求**。
# 需求面與供給面講的是同一件事，軸必須對齊。
#
# `other` 只在 reason 這一側：一條來源不能宣稱自己「有能力報導其他」。
REASONS = CAPABILITIES | frozenset({"other"})


def is_running(src):
    """這條來源會不會被抓。`lifecycle` 缺值＝不會（往嚴的方向倒）。"""
    return (src or {}).get("lifecycle") in RUN_LIFECYCLES


# 「不是發布方的人」＝ 媒體線 + KOL 線。
#
# `aggregator` 刻意不在裡面：`_config/sources.yaml` 的檔頭寫明它「只當候選來源，
# 不作任何事實依據」。把 HN 算成獨立供給，等於讓一個轉貼站撐起某一格的覆蓋率。
#
# 這個集合的消費者是覆蓋缺口矩陣的燈號（references/vault-pages.md）。
# 為什麼燈號只看獨立那一欄：2026-08-11 的 26 則裁決裡，22 則判 unanswerable 的
# **每一則都是「只有官方說了，我們判定看不到」**——官方供給在這批需求上的
# 實測命中率是 0。這是量出來的，不是推論的。
INDEPENDENT_TRACKS = frozenset({"media", "kol"})
OFFICIAL_TRACKS = frozenset({"official"})


def capability_claims(raw, tracks=None):
    """→ {capability: [source_id, ...]}，只算會被抓的來源。

    只算 running 的是刻意的：一條 dormant 來源的 capability 是**將來**的宣稱，
    把它算進覆蓋率會讓盲區看起來比實際小——而這一整層存在的理由就是把盲區
    指出來。停用的來源不補盲區。

    `tracks` 給一個 track 集合就只算那幾軌（例如 INDEPENDENT_TRACKS）。
    給 None 算全部——**包含 aggregator**，因為「這一格總共有幾條來源宣稱」
    跟「有幾條獨立來源」是兩個不同的問題，不該用同一個過濾器回答。
    """
    out = {}
    for s in iter_sources(raw):
        if not is_running(s):
            continue
        if tracks is not None and s.get("track") not in tracks:
            continue
        for c in (s.get("capabilities") or []):
            out.setdefault(c, []).append(str(s.get("id")))
    return out


def iter_sources(raw, skip_templates=True):
    """依 SECTIONS 順序走訪 sources.yaml 的所有來源條目。

    skip_templates：跳過 id 以 `<slug>` 結尾的樣板佔位條目。
    """
    for key in SECTIONS:
        for s in raw.get(key) or []:
            if skip_templates and str(s.get("id", "")).endswith("<slug>"):
                continue
            yield s
