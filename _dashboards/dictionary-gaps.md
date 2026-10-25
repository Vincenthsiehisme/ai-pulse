---
generated_day: '2026-10-25'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**90 天**（2026-07-24 … 2026-10-25），去重後 **5954** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 183 | 2 |
| Apple | 130 | 6 |
| Amazon | 86 | 5 |
| September | 61 | 8 |
| LLMs | 58 | 13 |
| There | 57 | 7 |
| They | 55 | 9 |
| LLM | 55 | 12 |
| Here | 52 | 8 |
| October | 50 | 7 |
| Muse | 48 | 6 |
| Trump | 45 | 5 |
| One | 43 | 10 |
| Python | 42 | 5 |
| Pro | 42 | 8 |
| San Francisco | 41 | 9 |
| CEO | 40 | 5 |
| AI-powered | 39 | 10 |
| When | 39 | 11 |
| July | 38 | 9 |
| U.S | 36 | 8 |
| After | 36 | 6 |
| Android | 35 | 4 |
| China | 33 | 8 |
| Linux | 33 | 5 |
| Last | 33 | 6 |
| Astra | 32 | 6 |
| June | 31 | 7 |
| With | 31 | 10 |
| Research | 30 | 6 |
| AI-generated | 30 | 8 |
| August | 30 | 8 |
| Rust | 29 | 3 |
| Europe | 28 | 8 |
| Learn | 28 | 6 |
| Windows | 27 | 5 |
| These | 26 | 7 |
| Building | 25 | 10 |
| Samsung | 25 | 5 |
| SpaceX | 24 | 5 |
| Pixel | 24 | 3 |
| Opus | 23 | 6 |
| API | 23 | 6 |
| Wednesday | 22 | 5 |
| Elon Musk | 22 | 5 |
| Over | 22 | 5 |
| Xbox | 22 | 2 |
| Flash | 21 | 6 |
| Tuesday | 21 | 6 |
| Chinese | 21 | 8 |
| Tool | 21 | 2 |
| The AI | 21 | 6 |
| Some | 20 | 8 |
| While | 20 | 4 |
| RAM | 20 | 2 |
| Thursday | 19 | 4 |
| Mac | 19 | 4 |
| Fable | 19 | 5 |
| Don | 19 | 5 |
| Duo | 19 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| The Download | 68 | src-media-mit-techreview |
| Tags | 38 | src-kol-simonwillison |
| Hi HN | 27 | src-hn-frontpage |
| Register | 27 | src-media-techcrunch |
| MIT Technology Review | 24 | src-media-mit-techreview |
| Launch HN | 22 | src-hn-frontpage |
| Highlights | 20 | src-gh-vllm-releases |
| The Verge | 20 | src-media-theverge |
| Opt | 19 | src-media-theverge |
| A Blog | 19 | src-hf-blog |
| Ask HN | 17 | src-hn-frontpage |
| Is Hiring | 17 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| GeForce NOW | 15 | src-nvidia-blog |
| Best Buy | 15 | src-media-theverge |
| Hey HN | 14 | src-hn-frontpage |
| The Stepback | 13 | src-media-theverge |
| Datasette | 12 | src-kol-simonwillison |
| YC S26 | 11 | src-hn-frontpage |
| Installer No | 11 | src-media-theverge |
| Verge-iest | 11 | src-media-theverge |
| Installer | 11 | src-media-theverge |
| Disrupt | 11 | src-media-techcrunch |
| Roundtables | 10 | src-media-mit-techreview |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| FCC | 9 | src-media-theverge |
| Startup Battlefield | 9 | src-media-techcrunch |
| Sunday | 8 | src-media-theverge |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| The Algorithm | 8 | src-media-mit-techreview |
| Apple TV | 8 | src-media-theverge |
| Open-source | 7 | src-hn-frontpage |
| PlayStation | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Grand Theft Auto | 7 | src-media-theverge |
| Series A | 7 | src-media-techcrunch |
| Verge | 7 | src-media-theverge |
| Victoria Song | 7 | src-media-theverge |
| Join | 7 | src-media-techcrunch |
| VCs | 7 | src-media-techcrunch |
| Related | 6 | src-hn-frontpage |
| Code | 6 | src-hn-frontpage |
| Galaxy Z Fold | 6 | src-media-theverge |
| AI Stage | 6 | src-media-techcrunch |
| Reuters | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Bose | 6 | src-media-theverge |
| IBM Research | 6 | src-hf-blog |
| The New York | 6 | src-media-theverge |
| Optimizer | 6 | src-media-theverge |
| Co-Scientist | 5 | src-deepmind-blog |
| Latest | 5 | src-kol-interconnects |
| Equity | 5 | src-media-techcrunch |
| Zig | 5 | src-hn-frontpage |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
