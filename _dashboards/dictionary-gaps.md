---
generated_day: '2026-09-30'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**65 天**（2026-07-24 … 2026-09-30），去重後 **4379** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 96 | 5 |
| September | 54 | 7 |
| LLMs | 49 | 13 |
| Amazon | 46 | 5 |
| LLM | 45 | 11 |
| They | 44 | 9 |
| There | 42 | 7 |
| Here | 36 | 8 |
| One | 35 | 10 |
| Trump | 34 | 4 |
| Pro | 33 | 6 |
| Muse | 33 | 5 |
| July | 31 | 9 |
| U.S | 30 | 8 |
| When | 30 | 9 |
| AI-powered | 29 | 9 |
| Astra | 28 | 5 |
| June | 27 | 7 |
| Python | 27 | 4 |
| CEO | 27 | 5 |
| August | 27 | 8 |
| Research | 26 | 6 |
| San Francisco | 26 | 9 |
| China | 24 | 7 |
| After | 24 | 6 |
| Android | 24 | 4 |
| Last | 23 | 6 |
| Pixel | 23 | 3 |
| Building | 22 | 10 |
| Linux | 22 | 5 |
| With | 21 | 10 |
| October | 21 | 7 |
| Learn | 20 | 5 |
| Samsung | 20 | 5 |
| Wednesday | 19 | 4 |
| Rust | 19 | 3 |
| Opus | 18 | 5 |
| These | 18 | 6 |
| AI-generated | 18 | 7 |
| Europe | 17 | 7 |
| Tuesday | 17 | 6 |
| Fable | 17 | 5 |
| Flash | 16 | 5 |
| Industry | 16 | 2 |
| India | 16 | 4 |
| May | 16 | 7 |
| Chinese | 16 | 8 |
| API | 16 | 5 |
| Elon Musk | 16 | 5 |
| RAM | 16 | 2 |
| Over | 16 | 4 |
| Xbox | 16 | 2 |
| The AI | 16 | 6 |
| European Union | 15 | 3 |
| Monday | 15 | 4 |
| Some | 15 | 8 |
| Mac | 15 | 4 |
| SpaceX | 15 | 5 |
| Windows | 15 | 3 |
| Don | 15 | 5 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 124 | src-hn-frontpage |
| The Download | 51 | src-media-mit-techreview |
| TechCrunch Disrupt | 50 | src-media-techcrunch |
| Tags | 30 | src-kol-simonwillison |
| Hi HN | 19 | src-hn-frontpage |
| Highlights | 18 | src-gh-vllm-releases |
| Launch HN | 17 | src-hn-frontpage |
| MIT Technology Review | 16 | src-media-mit-techreview |
| Committee | 15 | src-ep-itre |
| Register | 15 | src-media-techcrunch |
| Opt | 14 | src-media-theverge |
| Tool | 13 | src-kol-simonwillison |
| Ask HN | 13 | src-hn-frontpage |
| The Verge | 12 | src-media-theverge |
| Hey HN | 12 | src-hn-frontpage |
| Is Hiring | 12 | src-hn-frontpage |
| GeForce NOW | 11 | src-nvidia-blog |
| According | 11 | src-media-theverge |
| YC S26 | 11 | src-hn-frontpage |
| Best Buy | 11 | src-media-theverge |
| Disrupt | 10 | src-media-techcrunch |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| The Stepback | 9 | src-media-theverge |
| Datasette | 9 | src-kol-simonwillison |
| Roundtables | 8 | src-media-mit-techreview |
| Get | 8 | src-media-techcrunch |
| Marvel | 7 | src-media-theverge |
| At TechCrunch Disrupt | 7 | src-media-techcrunch |
| FCC | 7 | src-media-theverge |
| The Algorithm | 7 | src-media-mit-techreview |
| Installer No | 7 | src-media-theverge |
| Verge-iest | 7 | src-media-theverge |
| Installer | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| A Blog | 7 | src-hf-blog |
| Code | 6 | src-hn-frontpage |
| Netflix | 6 | src-media-theverge |
| Galaxy Z Fold | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Valve | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| Series A | 6 | src-media-techcrunch |
| Victoria Song | 6 | src-media-theverge |
| VCs | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Sunday | 5 | src-media-theverge |
| Woot | 5 | src-media-theverge |
| Nscale | 5 | src-media-techcrunch |
| Lenovo | 5 | src-media-theverge |
| Real World AI | 5 | src-media-techcrunch |
| Stage | 5 | src-media-techcrunch |
| Bose | 5 | src-media-theverge |
| Innovators Under | 5 | src-media-mit-techreview |
| Self-hosted | 5 | src-hn-frontpage |
| Walmart | 5 | src-media-theverge |
| Optimizer | 5 | src-media-theverge |
| Verge | 5 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
