---
generated_day: '2026-09-11'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**46 天**（2026-07-24 … 2026-09-11），去重後 **3163** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 74 | 5 |
| LLMs | 38 | 12 |
| Amazon | 36 | 5 |
| LLM | 35 | 11 |
| There | 32 | 7 |
| They | 31 | 9 |
| July | 30 | 9 |
| Here | 29 | 8 |
| Research | 25 | 6 |
| Python | 24 | 4 |
| When | 24 | 9 |
| August | 24 | 7 |
| One | 22 | 9 |
| Pro | 22 | 6 |
| June | 21 | 7 |
| U.S | 21 | 7 |
| Android | 21 | 4 |
| Pixel | 20 | 3 |
| Trump | 19 | 4 |
| CEO | 19 | 5 |
| September | 18 | 5 |
| Building | 18 | 10 |
| China | 18 | 6 |
| Linux | 18 | 5 |
| After | 18 | 6 |
| Samsung | 18 | 4 |
| AI-powered | 17 | 8 |
| With | 17 | 9 |
| Wednesday | 16 | 4 |
| Industry | 16 | 2 |
| Astra | 16 | 5 |
| Europe | 15 | 7 |
| European Union | 15 | 3 |
| San Francisco | 15 | 8 |
| Rust | 15 | 3 |
| SpaceX | 15 | 5 |
| Flash | 14 | 4 |
| Elon Musk | 14 | 5 |
| AI-generated | 14 | 5 |
| Thursday | 13 | 4 |
| Fable | 13 | 4 |
| These | 13 | 6 |
| RAM | 13 | 2 |
| Some | 12 | 7 |
| Draft | 11 | 2 |
| Tuesday | 11 | 4 |
| Monday | 11 | 4 |
| Learn | 11 | 3 |
| Texas | 11 | 6 |
| India | 11 | 3 |
| Flock | 11 | 3 |
| May | 11 | 5 |
| Opus | 11 | 4 |
| API | 11 | 4 |
| Last | 11 | 6 |
| While | 11 | 4 |
| Union | 10 | 2 |
| Ultra | 10 | 4 |
| From | 10 | 8 |
| Chinese | 10 | 6 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 84 | src-hn-frontpage |
| The Download | 38 | src-media-mit-techreview |
| Highlights | 17 | src-gh-vllm-releases |
| Hi HN | 16 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Tags | 15 | src-kol-simonwillison |
| Launch HN | 13 | src-hn-frontpage |
| YC S26 | 11 | src-hn-frontpage |
| TechCrunch Disrupt | 10 | src-media-techcrunch |
| The Verge | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| GeForce NOW | 9 | src-nvidia-blog |
| Ask HN | 9 | src-hn-frontpage |
| Opt | 8 | src-media-theverge |
| Best Buy | 8 | src-media-theverge |
| MIT Technology Review | 8 | src-media-mit-techreview |
| Minutes | 7 | src-ep-itre |
| Tool | 7 | src-kol-simonwillison |
| November | 7 | src-media-theverge |
| Marvel | 6 | src-media-theverge |
| The Stepback | 6 | src-media-theverge |
| FCC | 6 | src-media-theverge |
| Bloomberg | 6 | src-media-theverge |
| Galaxy Z Fold | 6 | src-media-theverge |
| Switch | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Decoder | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| Is Hiring | 6 | src-hn-frontpage |
| Co-Scientist | 5 | src-deepmind-blog |
| According | 5 | src-media-theverge |
| The Algorithm | 5 | src-media-mit-techreview |
| Netflix | 5 | src-media-theverge |
| Innovators Under | 5 | src-media-mit-techreview |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Latest | 4 | src-kol-interconnects |
| Equity | 4 | src-media-techcrunch |
| Sunday | 4 | src-media-theverge |
| At TechCrunch Disrupt | 4 | src-media-techcrunch |
| Peacock | 4 | src-media-theverge |
| RAMageddon | 4 | src-media-theverge |
| Zig | 4 | src-hn-frontpage |
| Woot | 4 | src-media-theverge |
| Sure | 4 | src-media-theverge |
| Installer No | 4 | src-media-theverge |
| Verge-iest | 4 | src-media-theverge |
| Installer | 4 | src-media-theverge |
| Disney | 4 | src-media-theverge |
| Hey HN | 4 | src-hn-frontpage |
| TikTok | 4 | src-media-theverge |
| A Blog | 4 | src-hf-blog |
| GTA VI | 4 | src-media-theverge |
| The New York | 4 | src-media-theverge |
| Times | 4 | src-media-theverge |
| Rockstar Games | 4 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
