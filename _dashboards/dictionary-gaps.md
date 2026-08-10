---
generated_day: '2026-08-10'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**14 天**（2026-07-24 … 2026-08-10），去重後 **1269** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 25 | 11 |
| July | 22 | 9 |
| June | 17 | 7 |
| Research | 17 | 3 |
| Apple | 17 | 5 |
| Industry | 16 | 2 |
| LLM | 16 | 8 |
| Here | 16 | 8 |
| U.S | 15 | 6 |
| European Union | 13 | 2 |
| Building | 13 | 8 |
| Amazon | 12 | 3 |
| One | 11 | 8 |
| August | 11 | 4 |
| Union | 10 | 2 |
| Wednesday | 10 | 4 |
| When | 10 | 4 |
| Trump | 10 | 4 |
| Energy | 9 | 2 |
| Thursday | 9 | 3 |
| They | 9 | 6 |
| There | 9 | 5 |
| Elon Musk | 9 | 5 |
| Monday | 8 | 4 |
| SpaceX | 8 | 4 |
| RAM | 8 | 2 |
| Tuesday | 7 | 4 |
| Python | 7 | 3 |
| Learn | 7 | 3 |
| Pro | 7 | 4 |
| After | 7 | 4 |
| AI-powered | 6 | 4 |
| Security | 6 | 3 |
| Gemma | 6 | 5 |
| San Francisco | 6 | 5 |
| Texas | 6 | 4 |
| China | 6 | 5 |
| With | 6 | 5 |
| January | 6 | 5 |
| Opus | 6 | 3 |
| Fable | 6 | 3 |
| Chinese | 6 | 4 |
| Rust | 6 | 2 |
| SQLite | 6 | 2 |
| AI-native | 6 | 3 |
| These | 6 | 4 |
| Samsung | 6 | 2 |
| Source | 5 | 2 |
| Part | 5 | 3 |
| Understanding | 5 | 3 |
| Built | 5 | 3 |
| Power | 5 | 5 |
| Models | 5 | 4 |
| Learning | 5 | 3 |
| Let | 5 | 4 |
| From | 5 | 5 |
| Mac | 5 | 3 |
| Advancing | 5 | 3 |
| World | 5 | 4 |
| NASA | 5 | 2 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 33 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Highlights | 14 | src-gh-vllm-releases |
| The Download | 14 | src-media-mit-techreview |
| Draft | 10 | src-ep-itre |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Tags | 8 | src-kol-simonwillison |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| Hi HN | 7 | src-hn-frontpage |
| Co-Scientist | 5 | src-deepmind-blog |
| Sam Altman | 5 | src-media-techcrunch |
| The Verge | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Release Notes | 4 | src-gh-vllm-releases |
| GeForce NOW | 4 | src-nvidia-blog |
| Nancy Grace Roman | 4 | src-media-mit-techreview |
| TechCrunch Disrupt | 4 | src-media-techcrunch |
| RAMageddon | 4 | src-media-theverge |
| Spider-Man | 4 | src-media-theverge |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Only | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| Latest | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| List | 3 | src-kol-raschka |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| Space Telescope | 3 | src-media-mit-techreview |
| Equity | 3 | src-media-techcrunch |
| The Stepback | 3 | src-media-theverge |
| Opt | 3 | src-media-theverge |
| Ask HN | 3 | src-hn-frontpage |
| Launch HN | 3 | src-hn-frontpage |
| YC S26 | 3 | src-hn-frontpage |
| Montana | 3 | src-media-mit-techreview |
| Sure | 3 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
