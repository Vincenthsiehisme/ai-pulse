---
generated_day: '2026-11-17'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**113 天**（2026-07-24 … 2026-11-17），去重後 **7513** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 234 | 2 |
| Apple | 169 | 6 |
| Amazon | 114 | 5 |
| Here | 72 | 9 |
| LLMs | 71 | 14 |
| September | 68 | 8 |
| There | 68 | 9 |
| LLM | 67 | 13 |
| They | 65 | 9 |
| CEO | 63 | 6 |
| Muse | 57 | 6 |
| After | 56 | 6 |
| U.S | 55 | 8 |
| Trump | 55 | 5 |
| Jensen Huang | 54 | 6 |
| October | 53 | 8 |
| One | 51 | 10 |
| Pro | 50 | 8 |
| November | 50 | 6 |
| Python | 49 | 5 |
| China | 48 | 9 |
| San Francisco | 47 | 9 |
| When | 47 | 13 |
| AI-powered | 43 | 10 |
| July | 42 | 9 |
| Chinese | 42 | 8 |
| Rust | 42 | 3 |
| With | 41 | 10 |
| Linux | 41 | 6 |
| Android | 41 | 4 |
| Last | 38 | 7 |
| Astra | 38 | 6 |
| AI-generated | 37 | 9 |
| Windows | 37 | 5 |
| August | 36 | 8 |
| IPO | 35 | 8 |
| API | 34 | 6 |
| June | 33 | 7 |
| These | 33 | 8 |
| Research | 32 | 6 |
| Learn | 31 | 6 |
| Europe | 30 | 8 |
| Wednesday | 30 | 5 |
| Tuesday | 30 | 6 |
| Building | 30 | 12 |
| Samsung | 30 | 5 |
| Monday | 29 | 6 |
| Elon Musk | 29 | 5 |
| SpaceX | 29 | 7 |
| While | 29 | 4 |
| Fable | 28 | 8 |
| Huang | 28 | 5 |
| Pixel | 27 | 3 |
| Opus | 26 | 6 |
| YouTube | 26 | 7 |
| Xbox | 26 | 2 |
| Friday | 26 | 4 |
| Thursday | 25 | 6 |
| Mac | 25 | 4 |
| Over | 25 | 6 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| The Download | 85 | src-media-mit-techreview |
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| Tags | 43 | src-kol-simonwillison |
| Hi HN | 33 | src-hn-frontpage |
| Register | 32 | src-media-techcrunch |
| A Blog | 30 | src-hf-blog |
| Launch HN | 29 | src-hn-frontpage |
| Best Buy | 26 | src-media-theverge |
| Opt | 25 | src-media-theverge |
| MIT Technology Review | 25 | src-media-mit-techreview |
| The Verge | 23 | src-media-theverge |
| Datasette | 23 | src-kol-simonwillison |
| Highlights | 21 | src-gh-vllm-releases |
| Import AI | 20 | src-kol-importai |
| Ask HN | 19 | src-hn-frontpage |
| GeForce NOW | 18 | src-nvidia-blog |
| Hey HN | 18 | src-hn-frontpage |
| Is Hiring | 18 | src-hn-frontpage |
| The Stepback | 16 | src-media-theverge |
| Committee | 15 | src-ep-itre |
| Installer No | 14 | src-media-theverge |
| Verge-iest | 14 | src-media-theverge |
| Installer | 14 | src-media-theverge |
| The Algorithm | 12 | src-media-mit-techreview |
| Roundtables | 12 | src-media-mit-techreview |
| Disrupt | 12 | src-media-techcrunch |
| TechCrunch Founder Summit | 12 | src-media-techcrunch |
| Sunday | 11 | src-media-theverge |
| YC S26 | 11 | src-hn-frontpage |
| Verge | 11 | src-media-theverge |
| VCs | 11 | src-media-techcrunch |
| FCC | 10 | src-media-theverge |
| PlayStation | 10 | src-media-theverge |
| Victoria Song | 10 | src-media-theverge |
| Startup Battlefield | 10 | src-media-techcrunch |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Apple TV | 9 | src-media-theverge |
| Series A | 9 | src-media-techcrunch |
| Optimizer | 9 | src-media-theverge |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Code | 8 | src-hn-frontpage |
| Open-source | 8 | src-hn-frontpage |
| Wi-Fi | 8 | src-media-theverge |
| Grand Theft Auto | 8 | src-media-theverge |
| Following | 7 | src-media-theverge |
| Woot | 7 | src-media-theverge |
| Galaxy Z Fold | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Bose | 7 | src-media-theverge |
| IBM Research | 7 | src-hf-blog |
| YC S23 | 7 | src-hn-frontpage |
| Zelda | 7 | src-media-theverge |
| On Equity | 7 | src-media-techcrunch |
| Korea | 6 | src-nvidia-blog |
| Related | 6 | src-hn-frontpage |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
