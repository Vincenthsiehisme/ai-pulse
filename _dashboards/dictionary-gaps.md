---
generated_day: '2026-11-13'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**109 天**（2026-07-24 … 2026-11-13），去重後 **7195** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 226 | 2 |
| Apple | 164 | 6 |
| Amazon | 107 | 5 |
| Here | 70 | 9 |
| LLMs | 69 | 13 |
| There | 68 | 9 |
| September | 67 | 8 |
| They | 61 | 9 |
| LLM | 61 | 12 |
| Muse | 56 | 6 |
| CEO | 55 | 5 |
| After | 54 | 6 |
| U.S | 53 | 8 |
| October | 53 | 8 |
| Trump | 52 | 5 |
| Pro | 50 | 8 |
| One | 49 | 10 |
| Python | 48 | 5 |
| San Francisco | 46 | 9 |
| November | 46 | 6 |
| When | 45 | 12 |
| China | 44 | 8 |
| AI-powered | 43 | 10 |
| July | 40 | 9 |
| Android | 40 | 4 |
| With | 39 | 10 |
| Linux | 39 | 6 |
| Chinese | 38 | 8 |
| Rust | 38 | 3 |
| Last | 38 | 7 |
| Jensen Huang | 36 | 5 |
| AI-generated | 35 | 9 |
| Windows | 35 | 5 |
| Astra | 34 | 6 |
| August | 33 | 8 |
| IPO | 33 | 7 |
| June | 32 | 7 |
| Research | 32 | 6 |
| These | 32 | 8 |
| API | 32 | 6 |
| Learn | 31 | 6 |
| Europe | 30 | 8 |
| Wednesday | 30 | 5 |
| Samsung | 30 | 5 |
| Building | 29 | 12 |
| Elon Musk | 28 | 5 |
| While | 28 | 4 |
| SpaceX | 27 | 6 |
| Pixel | 27 | 3 |
| Tuesday | 26 | 6 |
| Opus | 26 | 6 |
| Fable | 26 | 6 |
| Xbox | 26 | 2 |
| Thursday | 25 | 6 |
| Monday | 25 | 4 |
| YouTube | 25 | 7 |
| Mac | 24 | 4 |
| According | 24 | 4 |
| Over | 24 | 6 |
| Duo | 24 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| The Download | 83 | src-media-mit-techreview |
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| Tags | 42 | src-kol-simonwillison |
| Hi HN | 32 | src-hn-frontpage |
| Register | 32 | src-media-techcrunch |
| A Blog | 30 | src-hf-blog |
| Launch HN | 27 | src-hn-frontpage |
| MIT Technology Review | 25 | src-media-mit-techreview |
| Opt | 24 | src-media-theverge |
| The Verge | 23 | src-media-theverge |
| Best Buy | 23 | src-media-theverge |
| Highlights | 21 | src-gh-vllm-releases |
| Ask HN | 19 | src-hn-frontpage |
| GeForce NOW | 18 | src-nvidia-blog |
| Is Hiring | 18 | src-hn-frontpage |
| Hey HN | 17 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| The Stepback | 15 | src-media-theverge |
| Datasette | 15 | src-kol-simonwillison |
| Installer No | 13 | src-media-theverge |
| Verge-iest | 13 | src-media-theverge |
| Installer | 13 | src-media-theverge |
| Disrupt | 12 | src-media-techcrunch |
| TechCrunch Founder Summit | 12 | src-media-techcrunch |
| The Algorithm | 11 | src-media-mit-techreview |
| YC S26 | 11 | src-hn-frontpage |
| Roundtables | 11 | src-media-mit-techreview |
| Verge | 11 | src-media-theverge |
| Sunday | 10 | src-media-theverge |
| FCC | 10 | src-media-theverge |
| Victoria Song | 10 | src-media-theverge |
| VCs | 10 | src-media-techcrunch |
| Startup Battlefield | 10 | src-media-techcrunch |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Apple TV | 9 | src-media-theverge |
| PlayStation | 9 | src-media-theverge |
| Optimizer | 9 | src-media-theverge |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Open-source | 8 | src-hn-frontpage |
| Series A | 8 | src-media-techcrunch |
| Following | 7 | src-media-theverge |
| Woot | 7 | src-media-theverge |
| Galaxy Z Fold | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Bose | 7 | src-media-theverge |
| Wi-Fi | 7 | src-media-theverge |
| IBM Research | 7 | src-hf-blog |
| Grand Theft Auto | 7 | src-media-theverge |
| YC S23 | 7 | src-hn-frontpage |
| On Equity | 7 | src-media-techcrunch |
| Related | 6 | src-hn-frontpage |
| Code | 6 | src-hn-frontpage |
| AI Stage | 6 | src-media-techcrunch |
| Los Angeles | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
