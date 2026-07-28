---
generated_day: '2026-07-28'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**5 天**（2026-07-24 … 2026-07-28），去重後 **681** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Industry | 16 | 2 |
| Research | 16 | 2 |
| LLMs | 16 | 6 |
| LLM | 11 | 8 |
| Union | 10 | 2 |
| June | 9 | 4 |
| Energy | 9 | 2 |
| July | 9 | 5 |
| Building | 9 | 7 |
| Here | 9 | 6 |
| U.S | 7 | 4 |
| One | 7 | 5 |
| Security | 6 | 3 |
| Monday | 6 | 4 |
| Learn | 6 | 3 |
| Source | 5 | 2 |
| Gemma | 5 | 4 |
| Understanding | 5 | 3 |
| San Francisco | 5 | 4 |
| Power | 5 | 5 |
| China | 5 | 4 |
| Learning | 5 | 3 |
| January | 5 | 4 |
| Fable | 5 | 3 |
| Pro | 5 | 3 |
| AI-native | 5 | 3 |
| These | 5 | 3 |
| There | 5 | 4 |
| Flash | 4 | 2 |
| Making | 4 | 4 |
| Thursday | 4 | 2 |
| Tuesday | 4 | 2 |
| Python | 4 | 2 |
| Updated | 4 | 2 |
| They | 4 | 3 |
| Built | 4 | 2 |
| American | 4 | 4 |
| Amazon | 4 | 2 |
| Models | 4 | 3 |
| When | 4 | 2 |
| Opus | 4 | 3 |
| Chinese | 4 | 3 |
| Trump | 4 | 3 |
| Apple | 4 | 2 |
| AI-powered | 3 | 3 |
| Finding | 3 | 3 |
| Users | 3 | 2 |
| Part | 3 | 3 |
| Extending | 3 | 2 |
| AI-driven | 3 | 3 |
| Data | 3 | 3 |
| GPUs | 3 | 2 |
| Plus | 3 | 3 |
| Frontier | 3 | 2 |
| Some | 3 | 3 |
| However | 3 | 2 |
| Large | 3 | 2 |
| Let | 3 | 3 |
| With | 3 | 3 |
| From | 3 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Committee | 15 | src-ep-itre |
| Highlights | 14 | src-gh-vllm-releases |
| Show HN | 13 | src-hn-frontpage |
| European Union | 12 | src-ep-itre |
| Draft | 10 | src-ep-itre |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| The Download | 6 | src-media-mit-techreview |
| Co-Scientist | 5 | src-deepmind-blog |
| Wednesday | 4 | src-ep-itre |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Release Notes | 4 | src-gh-vllm-releases |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Video | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Only | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| Open | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| List | 3 | src-kol-raschka |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
