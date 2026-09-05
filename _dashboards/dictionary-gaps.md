---
generated_day: '2026-09-05'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**40 天**（2026-07-24 … 2026-09-05），去重後 **2740** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 55 | 5 |
| LLMs | 38 | 12 |
| LLM | 35 | 11 |
| Amazon | 34 | 5 |
| July | 28 | 9 |
| Here | 26 | 8 |
| They | 25 | 9 |
| There | 25 | 7 |
| Research | 21 | 5 |
| U.S | 21 | 7 |
| August | 21 | 5 |
| June | 20 | 7 |
| One | 20 | 9 |
| When | 20 | 7 |
| Python | 19 | 3 |
| Trump | 19 | 4 |
| Pixel | 19 | 3 |
| Building | 18 | 10 |
| CEO | 17 | 5 |
| Android | 17 | 3 |
| Industry | 16 | 2 |
| Linux | 16 | 5 |
| Pro | 16 | 4 |
| After | 16 | 6 |
| European Union | 15 | 3 |
| Samsung | 15 | 3 |
| AI-powered | 14 | 8 |
| Europe | 14 | 7 |
| Wednesday | 14 | 4 |
| China | 14 | 5 |
| With | 14 | 9 |
| Elon Musk | 14 | 5 |
| Flash | 13 | 4 |
| September | 13 | 5 |
| San Francisco | 13 | 8 |
| Rust | 13 | 3 |
| SpaceX | 13 | 5 |
| RAM | 13 | 2 |
| Astra | 13 | 5 |
| Fable | 12 | 4 |
| These | 12 | 6 |
| AI-generated | 12 | 3 |
| Draft | 11 | 2 |
| Thursday | 11 | 3 |
| Tuesday | 11 | 4 |
| Monday | 11 | 4 |
| Flock | 11 | 3 |
| Opus | 11 | 4 |
| Union | 10 | 2 |
| Learn | 10 | 3 |
| India | 10 | 3 |
| From | 10 | 8 |
| While | 10 | 4 |
| Energy | 9 | 2 |
| Built | 9 | 6 |
| Texas | 9 | 6 |
| May | 9 | 5 |
| Mac | 9 | 4 |
| SQLite | 9 | 2 |
| Qwen | 9 | 2 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 71 | src-hn-frontpage |
| The Download | 33 | src-media-mit-techreview |
| Highlights | 16 | src-gh-vllm-releases |
| Committee | 15 | src-ep-itre |
| Hi HN | 15 | src-hn-frontpage |
| Launch HN | 13 | src-hn-frontpage |
| Tags | 11 | src-kol-simonwillison |
| YC S26 | 11 | src-hn-frontpage |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| TechCrunch Disrupt | 9 | src-media-techcrunch |
| The Verge | 9 | src-media-theverge |
| GeForce NOW | 8 | src-nvidia-blog |
| Best Buy | 8 | src-media-theverge |
| Minutes | 7 | src-ep-itre |
| Opt | 7 | src-media-theverge |
| Ask HN | 7 | src-hn-frontpage |
| Bloomberg | 6 | src-media-theverge |
| November | 6 | src-media-theverge |
| Co-Scientist | 5 | src-deepmind-blog |
| According | 5 | src-media-theverge |
| Marvel | 5 | src-media-theverge |
| The Stepback | 5 | src-media-theverge |
| FCC | 5 | src-media-theverge |
| The Algorithm | 5 | src-media-mit-techreview |
| Netflix | 5 | src-media-theverge |
| Galaxy Z Fold | 5 | src-media-theverge |
| Spider-Man | 5 | src-media-theverge |
| MIT Technology Review | 5 | src-media-mit-techreview |
| Decoder | 5 | src-media-theverge |
| Grand Theft Auto | 5 | src-media-theverge |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Tool | 4 | src-kol-simonwillison |
| Equity | 4 | src-media-techcrunch |
| At TechCrunch Disrupt | 4 | src-media-techcrunch |
| Peacock | 4 | src-media-theverge |
| RAMageddon | 4 | src-media-theverge |
| Zig | 4 | src-hn-frontpage |
| Switch | 4 | src-media-theverge |
| Sure | 4 | src-media-theverge |
| Installer No | 4 | src-media-theverge |
| Verge-iest | 4 | src-media-theverge |
| Installer | 4 | src-media-theverge |
| Disney | 4 | src-media-theverge |
| TikTok | 4 | src-media-theverge |
| GTA VI | 4 | src-media-theverge |
| Rockstar Games | 4 | src-media-theverge |
| Is Hiring | 4 | src-hn-frontpage |
| Defence Source | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| Kubernetes | 3 | src-hn-frontpage |
| Latest | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| Qwen3 | 3 | src-qwen-blog |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
