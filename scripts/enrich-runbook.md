# enrich-runbook.md — Cowork 潤稿執行說明（Sprint 3c）

這份是給 **Cowork**（互動 session 或排程 Cowork 任務）照著做的 runbook。目的：把 pulse-cluster
產出的 `status: review` Event（六層 prose 還是「待編輯」佔位）潤成人話並過 speak-human-tw。

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

- prep 只挑「還有待編輯佔位」的 Event；apply 寫完後佔位消失、`enriched: true`，下次 prep 自動跳過。
- 所以重跑不會重潤已潤的，成本只跟「新事件數」走。

## 自動化模式（排程 Cowork 任務用）

這一節給無人值守的排程任務照著跑。呼叫端（scheduled task）會先用帶 token 的 URL clone 好 repo、cd 進去，再叫你「照這節做」。**token 只出現在 clone 指令裡，絕不寫進這個 repo 任何檔案。**

前置（呼叫端已完成）：
`git clone https://<user>:<TOKEN>@github.com/<owner>/ai-pulse.git && cd ai-pulse`
（clone 後 origin remote 已內含憑證，後面 push 不必再帶 token。）

你依序做：

1. 環境：`pip install pyyaml --quiet`。
2. git 身份：`git config user.name "ai-pulse-enrich" && git config user.email "ai-pulse-enrich@users.noreply.github.com"`
3. `export VAULT_DIR="$PWD"`

**0. 前置檢查：今晚的資料到底進來了沒**（一定要做，這是 2026-07-24 那次空轉的補丁）

這條鏈跟 GitHub Actions 只靠時鐘耦合：Actions 的 cron 是「最早不早於」，實測誤點過 96 分鐘。
你比它早到 → clone 到的是昨天的 repo → worklist 空 → 整晚看起來「正常無事」，其實今天的事件沒人潤。
所以先確認資料在不在，不在就自己補跑一次抓取（那條鏈本來就是純規則、零 LLM，你只是代跑，不是代判斷）：

```
TODAY=$(date -u +%F)
if [ -d "_corpus/$TODAY" ]; then
  echo "[pre] 今日 corpus 已就緒：_corpus/$TODAY"
else
  echo "[pre] 今日 corpus 不存在——Actions 還沒跑到或誤點，改由我補跑抓取鏈"
  pip install requests feedparser ruamel.yaml --quiet
  python scripts/pulse-robots-recheck.py --stale-days 7 --apply --revive || true
  python scripts/pulse-probe.py || echo "[warn] probe 無新料或部分來源失敗，續跑"
  python scripts/pulse-score.py
  python scripts/pulse-cluster.py
fi
```

補跑不會撞車：`pulse-probe` 有 cursor、`pulse-cluster` 以 fingerprint 去重，Actions 之後再跑一次是冪等的。
補跑過就在收尾摘要註明「今晚由潤稿端補跑抓取」——這是要被看見的異常，不是可以吞掉的細節。

**A. 事件潤稿（敘述）**
4. prep：`python scripts/pulse-enrich-prep.py` → 讀 `_probe/enrich-worklist.json`。若為空陣列 → A 段跳過。
5. 依本檔「流程 步驟 2–3」的 schema 與 speak-human-tw 規則，為 worklist 每個 Event 產出 `enrich-result.json`（dict keyed by event_id）。紅線：判斷不由你決定發不發、只依證據不編造、去 AI 口吻。
6. apply：先 `python scripts/pulse-enrich-apply.py --in enrich-result.json --dry-run` 自檢，再正式 `python scripts/pulse-enrich-apply.py --in enrich-result.json`。

**B. 過門禁 + 索引**
7. `python scripts/pulse-gate.py && python scripts/pulse-dashboard.py`

**C. 主線敘事刷新（只在有主線變動時；這也是敘述、同樣過 speak-human-tw）**
8. `python scripts/pulse-narrative-prep.py` → 讀 `_probe/narrative-worklist.json`。
   - **若為空陣列 → 整個 C 段跳過**（多數夜晚如此：只有某主線今晚新增／變動事件才會 dirty；dirty 由事件集合簽章決定，不由你判斷）。
   - 否則對每個 dirty 主線，依它的 `events`（附 title/summary/date/confidence/heat）**只重寫 `now` 與 `next` 兩段——thesis 與 lenses 不要動**。只依事件、不編造、套 speak-human-tw 自動化模式、去 AI 口吻。`now`＝這條線目前狀態；`next`＝接下來要觀察的可驗證訊號。
   - 組成 `narrative-result.json`：`{"<track-slug>":{"now":"...","next":"..."}, ...}`（只放 dirty 主線）。
   - `python scripts/pulse-narrative-apply.py --in narrative-result.json`（過 voice_clean、更新 updated、記錄簽章）。

