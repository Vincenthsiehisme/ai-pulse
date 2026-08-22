---
generated_day: '2026-08-22'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**26 天**（2026-07-24 … 2026-08-22），去重後 **1965** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 31 | 11 |
| Apple | 31 | 5 |
| Amazon | 26 | 5 |
| July | 24 | 9 |
| LLM | 24 | 9 |
| Research | 21 | 5 |
| There | 20 | 7 |
| June | 19 | 7 |
| U.S | 19 | 7 |
| They | 18 | 8 |
| Here | 18 | 8 |
| Pixel | 18 | 3 |
| One | 17 | 9 |
| August | 17 | 5 |
| Industry | 16 | 2 |
| Building | 16 | 10 |
| When | 16 | 6 |
| European Union | 13 | 2 |
| Pro | 13 | 4 |
| Wednesday | 12 | 4 |
| With | 12 | 8 |
| Trump | 12 | 4 |
| Draft | 11 | 2 |
| Python | 11 | 3 |
| Rust | 11 | 3 |
| Linux | 11 | 4 |
| Elon Musk | 11 | 5 |
| RAM | 11 | 2 |
| After | 11 | 5 |
| Android | 11 | 3 |
| AI-powered | 10 | 5 |
| Union | 10 | 2 |
| Thursday | 10 | 3 |
| Tuesday | 10 | 4 |
| Learn | 10 | 3 |
| San Francisco | 10 | 7 |
| SpaceX | 10 | 4 |
| Samsung | 10 | 2 |
| Energy | 9 | 2 |
| Monday | 9 | 4 |
| China | 9 | 5 |
| These | 9 | 5 |
| Last | 9 | 5 |
| CEO | 9 | 4 |
| Texas | 8 | 5 |
| Flock | 8 | 3 |
| Opus | 8 | 4 |
| AI-native | 8 | 3 |
| Mark Zuckerberg | 8 | 3 |
| Over | 8 | 3 |
| Flash | 7 | 3 |
| Built | 7 | 5 |
| GPUs | 7 | 4 |
| Models | 7 | 6 |
| From | 7 | 6 |
| January | 7 | 5 |
| Fable | 7 | 3 |
| SQLite | 7 | 2 |
| API | 7 | 4 |
| AI-generated | 7 | 2 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 54 | src-hn-frontpage |
| The Download | 24 | src-media-mit-techreview |
| Committee | 15 | src-ep-itre |
| Highlights | 15 | src-gh-vllm-releases |
| Hi HN | 10 | src-hn-frontpage |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Tags | 9 | src-kol-simonwillison |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| Launch HN | 7 | src-hn-frontpage |
| The Verge | 7 | src-media-theverge |
| GeForce NOW | 6 | src-nvidia-blog |
| Co-Scientist | 5 | src-deepmind-blog |
| Marvel | 5 | src-media-theverge |
| FCC | 5 | src-media-theverge |
| YC S26 | 5 | src-hn-frontpage |
| TechCrunch | 5 | src-media-techcrunch |
| Best Buy | 5 | src-media-theverge |
| Spider-Man | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Nancy Grace Roman | 4 | src-media-mit-techreview |
| Equity | 4 | src-media-techcrunch |
| TechCrunch Disrupt | 4 | src-media-techcrunch |
| The Algorithm | 4 | src-media-mit-techreview |
| Ask HN | 4 | src-hn-frontpage |
| Galaxy Z Fold | 4 | src-media-theverge |
| Sure | 4 | src-media-theverge |
| Disney | 4 | src-media-theverge |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| CEO Jensen Huang | 3 | src-nvidia-blog |
| Latest | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| Tool | 3 | src-kol-simonwillison |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| GrapheneOS | 3 | src-hn-frontpage |
| Space Telescope | 3 | src-media-mit-techreview |
| According | 3 | src-media-theverge |
| The Stepback | 3 | src-media-theverge |
| Opt | 3 | src-media-theverge |
| Peacock | 3 | src-media-theverge |
| RAMageddon | 3 | src-media-theverge |
| Lean | 3 | src-hn-frontpage |
| Zig | 3 | src-hn-frontpage |
| Apple Silicon | 3 | src-hn-frontpage |
| Rippling | 3 | src-media-techcrunch |
| APIs | 3 | src-media-techcrunch |
| Montana | 3 | src-media-mit-techreview |
| Star Wars | 3 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
