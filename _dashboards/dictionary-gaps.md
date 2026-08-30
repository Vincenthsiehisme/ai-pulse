---
generated_day: '2026-08-30'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**34 天**（2026-07-24 … 2026-08-30），去重後 **2385** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 43 | 5 |
| LLMs | 35 | 12 |
| LLM | 31 | 9 |
| Amazon | 30 | 5 |
| July | 26 | 9 |
| There | 24 | 7 |
| They | 22 | 9 |
| Research | 21 | 5 |
| Here | 21 | 8 |
| June | 20 | 7 |
| U.S | 20 | 7 |
| August | 20 | 5 |
| When | 19 | 7 |
| Building | 18 | 10 |
| One | 18 | 9 |
| Trump | 18 | 4 |
| Pixel | 18 | 3 |
| Industry | 16 | 2 |
| Python | 16 | 3 |
| Android | 15 | 3 |
| Wednesday | 14 | 4 |
| After | 14 | 6 |
| AI-powered | 13 | 7 |
| European Union | 13 | 2 |
| Rust | 13 | 3 |
| Linux | 13 | 4 |
| Pro | 13 | 4 |
| Elon Musk | 13 | 5 |
| SpaceX | 13 | 5 |
| Samsung | 13 | 3 |
| China | 12 | 5 |
| With | 12 | 8 |
| RAM | 12 | 2 |
| CEO | 12 | 4 |
| Draft | 11 | 2 |
| Thursday | 11 | 3 |
| Tuesday | 11 | 4 |
| San Francisco | 11 | 8 |
| Union | 10 | 2 |
| Monday | 10 | 4 |
| Learn | 10 | 3 |
| Flock | 10 | 3 |
| From | 10 | 8 |
| Opus | 10 | 4 |
| These | 10 | 5 |
| Flash | 9 | 4 |
| Europe | 9 | 6 |
| Energy | 9 | 2 |
| Texas | 9 | 6 |
| May | 9 | 5 |
| SQLite | 9 | 2 |
| Qwen | 9 | 2 |
| Last | 9 | 5 |
| AI-generated | 9 | 3 |
| September | 8 | 4 |
| Built | 8 | 5 |
| India | 8 | 3 |
| Welcome | 8 | 3 |
| Fable | 8 | 3 |
| Chinese | 8 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 64 | src-hn-frontpage |
| The Download | 29 | src-media-mit-techreview |
| Highlights | 16 | src-gh-vllm-releases |
| Committee | 15 | src-ep-itre |
| Hi HN | 13 | src-hn-frontpage |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Tags | 9 | src-kol-simonwillison |
| Launch HN | 9 | src-hn-frontpage |
| The Verge | 9 | src-media-theverge |
| Minutes | 7 | src-ep-itre |
| GeForce NOW | 7 | src-nvidia-blog |
| YC S26 | 7 | src-hn-frontpage |
| Opt | 6 | src-media-theverge |
| TechCrunch Disrupt | 6 | src-media-techcrunch |
| Best Buy | 6 | src-media-theverge |
| Co-Scientist | 5 | src-deepmind-blog |
| Marvel | 5 | src-media-theverge |
| The Stepback | 5 | src-media-theverge |
| FCC | 5 | src-media-theverge |
| Netflix | 5 | src-media-theverge |
| Spider-Man | 5 | src-media-theverge |
| MIT Technology Review | 5 | src-media-mit-techreview |
| Grand Theft Auto | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Equity | 4 | src-media-techcrunch |
| According | 4 | src-media-theverge |
| At TechCrunch Disrupt | 4 | src-media-techcrunch |
| Peacock | 4 | src-media-theverge |
| Zig | 4 | src-hn-frontpage |
| The Algorithm | 4 | src-media-mit-techreview |
| Ask HN | 4 | src-hn-frontpage |
| Galaxy Z Fold | 4 | src-media-theverge |
| Switch | 4 | src-media-theverge |
| Sure | 4 | src-media-theverge |
| Installer No | 4 | src-media-theverge |
| Verge-iest | 4 | src-media-theverge |
| Installer | 4 | src-media-theverge |
| Disney | 4 | src-media-theverge |
| Decoder | 4 | src-media-theverge |
| GTA VI | 4 | src-media-theverge |
| Rockstar Games | 4 | src-media-theverge |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| Kubernetes | 3 | src-hn-frontpage |
| Latest | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| Tool | 3 | src-kol-simonwillison |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| Htmx | 3 | src-hn-frontpage |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
