---
generated_day: '2026-10-06'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**71 天**（2026-07-24 … 2026-10-06），去重後 **4729** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 136 | 2 |
| Apple | 103 | 5 |
| September | 58 | 8 |
| Amazon | 56 | 5 |
| LLMs | 52 | 13 |
| LLM | 48 | 12 |
| They | 46 | 9 |
| Here | 45 | 8 |
| There | 45 | 7 |
| Trump | 39 | 4 |
| One | 38 | 10 |
| Muse | 38 | 5 |
| Pro | 34 | 6 |
| CEO | 34 | 5 |
| When | 33 | 10 |
| July | 31 | 9 |
| U.S | 31 | 8 |
| AI-powered | 30 | 9 |
| October | 30 | 7 |
| June | 29 | 7 |
| Python | 29 | 4 |
| San Francisco | 28 | 9 |
| August | 28 | 8 |
| Android | 28 | 4 |
| Astra | 28 | 5 |
| Research | 27 | 6 |
| Linux | 27 | 5 |
| China | 26 | 8 |
| After | 26 | 6 |
| Last | 25 | 6 |
| Building | 24 | 10 |
| With | 24 | 10 |
| Learn | 23 | 5 |
| Rust | 23 | 3 |
| Pixel | 23 | 3 |
| Samsung | 21 | 5 |
| Opus | 20 | 5 |
| AI-generated | 20 | 7 |
| Wednesday | 19 | 4 |
| Chinese | 19 | 8 |
| These | 19 | 6 |
| Europe | 18 | 7 |
| API | 18 | 5 |
| Over | 18 | 4 |
| Flash | 17 | 5 |
| Tuesday | 17 | 6 |
| May | 17 | 7 |
| Mac | 17 | 4 |
| Fable | 17 | 5 |
| Elon Musk | 17 | 5 |
| SpaceX | 17 | 5 |
| RAM | 17 | 2 |
| The AI | 17 | 6 |
| Don | 17 | 5 |
| Industry | 16 | 2 |
| European Union | 16 | 3 |
| Thursday | 16 | 4 |
| India | 16 | 4 |
| Some | 16 | 8 |
| Windows | 16 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| TechCrunch Disrupt | 59 | src-media-techcrunch |
| The Download | 55 | src-media-mit-techreview |
| Tags | 31 | src-kol-simonwillison |
| Hi HN | 20 | src-hn-frontpage |
| Register | 20 | src-media-techcrunch |
| Highlights | 19 | src-gh-vllm-releases |
| MIT Technology Review | 19 | src-media-mit-techreview |
| Launch HN | 17 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Opt | 15 | src-media-theverge |
| Ask HN | 15 | src-hn-frontpage |
| Tool | 14 | src-kol-simonwillison |
| The Verge | 14 | src-media-theverge |
| Is Hiring | 14 | src-hn-frontpage |
| GeForce NOW | 12 | src-nvidia-blog |
| Best Buy | 12 | src-media-theverge |
| Hey HN | 12 | src-hn-frontpage |
| According | 11 | src-media-theverge |
| YC S26 | 11 | src-hn-frontpage |
| The Stepback | 10 | src-media-theverge |
| Datasette | 10 | src-kol-simonwillison |
| Disrupt | 10 | src-media-techcrunch |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| FCC | 8 | src-media-theverge |
| Netflix | 8 | src-media-theverge |
| Installer No | 8 | src-media-theverge |
| Verge-iest | 8 | src-media-theverge |
| Installer | 8 | src-media-theverge |
| Roundtables | 8 | src-media-mit-techreview |
| A Blog | 8 | src-hf-blog |
| Marvel | 7 | src-media-theverge |
| At TechCrunch Disrupt | 7 | src-media-techcrunch |
| The Algorithm | 7 | src-media-mit-techreview |
| Decoder | 7 | src-media-theverge |
| Startup Battlefield | 7 | src-media-techcrunch |
| October Prime Day | 7 | src-media-theverge |
| Sunday | 6 | src-media-theverge |
| Code | 6 | src-hn-frontpage |
| Open-source | 6 | src-hn-frontpage |
| Galaxy Z Fold | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Walmart | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| Series A | 6 | src-media-techcrunch |
| Verge | 6 | src-media-theverge |
| Victoria Song | 6 | src-media-theverge |
| VCs | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Woot | 5 | src-media-theverge |
| Nscale | 5 | src-media-techcrunch |
| AI Stage | 5 | src-media-techcrunch |
| PlayStation | 5 | src-media-theverge |
| Lenovo | 5 | src-media-theverge |
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
