---
generated_day: '2026-08-04'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**12 天**（2026-07-24 … 2026-08-04），去重後 **1100** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 23 | 10 |
| July | 18 | 7 |
| Industry | 16 | 2 |
| Research | 16 | 2 |
| June | 14 | 6 |
| Here | 14 | 8 |
| European Union | 13 | 2 |
| LLM | 13 | 8 |
| Apple | 13 | 5 |
| Building | 12 | 8 |
| U.S | 11 | 4 |
| Union | 10 | 2 |
| Amazon | 10 | 3 |
| One | 10 | 7 |
| Energy | 9 | 2 |
| Thursday | 9 | 3 |
| When | 9 | 4 |
| Monday | 8 | 4 |
| They | 8 | 6 |
| Trump | 8 | 4 |
| Tuesday | 7 | 4 |
| Python | 7 | 3 |
| Learn | 7 | 3 |
| There | 7 | 5 |
| RAM | 7 | 2 |
| Wednesday | 6 | 2 |
| Security | 6 | 3 |
| Gemma | 6 | 5 |
| China | 6 | 5 |
| With | 6 | 5 |
| Opus | 6 | 3 |
| Fable | 6 | 3 |
| Rust | 6 | 2 |
| Pro | 6 | 4 |
| AI-native | 6 | 3 |
| Samsung | 6 | 2 |
| August | 6 | 2 |
| Source | 5 | 2 |
| Understanding | 5 | 3 |
| San Francisco | 5 | 4 |
| Built | 5 | 3 |
| Power | 5 | 5 |
| Models | 5 | 4 |
| Learning | 5 | 3 |
| Let | 5 | 4 |
| January | 5 | 4 |
| Mac | 5 | 3 |
| Chinese | 5 | 4 |
| Advancing | 5 | 3 |
| These | 5 | 3 |
| SpaceX | 5 | 3 |
| CEO | 5 | 3 |
| Chrome | 5 | 4 |
| Flash | 4 | 2 |
| AI-powered | 4 | 4 |
| Making | 4 | 4 |
| Video | 4 | 2 |
| Updated | 4 | 2 |
| Part | 4 | 3 |
| Anatomy | 4 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 31 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Highlights | 14 | src-gh-vllm-releases |
| The Download | 11 | src-media-mit-techreview |
| Draft | 10 | src-ep-itre |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| Hi HN | 7 | src-hn-frontpage |
| Co-Scientist | 5 | src-deepmind-blog |
| Tags | 5 | src-kol-simonwillison |
| Sam Altman | 5 | src-media-techcrunch |
| The Verge | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Release Notes | 4 | src-gh-vllm-releases |
| AI-generated | 4 | src-media-techcrunch |
| Spider-Man | 4 | src-media-theverge |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Only | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| GeForce NOW | 3 | src-nvidia-blog |
| Open | 3 | src-kol-interconnects |
| Latest | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| List | 3 | src-kol-raschka |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| TechCrunch Disrupt | 3 | src-media-techcrunch |
| RAMageddon | 3 | src-media-theverge |
| Launch HN | 3 | src-hn-frontpage |
| YC S26 | 3 | src-hn-frontpage |
| Montana | 3 | src-media-mit-techreview |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
