---
generated_day: '2026-10-18'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**83 天**（2026-07-24 … 2026-10-18），去重後 **5472** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 166 | 2 |
| Apple | 123 | 5 |
| Amazon | 76 | 5 |
| September | 61 | 8 |
| LLMs | 55 | 13 |
| There | 55 | 7 |
| They | 52 | 9 |
| LLM | 52 | 12 |
| Here | 48 | 8 |
| October | 46 | 7 |
| Trump | 44 | 5 |
| One | 43 | 10 |
| Muse | 43 | 5 |
| San Francisco | 40 | 9 |
| CEO | 40 | 5 |
| Python | 38 | 4 |
| When | 37 | 11 |
| AI-powered | 36 | 10 |
| Pro | 36 | 7 |
| July | 34 | 9 |
| U.S | 34 | 8 |
| After | 33 | 6 |
| Linux | 32 | 5 |
| Last | 32 | 6 |
| Android | 32 | 4 |
| China | 31 | 8 |
| June | 30 | 7 |
| August | 30 | 8 |
| Astra | 30 | 5 |
| Research | 29 | 6 |
| AI-generated | 28 | 8 |
| With | 27 | 10 |
| Building | 25 | 10 |
| Rust | 25 | 3 |
| These | 25 | 7 |
| Windows | 25 | 5 |
| Learn | 24 | 6 |
| Pixel | 24 | 3 |
| Europe | 23 | 8 |
| Wednesday | 22 | 5 |
| API | 22 | 6 |
| Samsung | 22 | 5 |
| Over | 22 | 5 |
| Opus | 21 | 5 |
| Tuesday | 20 | 6 |
| Elon Musk | 20 | 5 |
| Flash | 19 | 5 |
| Mac | 19 | 4 |
| Chinese | 19 | 8 |
| Tool | 19 | 2 |
| SpaceX | 19 | 5 |
| While | 19 | 4 |
| RAM | 19 | 2 |
| The AI | 19 | 6 |
| Don | 19 | 5 |
| Thursday | 18 | 4 |
| Some | 18 | 8 |
| Fable | 18 | 5 |
| Xbox | 18 | 2 |
| Monday | 17 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| TechCrunch Disrupt | 76 | src-media-techcrunch |
| The Download | 63 | src-media-mit-techreview |
| Tags | 35 | src-kol-simonwillison |
| Register | 27 | src-media-techcrunch |
| Hi HN | 24 | src-hn-frontpage |
| MIT Technology Review | 22 | src-media-mit-techreview |
| Highlights | 20 | src-gh-vllm-releases |
| Launch HN | 19 | src-hn-frontpage |
| Opt | 18 | src-media-theverge |
| The Verge | 17 | src-media-theverge |
| Committee | 15 | src-ep-itre |
| Ask HN | 15 | src-hn-frontpage |
| Is Hiring | 15 | src-hn-frontpage |
| GeForce NOW | 14 | src-nvidia-blog |
| Best Buy | 13 | src-media-theverge |
| Hey HN | 13 | src-hn-frontpage |
| The Stepback | 12 | src-media-theverge |
| Datasette | 12 | src-kol-simonwillison |
| A Blog | 12 | src-hf-blog |
| YC S26 | 11 | src-hn-frontpage |
| Installer No | 10 | src-media-theverge |
| Verge-iest | 10 | src-media-theverge |
| Installer | 10 | src-media-theverge |
| Roundtables | 10 | src-media-mit-techreview |
| Disrupt | 10 | src-media-techcrunch |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| FCC | 9 | src-media-theverge |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Walmart | 8 | src-media-theverge |
| Startup Battlefield | 8 | src-media-techcrunch |
| Sunday | 7 | src-media-theverge |
| The Algorithm | 7 | src-media-mit-techreview |
| Apple TV | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Series A | 7 | src-media-techcrunch |
| Verge | 7 | src-media-theverge |
| Victoria Song | 7 | src-media-theverge |
| Join | 7 | src-media-techcrunch |
| Code | 6 | src-hn-frontpage |
| Open-source | 6 | src-hn-frontpage |
| Galaxy Z Fold | 6 | src-media-theverge |
| AI Stage | 6 | src-media-techcrunch |
| Spider-Man | 6 | src-media-theverge |
| Bose | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| The New York | 6 | src-media-theverge |
| Optimizer | 6 | src-media-theverge |
| VCs | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Zig | 5 | src-hn-frontpage |
| Woot | 5 | src-media-theverge |
| Nscale | 5 | src-media-techcrunch |
| PlayStation | 5 | src-media-theverge |
| Reuters | 5 | src-media-theverge |
| Real World AI | 5 | src-media-techcrunch |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
