---
generated_day: '2026-11-03'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**99 天**（2026-07-24 … 2026-11-03），去重後 **6537** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 204 | 2 |
| Apple | 155 | 6 |
| Amazon | 96 | 5 |
| September | 65 | 8 |
| LLMs | 65 | 13 |
| Here | 62 | 9 |
| There | 62 | 8 |
| They | 58 | 9 |
| LLM | 58 | 12 |
| October | 52 | 7 |
| Trump | 48 | 5 |
| Muse | 48 | 6 |
| Python | 46 | 5 |
| One | 46 | 10 |
| Pro | 46 | 8 |
| CEO | 45 | 5 |
| When | 42 | 11 |
| AI-powered | 41 | 10 |
| San Francisco | 41 | 9 |
| U.S | 40 | 8 |
| After | 40 | 6 |
| July | 39 | 9 |
| Android | 38 | 4 |
| Last | 36 | 7 |
| China | 35 | 8 |
| With | 35 | 10 |
| Linux | 35 | 5 |
| Astra | 34 | 6 |
| AI-generated | 32 | 8 |
| Windows | 32 | 5 |
| June | 31 | 7 |
| Research | 31 | 6 |
| August | 31 | 8 |
| Europe | 30 | 8 |
| Learn | 30 | 6 |
| Rust | 29 | 3 |
| These | 29 | 8 |
| November | 29 | 5 |
| Building | 27 | 11 |
| IPO | 27 | 7 |
| Wednesday | 26 | 5 |
| API | 26 | 6 |
| Samsung | 26 | 5 |
| Opus | 25 | 6 |
| SpaceX | 25 | 5 |
| Monday | 24 | 4 |
| Chinese | 24 | 8 |
| Elon Musk | 24 | 5 |
| Pixel | 24 | 3 |
| Xbox | 24 | 2 |
| Tuesday | 23 | 6 |
| While | 23 | 4 |
| YouTube | 23 | 7 |
| Thursday | 22 | 5 |
| Mac | 22 | 4 |
| Tool | 22 | 2 |
| Over | 22 | 5 |
| The AI | 22 | 7 |
| Can | 22 | 7 |
| Duo | 22 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| The Download | 75 | src-media-mit-techreview |
| Tags | 39 | src-kol-simonwillison |
| Register | 31 | src-media-techcrunch |
| Hi HN | 29 | src-hn-frontpage |
| Launch HN | 24 | src-hn-frontpage |
| MIT Technology Review | 24 | src-media-mit-techreview |
| A Blog | 24 | src-hf-blog |
| The Verge | 22 | src-media-theverge |
| Highlights | 21 | src-gh-vllm-releases |
| Opt | 21 | src-media-theverge |
| Best Buy | 19 | src-media-theverge |
| Ask HN | 18 | src-hn-frontpage |
| Is Hiring | 18 | src-hn-frontpage |
| GeForce NOW | 16 | src-nvidia-blog |
| Committee | 15 | src-ep-itre |
| Hey HN | 15 | src-hn-frontpage |
| The Stepback | 14 | src-media-theverge |
| Installer No | 12 | src-media-theverge |
| Verge-iest | 12 | src-media-theverge |
| Installer | 12 | src-media-theverge |
| Datasette | 12 | src-kol-simonwillison |
| YC S26 | 11 | src-hn-frontpage |
| Disrupt | 11 | src-media-techcrunch |
| TechCrunch Founder Summit | 11 | src-media-techcrunch |
| FCC | 10 | src-media-theverge |
| The Algorithm | 10 | src-media-mit-techreview |
| Roundtables | 10 | src-media-mit-techreview |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Sunday | 9 | src-media-theverge |
| VCs | 9 | src-media-techcrunch |
| Startup Battlefield | 9 | src-media-techcrunch |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Open-source | 8 | src-hn-frontpage |
| Apple TV | 8 | src-media-theverge |
| Reuters | 8 | src-media-theverge |
| Series A | 8 | src-media-techcrunch |
| Verge | 8 | src-media-theverge |
| Victoria Song | 8 | src-media-theverge |
| PlayStation | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| IBM Research | 7 | src-hf-blog |
| Grand Theft Auto | 7 | src-media-theverge |
| Optimizer | 7 | src-media-theverge |
| Join | 7 | src-media-techcrunch |
| Related | 6 | src-hn-frontpage |
| Code | 6 | src-hn-frontpage |
| Following | 6 | src-media-theverge |
| Galaxy Z Fold | 6 | src-media-theverge |
| AI Stage | 6 | src-media-techcrunch |
| Spider-Man | 6 | src-media-theverge |
| Bose | 6 | src-media-theverge |
| YC W24 | 6 | src-hn-frontpage |
| On Equity | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
