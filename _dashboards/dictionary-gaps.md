---
generated_day: '2026-08-12'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**16 天**（2026-07-24 … 2026-08-12），去重後 **1409** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 27 | 11 |
| July | 21 | 9 |
| Apple | 21 | 5 |
| June | 18 | 7 |
| Research | 17 | 3 |
| Industry | 16 | 2 |
| U.S | 16 | 7 |
| LLM | 16 | 8 |
| Here | 16 | 8 |
| Amazon | 14 | 4 |
| Pixel | 14 | 3 |
| European Union | 13 | 2 |
| Building | 13 | 8 |
| August | 13 | 5 |
| One | 12 | 8 |
| There | 12 | 5 |
| Wednesday | 11 | 4 |
| Union | 10 | 2 |
| When | 10 | 4 |
| Trump | 10 | 4 |
| After | 10 | 5 |
| Energy | 9 | 2 |
| Thursday | 9 | 3 |
| Tuesday | 9 | 4 |
| Monday | 9 | 4 |
| Python | 9 | 3 |
| They | 9 | 6 |
| Rust | 9 | 3 |
| Pro | 9 | 4 |
| These | 9 | 5 |
| Android | 9 | 3 |
| Elon Musk | 8 | 5 |
| SpaceX | 8 | 4 |
| Samsung | 8 | 2 |
| AI-powered | 7 | 5 |
| Learn | 7 | 3 |
| San Francisco | 7 | 6 |
| China | 7 | 5 |
| With | 7 | 6 |
| From | 7 | 6 |
| Fable | 7 | 3 |
| SQLite | 7 | 2 |
| AI-native | 7 | 3 |
| RAM | 7 | 2 |
| CEO | 7 | 4 |
| Security | 6 | 3 |
| Release Notes | 6 | 2 |
| Gemma | 6 | 5 |
| Texas | 6 | 5 |
| Models | 6 | 5 |
| January | 6 | 5 |
| Opus | 6 | 3 |
| Chinese | 6 | 4 |
| AI-generated | 6 | 2 |
| Chrome | 6 | 4 |
| Making | 5 | 4 |
| Source | 5 | 2 |
| Understanding | 5 | 3 |
| Built | 5 | 3 |
| Plus | 5 | 5 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 36 | src-hn-frontpage |
| The Download | 17 | src-media-mit-techreview |
| Committee | 15 | src-ep-itre |
| Highlights | 15 | src-gh-vllm-releases |
| Draft | 10 | src-ep-itre |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Tags | 9 | src-kol-simonwillison |
| Hi HN | 8 | src-hn-frontpage |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| Co-Scientist | 5 | src-deepmind-blog |
| Launch HN | 5 | src-hn-frontpage |
| Sam Altman | 5 | src-media-techcrunch |
| The Verge | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| GeForce NOW | 4 | src-nvidia-blog |
| Nancy Grace Roman | 4 | src-media-mit-techreview |
| TechCrunch Disrupt | 4 | src-media-techcrunch |
| Sure | 4 | src-media-theverge |
| Spider-Man | 4 | src-media-theverge |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Only | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| CEO Jensen Huang | 3 | src-nvidia-blog |
| Markdown | 3 | src-hn-frontpage |
| Latest | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| Space Telescope | 3 | src-media-mit-techreview |
| Equity | 3 | src-media-techcrunch |
| FCC | 3 | src-media-theverge |
| RAMageddon | 3 | src-media-theverge |
| The Algorithm | 3 | src-media-mit-techreview |
| Ask HN | 3 | src-hn-frontpage |
| Apple Silicon | 3 | src-hn-frontpage |
| YC S26 | 3 | src-hn-frontpage |
| Galaxy Z Fold | 3 | src-media-theverge |
| Best Buy | 3 | src-media-theverge |
| Montana | 3 | src-media-mit-techreview |
| MIT Technology Review | 3 | src-media-mit-techreview |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
