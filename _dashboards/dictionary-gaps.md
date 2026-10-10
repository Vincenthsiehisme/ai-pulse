---
generated_day: '2026-10-10'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**75 天**（2026-07-24 … 2026-10-10），去重後 **4986** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 145 | 2 |
| Apple | 106 | 5 |
| Amazon | 63 | 5 |
| September | 61 | 8 |
| LLMs | 53 | 13 |
| They | 49 | 9 |
| There | 49 | 7 |
| LLM | 48 | 12 |
| Here | 46 | 8 |
| Muse | 41 | 5 |
| Trump | 40 | 5 |
| One | 39 | 10 |
| October | 39 | 7 |
| When | 35 | 11 |
| San Francisco | 34 | 9 |
| Pro | 34 | 6 |
| CEO | 34 | 5 |
| AI-powered | 31 | 9 |
| July | 31 | 9 |
| Python | 31 | 4 |
| U.S | 31 | 8 |
| June | 29 | 7 |
| Linux | 29 | 5 |
| After | 29 | 6 |
| August | 29 | 8 |
| Android | 29 | 4 |
| Astra | 29 | 5 |
| Research | 27 | 6 |
| China | 27 | 8 |
| Last | 26 | 6 |
| Building | 25 | 10 |
| With | 25 | 10 |
| Pixel | 24 | 3 |
| Windows | 24 | 5 |
| Learn | 23 | 5 |
| Rust | 23 | 3 |
| AI-generated | 22 | 8 |
| Samsung | 22 | 5 |
| Opus | 21 | 5 |
| Wednesday | 20 | 5 |
| These | 20 | 6 |
| Europe | 19 | 7 |
| Chinese | 19 | 8 |
| API | 19 | 5 |
| Over | 19 | 5 |
| Flash | 18 | 5 |
| Tuesday | 18 | 6 |
| Some | 18 | 8 |
| RAM | 18 | 2 |
| Don | 18 | 5 |
| Thursday | 17 | 4 |
| May | 17 | 7 |
| Mac | 17 | 4 |
| Fable | 17 | 5 |
| Elon Musk | 17 | 5 |
| SpaceX | 17 | 5 |
| The AI | 17 | 6 |
| Get | 17 | 4 |
| Industry | 16 | 2 |
| European Union | 16 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| TechCrunch Disrupt | 66 | src-media-techcrunch |
| The Download | 58 | src-media-mit-techreview |
| Tags | 33 | src-kol-simonwillison |
| Register | 23 | src-media-techcrunch |
| Hi HN | 21 | src-hn-frontpage |
| MIT Technology Review | 21 | src-media-mit-techreview |
| Highlights | 19 | src-gh-vllm-releases |
| Launch HN | 17 | src-hn-frontpage |
| The Verge | 17 | src-media-theverge |
| Committee | 15 | src-ep-itre |
| Opt | 15 | src-media-theverge |
| Ask HN | 15 | src-hn-frontpage |
| Tool | 14 | src-kol-simonwillison |
| Is Hiring | 14 | src-hn-frontpage |
| GeForce NOW | 13 | src-nvidia-blog |
| Best Buy | 13 | src-media-theverge |
| Hey HN | 12 | src-hn-frontpage |
| YC S26 | 11 | src-hn-frontpage |
| Datasette | 11 | src-kol-simonwillison |
| A Blog | 11 | src-hf-blog |
| The Stepback | 10 | src-media-theverge |
| Disrupt | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| FCC | 9 | src-media-theverge |
| Installer No | 9 | src-media-theverge |
| Verge-iest | 9 | src-media-theverge |
| Installer | 9 | src-media-theverge |
| Roundtables | 9 | src-media-mit-techreview |
| Marvel | 7 | src-media-theverge |
| At TechCrunch Disrupt | 7 | src-media-techcrunch |
| The Algorithm | 7 | src-media-mit-techreview |
| Decoder | 7 | src-media-theverge |
| Walmart | 7 | src-media-theverge |
| Series A | 7 | src-media-techcrunch |
| Startup Battlefield | 7 | src-media-techcrunch |
| Moscone West | 7 | src-media-techcrunch |
| Sunday | 6 | src-media-theverge |
| Code | 6 | src-hn-frontpage |
| Open-source | 6 | src-hn-frontpage |
| Galaxy Z Fold | 6 | src-media-theverge |
| AI Stage | 6 | src-media-techcrunch |
| Spider-Man | 6 | src-media-theverge |
| Lenovo | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| Verge | 6 | src-media-theverge |
| Victoria Song | 6 | src-media-theverge |
| VCs | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Woot | 5 | src-media-theverge |
| Nscale | 5 | src-media-techcrunch |
| PlayStation | 5 | src-media-theverge |
| Reuters | 5 | src-media-theverge |
| Real World AI | 5 | src-media-techcrunch |
| Stage | 5 | src-media-techcrunch |
| Bose | 5 | src-media-theverge |
| Innovators Under | 5 | src-media-mit-techreview |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
