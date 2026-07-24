# enrich-runbook.md — Cowork 潤稿執行說明（Sprint 3c）

這份是給 **Cowork**（互動 session 或排程 Cowork 任務）照著做的 runbook。目的：把 pulse-cluster
產出的 `status: review` Event（六層 prose 還是「待编辑」佔位）潤成人話並過 speak-human-tw。

## 紅線（不可違反）

1. **判斷不由你決定。** 你只寫敘述。發不發是 3d gate 的規則決定，你不改 status、不改分數。
2. **只根據提供的證據寫，不編造。** worklist 每個 Event 附了綁定證據的標題 + 摘要。prose 只能講
   證據支持的內容。證據不足以支撐某一層 → 那一層寫「（證據不足，待補）」，**不要瞎掰**。
   （對照 speak-human-tw：假故事比空話更糟——空話只是無聊，編造是說謊。）
3. **去 AI 口吻。** 見下方規則摘要；出來的字要像一個犀利的人類分析師寫的，不是模型腔。

## 模式：跳過確認、事後摘要

這一步接進自動化工作流（排程任務半夜跑，沒有人即時確認）。依 speak-human-tw 的
「自動化工作流模式」，走 **跳過確認、事後摘要**：直接把分析出的改法全部套用，跑完由
`pulse-enrich-apply.py` 印一份事後摘要，交人（或 git diff）事後檢查。**不要**輸出一個沒人會回答的問句然後停住。

## 流程

1. **跑 prep**（確定性，先做）：
   ```
   VAULT_DIR=<vault> python scripts/pulse-enrich-prep.py
   ```
   產出 `_probe/enrich-worklist.json`。

2. **讀 worklist**，逐個 Event 寫六層 prose。每個 item 有：`title / fingerprint / facet /
   company_guess / independent_sources / evidence[{source_id,title,summary,url}]`。

3. **為每個 Event 產出結構化結果**（不是自由散文），組成一份 JSON：
   ```json
   {
     "<event_id>": {
       "summary":     "一句話 lead：這件事最重要的是什麼（≤50 字）",
       "fact":        "## 事實：發生了什麼，具體、只講證據有的",
       "context":     "## 脈絡：放在什麼背景才看得懂",
       "impact":      "## 影響：對能力 / 成本 / 競爭結構的影響",
       "judgment":    "## 判斷：你的分析（rule-tag 由 apply 自動加，你不用寫待證實那句）",
       "next_signal": "## 下一個訊號：接下來要觀察哪個可驗證訊號",
       "category":    "model-capability | product | research | policy | infra | capital | ...",
       "track":       "模型能力與研究 | Agent與軟體重構 | 產品與商業驗證 | 基礎設施與成本 | 資本與公司演化 | 全球創新版圖",
       "keywords":    ["3-6 個"],
       "company":     "修正後的公司名（company_guess 若是 industry 而證據看得出主體，改對）"
     }
   }
   ```
   存成 `enrich-result.json`。

4. **跑 apply**（確定性寫回 + 後洗 + 事後摘要）：
   ```
   VAULT_DIR=<vault> python scripts/pulse-enrich-apply.py --in enrich-result.json --dry-run   # 先預覽
   VAULT_DIR=<vault> python scripts/pulse-enrich-apply.py --in enrich-result.json             # 正式寫入
   ```

5. **commit + push**（GitHub 鏈接上後由排程任務做；手動階段你自己 push）。

## speak-human-tw 規則摘要（寫的時候就套，別事後才補）

**先刪**：公式化開場（「在當今瞬息萬變的 AI 領域」「隨著 AI 快速發展」這類時代大帽子）、
通用積極結論（「未來充滿無限可能」「值得持續關注」）、對話殘留（「希望這對你有幫助」）。
第一句就要有只有這則 Event 才有的資訊。

**再具體化**：價值上升詞落地——「標誌著 / 見證了 / 奠定基礎 / 體現了 / 不僅僅是」改成具體事實，
寫不出來就刪。避免立場真空（「各有優缺點」「因人而異」）——給明確判斷，或標「（需補充）」。

**再降格式**：破折號每 300–500 字最多 1 次（多的改逗號 / 句號 / 冒號）；「不是 A，而是 B」整段最多一次；
「首先 / 其次 / 最後」三段式拆掉，服從邏輯不服從對稱；少用粗體。

**台灣在地化**：全形標點「，。：；！？「」（）、」；中國用語替換（視頻→影片、質量→品質、
信息→資訊、網絡→網路、軟件→軟體、默認→預設、智能→智慧、水平→水準…）。這層 `voice_clean.py`
會再兜一次底，但你寫的時候就該對。

**人味**：短句長句交錯、對事實做出反應而非只報告、資訊密度可以不平均（最有話說的那點給兩倍篇幅）。
但**人味是作者的不是你的**——別替作者發明沒有的立場或故事。

## 冪等 / 成本

- prep 只挑「還有待编辑佔位」的 Event；apply 寫完後佔位消失、`enriched: true`，下次 prep 自動跳過。
- 所以重跑不會重潤已潤的，成本只跟「新事件數」走。
