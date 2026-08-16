---
generated_day: '2026-08-16'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**20 天**（2026-07-24 … 2026-08-16），去重後 **1621** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 27 | 11 |
| Apple | 24 | 5 |
| July | 23 | 9 |
| June | 19 | 7 |
| Research | 18 | 4 |
| LLM | 18 | 9 |
| U.S | 17 | 7 |
| Amazon | 17 | 5 |
| Industry | 16 | 2 |
| Here | 16 | 8 |
| Building | 15 | 9 |
| Pixel | 14 | 3 |
| European Union | 13 | 2 |
| They | 13 | 7 |
| One | 13 | 8 |
| There | 13 | 5 |
| August | 13 | 5 |
| When | 12 | 4 |
| Draft | 11 | 2 |
| Wednesday | 11 | 4 |
| Trump | 11 | 4 |
| Android | 11 | 3 |
| Union | 10 | 2 |
| Python | 10 | 3 |
| After | 10 | 5 |
| Energy | 9 | 2 |
| Thursday | 9 | 3 |
| Tuesday | 9 | 4 |
| Monday | 9 | 4 |
| San Francisco | 9 | 7 |
| China | 9 | 5 |
| Rust | 9 | 3 |
| Pro | 9 | 4 |
| These | 9 | 5 |
| Elon Musk | 9 | 5 |
| SpaceX | 9 | 4 |
| Samsung | 9 | 2 |
| AI-powered | 8 | 5 |
| Learn | 8 | 3 |
| With | 8 | 7 |
| Linux | 8 | 4 |
| AI-native | 8 | 3 |
| Flash | 7 | 3 |
| Texas | 7 | 5 |
| From | 7 | 6 |
| January | 7 | 5 |
| Opus | 7 | 4 |
| Fable | 7 | 3 |
| SQLite | 7 | 2 |
| RAM | 7 | 2 |
| Mark Zuckerberg | 7 | 3 |
| AI-generated | 7 | 2 |
| CEO | 7 | 4 |
| Security | 6 | 3 |
| Release Notes | 6 | 2 |
| Gemma | 6 | 5 |
| Built | 6 | 4 |
| GPUs | 6 | 4 |
| Some | 6 | 6 |
| Models | 6 | 5 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 45 | src-hn-frontpage |
| The Download | 19 | src-media-mit-techreview |
| Committee | 15 | src-ep-itre |
| Highlights | 15 | src-gh-vllm-releases |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Hi HN | 9 | src-hn-frontpage |
| Tags | 9 | src-kol-simonwillison |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| Launch HN | 6 | src-hn-frontpage |
| The Verge | 6 | src-media-theverge |
| Co-Scientist | 5 | src-deepmind-blog |
| GeForce NOW | 5 | src-nvidia-blog |
| Marvel | 5 | src-media-theverge |
| Sam Altman | 5 | src-media-techcrunch |
| Spider-Man | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Nancy Grace Roman | 4 | src-media-mit-techreview |
| TechCrunch Disrupt | 4 | src-media-techcrunch |
| YC S26 | 4 | src-hn-frontpage |
| Firefox | 4 | src-hn-frontpage |
| Sure | 4 | src-media-theverge |
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
| Tool | 3 | src-kol-simonwillison |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| Space Telescope | 3 | src-media-mit-techreview |
| Equity | 3 | src-media-techcrunch |
| The Stepback | 3 | src-media-theverge |
| Opt | 3 | src-media-theverge |
| FCC | 3 | src-media-theverge |
| RAMageddon | 3 | src-media-theverge |
| The Algorithm | 3 | src-media-mit-techreview |
| Ask HN | 3 | src-hn-frontpage |
| Apple Silicon | 3 | src-hn-frontpage |
| Galaxy Z Fold | 3 | src-media-theverge |
| TechCrunch | 3 | src-media-techcrunch |
| APIs | 3 | src-media-techcrunch |
| Best Buy | 3 | src-media-theverge |
| Montana | 3 | src-media-mit-techreview |
| Star Wars | 3 | src-media-theverge |
| Brand New Day | 3 | src-media-theverge |
| Disney | 3 | src-media-theverge |
| Not | 3 | src-hn-frontpage |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
