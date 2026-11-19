---
generated_day: '2026-11-19'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**115 天**（2026-07-24 … 2026-11-19），去重後 **7662** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 239 | 2 |
| Apple | 171 | 6 |
| Amazon | 119 | 5 |
| Here | 72 | 9 |
| September | 71 | 8 |
| LLMs | 71 | 14 |
| There | 70 | 9 |
| CEO | 68 | 6 |
| LLM | 67 | 13 |
| They | 65 | 9 |
| Jensen Huang | 60 | 6 |
| Muse | 59 | 6 |
| U.S | 57 | 8 |
| After | 57 | 6 |
| Trump | 56 | 5 |
| October | 56 | 8 |
| One | 52 | 10 |
| China | 51 | 9 |
| November | 51 | 6 |
| Python | 50 | 5 |
| Pro | 50 | 8 |
| When | 48 | 13 |
| San Francisco | 47 | 9 |
| With | 47 | 10 |
| AI-powered | 45 | 10 |
| Chinese | 44 | 8 |
| Rust | 43 | 3 |
| July | 42 | 9 |
| Linux | 42 | 6 |
| Android | 42 | 4 |
| Astra | 39 | 6 |
| IPO | 39 | 8 |
| Last | 38 | 7 |
| Windows | 38 | 6 |
| AI-generated | 37 | 9 |
| August | 36 | 8 |
| These | 35 | 8 |
| API | 34 | 6 |
| June | 33 | 7 |
| Research | 33 | 6 |
| Tuesday | 32 | 6 |
| Learn | 32 | 6 |
| Wednesday | 31 | 5 |
| Huang | 31 | 5 |
| Europe | 30 | 8 |
| Building | 30 | 12 |
| Elon Musk | 30 | 5 |
| Samsung | 30 | 5 |
| Monday | 29 | 6 |
| SpaceX | 29 | 7 |
| While | 29 | 4 |
| Fable | 28 | 8 |
| Mac | 27 | 4 |
| Pixel | 27 | 3 |
| Over | 27 | 7 |
| Friday | 27 | 4 |
| Thursday | 26 | 6 |
| Opus | 26 | 6 |
| RAM | 26 | 3 |
| YouTube | 26 | 7 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| The Download | 87 | src-media-mit-techreview |
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| Tags | 43 | src-kol-simonwillison |
| Hi HN | 34 | src-hn-frontpage |
| Register | 32 | src-media-techcrunch |
| Launch HN | 31 | src-hn-frontpage |
| A Blog | 31 | src-hf-blog |
| Best Buy | 26 | src-media-theverge |
| Opt | 25 | src-media-theverge |
| MIT Technology Review | 25 | src-media-mit-techreview |
| Datasette | 24 | src-kol-simonwillison |
| The Verge | 23 | src-media-theverge |
| Highlights | 21 | src-gh-vllm-releases |
| Import AI | 20 | src-kol-importai |
| Ask HN | 19 | src-hn-frontpage |
| Hey HN | 19 | src-hn-frontpage |
| Is Hiring | 19 | src-hn-frontpage |
| GeForce NOW | 18 | src-nvidia-blog |
| The Stepback | 16 | src-media-theverge |
| Committee | 15 | src-ep-itre |
| Installer No | 14 | src-media-theverge |
| Verge-iest | 14 | src-media-theverge |
| Installer | 14 | src-media-theverge |
| The Algorithm | 12 | src-media-mit-techreview |
| Roundtables | 12 | src-media-mit-techreview |
| Disrupt | 12 | src-media-techcrunch |
| TechCrunch Founder Summit | 12 | src-media-techcrunch |
| FCC | 11 | src-media-theverge |
| YC S26 | 11 | src-hn-frontpage |
| Verge | 11 | src-media-theverge |
| VCs | 11 | src-media-techcrunch |
| PlayStation | 10 | src-media-theverge |
| Victoria Song | 10 | src-media-theverge |
| Startup Battlefield | 10 | src-media-techcrunch |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Open-source | 9 | src-hn-frontpage |
| Apple TV | 9 | src-media-theverge |
| Series A | 9 | src-media-techcrunch |
| Optimizer | 9 | src-media-theverge |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Code | 8 | src-hn-frontpage |
| Wi-Fi | 8 | src-media-theverge |
| IBM Research | 8 | src-hf-blog |
| Grand Theft Auto | 8 | src-media-theverge |
| Following | 7 | src-media-theverge |
| Woot | 7 | src-media-theverge |
| Galaxy Z Fold | 7 | src-media-theverge |
| Spider-Man | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Bose | 7 | src-media-theverge |
| YC S23 | 7 | src-hn-frontpage |
| Zelda | 7 | src-media-theverge |
| On Equity | 7 | src-media-techcrunch |
| YC F26 | 7 | src-hn-frontpage |
| Korea | 6 | src-nvidia-blog |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
