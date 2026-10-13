---
generated_day: '2026-10-13'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**78 天**（2026-07-24 … 2026-10-13），去重後 **5163** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 153 | 2 |
| Apple | 112 | 5 |
| Amazon | 66 | 5 |
| September | 61 | 8 |
| LLMs | 53 | 13 |
| LLM | 51 | 12 |
| There | 51 | 7 |
| They | 50 | 9 |
| Here | 47 | 8 |
| One | 42 | 10 |
| Trump | 41 | 5 |
| October | 41 | 7 |
| Muse | 41 | 5 |
| San Francisco | 39 | 9 |
| CEO | 37 | 5 |
| When | 36 | 11 |
| Pro | 36 | 7 |
| Python | 35 | 4 |
| AI-powered | 34 | 9 |
| July | 32 | 9 |
| U.S | 32 | 8 |
| Android | 32 | 4 |
| After | 31 | 6 |
| China | 30 | 8 |
| June | 29 | 7 |
| Linux | 29 | 5 |
| August | 29 | 8 |
| Astra | 29 | 5 |
| Research | 27 | 6 |
| Last | 27 | 6 |
| With | 26 | 10 |
| Building | 25 | 10 |
| Rust | 24 | 3 |
| Pixel | 24 | 3 |
| AI-generated | 24 | 8 |
| Windows | 24 | 5 |
| Learn | 23 | 5 |
| These | 22 | 7 |
| Samsung | 22 | 5 |
| Opus | 21 | 5 |
| API | 21 | 6 |
| Europe | 20 | 7 |
| Wednesday | 20 | 5 |
| Over | 20 | 5 |
| Tuesday | 19 | 6 |
| Mac | 19 | 4 |
| Chinese | 19 | 8 |
| Don | 19 | 5 |
| Flash | 18 | 5 |
| Some | 18 | 8 |
| Elon Musk | 18 | 5 |
| SpaceX | 18 | 5 |
| RAM | 18 | 2 |
| Thursday | 17 | 4 |
| Monday | 17 | 4 |
| May | 17 | 7 |
| Fable | 17 | 5 |
| Xbox | 17 | 2 |
| The AI | 17 | 6 |
| Get | 17 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| TechCrunch Disrupt | 71 | src-media-techcrunch |
| The Download | 60 | src-media-mit-techreview |
| Tags | 34 | src-kol-simonwillison |
| Register | 25 | src-media-techcrunch |
| Hi HN | 22 | src-hn-frontpage |
| MIT Technology Review | 22 | src-media-mit-techreview |
| Highlights | 19 | src-gh-vllm-releases |
| Launch HN | 19 | src-hn-frontpage |
| The Verge | 17 | src-media-theverge |
| Opt | 16 | src-media-theverge |
| Committee | 15 | src-ep-itre |
| Ask HN | 15 | src-hn-frontpage |
| Is Hiring | 14 | src-hn-frontpage |
| GeForce NOW | 13 | src-nvidia-blog |
| Best Buy | 13 | src-media-theverge |
| Hey HN | 13 | src-hn-frontpage |
| Datasette | 12 | src-kol-simonwillison |
| The Stepback | 11 | src-media-theverge |
| YC S26 | 11 | src-hn-frontpage |
| A Blog | 11 | src-hf-blog |
| Disrupt | 10 | src-media-techcrunch |
| Moscone West | 10 | src-media-techcrunch |
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
| Startup Battlefield | 8 | src-media-techcrunch |
| Sunday | 7 | src-media-theverge |
| At TechCrunch Disrupt | 7 | src-media-techcrunch |
| The Algorithm | 7 | src-media-mit-techreview |
| Decoder | 7 | src-media-theverge |
| Walmart | 7 | src-media-theverge |
| Series A | 7 | src-media-techcrunch |
| Code | 6 | src-hn-frontpage |
| Open-source | 6 | src-hn-frontpage |
| Galaxy Z Fold | 6 | src-media-theverge |
| AI Stage | 6 | src-media-techcrunch |
| Spider-Man | 6 | src-media-theverge |
| Lenovo | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| The New York | 6 | src-media-theverge |
| Verge | 6 | src-media-theverge |
| Victoria Song | 6 | src-media-theverge |
| VCs | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Zig | 5 | src-hn-frontpage |
| Woot | 5 | src-media-theverge |
| Nscale | 5 | src-media-techcrunch |
| Apple TV | 5 | src-media-theverge |
| PlayStation | 5 | src-media-theverge |
| Reuters | 5 | src-media-theverge |
| Real World AI | 5 | src-media-techcrunch |
| Stage | 5 | src-media-techcrunch |
| Bose | 5 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
