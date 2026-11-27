---
generated_day: '2026-11-27'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**121 天**（2026-07-24 … 2026-11-27），去重後 **8023** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 253 | 2 |
| Apple | 175 | 6 |
| Amazon | 126 | 5 |
| Here | 79 | 9 |
| Jensen Huang | 79 | 7 |
| LLMs | 74 | 14 |
| There | 74 | 10 |
| CEO | 73 | 7 |
| September | 71 | 8 |
| They | 68 | 9 |
| LLM | 68 | 13 |
| U.S | 63 | 8 |
| Trump | 62 | 5 |
| Muse | 62 | 6 |
| After | 59 | 6 |
| One | 57 | 10 |
| October | 57 | 8 |
| China | 55 | 9 |
| November | 55 | 7 |
| Python | 52 | 5 |
| Pro | 52 | 8 |
| With | 50 | 10 |
| When | 49 | 13 |
| San Francisco | 48 | 9 |
| AI-powered | 46 | 10 |
| Chinese | 46 | 8 |
| Rust | 46 | 3 |
| Linux | 46 | 6 |
| Android | 45 | 4 |
| Huang | 43 | 6 |
| July | 42 | 9 |
| IPO | 41 | 8 |
| AI-generated | 40 | 9 |
| Astra | 40 | 6 |
| Last | 39 | 7 |
| Windows | 38 | 6 |
| August | 36 | 8 |
| These | 35 | 8 |
| API | 35 | 6 |
| June | 33 | 7 |
| Research | 33 | 6 |
| Tuesday | 33 | 6 |
| Wednesday | 32 | 5 |
| Learn | 32 | 6 |
| Elon Musk | 32 | 5 |
| SpaceX | 32 | 7 |
| Monday | 31 | 6 |
| Building | 31 | 13 |
| While | 31 | 4 |
| Samsung | 31 | 5 |
| Friday | 31 | 4 |
| Europe | 30 | 8 |
| Fable | 29 | 8 |
| YouTube | 29 | 7 |
| Over | 28 | 7 |
| Thursday | 27 | 6 |
| Some | 27 | 8 |
| Mac | 27 | 4 |
| Pixel | 27 | 3 |
| Most | 26 | 9 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| The Download | 92 | src-media-mit-techreview |
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| Tags | 43 | src-kol-simonwillison |
| Hi HN | 35 | src-hn-frontpage |
| A Blog | 33 | src-hf-blog |
| Register | 32 | src-media-techcrunch |
| Launch HN | 31 | src-hn-frontpage |
| Best Buy | 29 | src-media-theverge |
| Opt | 27 | src-media-theverge |
| The Verge | 27 | src-media-theverge |
| Datasette | 26 | src-kol-simonwillison |
| MIT Technology Review | 25 | src-media-mit-techreview |
| Import AI | 22 | src-kol-importai |
| Highlights | 21 | src-gh-vllm-releases |
| Ask HN | 21 | src-hn-frontpage |
| Is Hiring | 21 | src-hn-frontpage |
| Hey HN | 20 | src-hn-frontpage |
| GeForce NOW | 19 | src-nvidia-blog |
| The Stepback | 17 | src-media-theverge |
| Committee | 15 | src-ep-itre |
| Installer No | 15 | src-media-theverge |
| Verge-iest | 15 | src-media-theverge |
| Installer | 15 | src-media-theverge |
| FCC | 13 | src-media-theverge |
| The Algorithm | 13 | src-media-mit-techreview |
| Roundtables | 13 | src-media-mit-techreview |
| Verge | 12 | src-media-theverge |
| Disrupt | 12 | src-media-techcrunch |
| TechCrunch Founder Summit | 12 | src-media-techcrunch |
| YC S26 | 11 | src-hn-frontpage |
| Apple TV | 11 | src-media-theverge |
| Victoria Song | 11 | src-media-theverge |
| VCs | 11 | src-media-techcrunch |
| PlayStation | 10 | src-media-theverge |
| Optimizer | 10 | src-media-theverge |
| Startup Battlefield | 10 | src-media-techcrunch |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Open-source | 9 | src-hn-frontpage |
| IBM Research | 9 | src-hf-blog |
| Series A | 9 | src-media-techcrunch |
| Nintendo Switch | 9 | src-media-theverge |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Code | 8 | src-hn-frontpage |
| Datasette Agent | 8 | src-kol-simonwillison |
| Wi-Fi | 8 | src-media-theverge |
| Zelda | 8 | src-media-theverge |
| Woot | 7 | src-media-theverge |
| Galaxy Z Fold | 7 | src-media-theverge |
| Spider-Man | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Bose | 7 | src-media-theverge |
| Rockstar Games | 7 | src-media-theverge |
| YC S23 | 7 | src-hn-frontpage |
| RCE | 7 | src-hn-frontpage |
| YC W24 | 7 | src-hn-frontpage |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