**C2. GitHub 星速榜的中文描述（敘述；同樣過 speak-human-tw）**

repo 的 description 來自 GitHub API，是英文一行字。榜是給中文讀者看的，所以描述要翻。
翻譯是**敘述**不是判斷——排名、星速、上不上榜全部還是規則算的，你一個數字都不碰。

9. 重建榜單（**不要加 `--snapshot`**：星速基線只由 Actions 那班更新，你多打一次會把 Δ/天洗掉）：
   ```
   python scripts/pulse-github.py
   ```
   `dist/` 沒進版控，所以每次 clone 都要重建。環境有 `GITHUB_TOKEN` 會自動帶上；沒有也跑得動
   （未認證額度較緊）。這步失敗就整個 C2 段跳過，不影響其他段——榜會維持上一晚的英文原文。

   **跳過現在會留下痕跡（2026-07-27）**：Actions 每班把「榜上有幾條中文」寫進
   `_github/desc-coverage.json`，`_dashboards/health.md` 印成一行，而且分得出
   「量不到 / 從來沒翻過 / 有過然後停了」三種。在此之前 C2 連續跳過幾十班都不會有
   任何地方看得出來——`desc-zh.json` 在整個 git 歷史裡從來沒有出現過。
   規格見 `references/vault-pages.md`。**所以這一步失敗時，收尾摘要要寫出來是為什麼
   失敗（多半是沒有 GITHUB_TOKEN、未認證額度用完），不要只寫「C2 跳過」。**
10. prep：`python scripts/pulse-github-desc-prep.py --limit 25` → 讀 `_probe/github-desc-worklist.json`。
    **若為空陣列 → C2 跳過**（穩定之後多數夜晚如此：只有新上榜、或上游改了 description 的才會排進來）。
11. 逐條翻寫，組成 `github-desc-result.json`：`{"<owner/repo>": "中文描述", ...}`。規則：
    - **只翻 `desc` 那句，不加料。** 不知道這個 repo 在做什麼就照字面翻，不要靠印象補背景、
      不要寫「業界廣泛採用」這種原文沒有的話。worklist 只給你原文、語言、topics、星數。
    - **一行字，≤60 字**，寫成人看得懂的白話，不是詞典式硬翻。專有名詞（LLM、RAG、MCP、
      Kubernetes…）保留原文不要硬翻成中文。
    - 去 AI 腔：不要「值得關注」「無限可能」「賦能」「助力」「打造」「旨在」「隨著…」。
      apply 會擋掉這些字，退件不是靜靜丟掉，是印出來下次重排。
    - `stale_zh` 有值 ＝ 上游改了描述、舊譯文失效要重譯，不是新 repo。對照著改，別整句重寫。
12. apply：先 `--dry-run` 自檢，再正式寫入：
    ```
    python scripts/pulse-github-desc-apply.py --in github-desc-result.json --dry-run
    python scripts/pulse-github-desc-apply.py --in github-desc-result.json
    ```
    譯文存進 `_github/desc-zh.json`（**這個檔進版控**，所以翻過的不會白翻，明晚 Actions
    重建榜單時會自動掛回去）。原文永遠留在 `desc` 欄且前台一併顯示——譯文是二手的，
    讀者要能看到一手的那句。

**D. 產站 + 推回**
13. render：`python scripts/pulse-render.py`
14. 推回：
    `git add -A`
    `git diff --cached --quiet && echo "無變更" || (git commit -m "nightly: enrich + narrative $(date -u +%F)" && git push)`
15. 健康監看（純規則，只讀不寫）：`python scripts/pulse-monitor.py --top 5`
    把它的輸出原樣放進收尾摘要。重點看三個數字：`probe_lag_days`（資料幾天沒更新）、
    `待處理`（扣掉 stale_backfill 這種設計上就該擋著的，真正卡住的有幾則）、`未 enrich`，
    外加最後那張覆蓋範圍表——「來源」那欄是 0 的必盯公司代表沒有任何來源在看它。
16. 收尾摘要：潤了幾則事件、gate 讓幾則上線、重寫了哪幾條主線敘事、翻了幾條 repo 描述
    （退件幾條、為什麼）、push 的 commit hash
    （或「今晚無待潤事件、無主線變動」）、是否補跑過抓取、以及第 15 步的監看輸出。
    **「今晚沒事做」跟「今晚沒跑到」長得一樣**——所以摘要一定要帶監看數字，讓人一眼分得出來是哪一種。

失敗處理：任一步非預期失敗就停、印出錯誤、**不要 push 半成品**。enrich 與敘事刷新都冪等，明晚會再挑同一批。
