---
generated_day: '2026-11-10'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**106 天**（2026-07-24 … 2026-11-10），去重後 **6976** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Show HN | 220 | 2 |
| Apple | 163 | 6 |
| Amazon | 104 | 5 |
| LLMs | 68 | 13 |
| September | 67 | 8 |
| Here | 65 | 9 |
| There | 65 | 9 |
| They | 61 | 9 |
| LLM | 60 | 12 |
| Muse | 55 | 6 |
| October | 53 | 8 |
| After | 51 | 6 |
| Trump | 50 | 5 |
| CEO | 50 | 5 |
| One | 49 | 10 |
| Pro | 49 | 8 |
| Python | 47 | 5 |
| U.S | 47 | 8 |
| San Francisco | 45 | 9 |
| When | 44 | 12 |
| AI-powered | 41 | 10 |
| Android | 40 | 4 |
| July | 39 | 9 |
| China | 39 | 8 |
| Linux | 39 | 6 |
| November | 39 | 6 |
| With | 38 | 10 |
| Last | 36 | 7 |
| Chinese | 35 | 8 |
| AI-generated | 35 | 9 |
| Windows | 35 | 5 |
| Rust | 34 | 3 |
| Astra | 34 | 6 |
| August | 33 | 8 |
| June | 32 | 7 |
| Research | 32 | 6 |
| These | 32 | 8 |
| IPO | 32 | 7 |
| Learn | 31 | 6 |
| Europe | 30 | 8 |
| Building | 29 | 12 |
| API | 29 | 6 |
| Samsung | 29 | 5 |
| Wednesday | 26 | 5 |
| Tuesday | 26 | 6 |
| Opus | 26 | 6 |
| Elon Musk | 26 | 5 |
| SpaceX | 26 | 5 |
| While | 26 | 4 |
| Pixel | 26 | 3 |
| Fable | 25 | 6 |
| Xbox | 25 | 2 |
| Thursday | 24 | 5 |
| Monday | 24 | 4 |
| Mac | 24 | 4 |
| According | 24 | 4 |
| YouTube | 24 | 7 |
| Duo | 24 | 3 |
| Flash | 23 | 6 |
| Tool | 23 | 2 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| The Download | 80 | src-media-mit-techreview |
| TechCrunch Disrupt | 77 | src-media-techcrunch |
| Tags | 42 | src-kol-simonwillison |
| Register | 32 | src-media-techcrunch |
| Hi HN | 30 | src-hn-frontpage |
| A Blog | 27 | src-hf-blog |
| Launch HN | 26 | src-hn-frontpage |
| MIT Technology Review | 24 | src-media-mit-techreview |
| Opt | 23 | src-media-theverge |
| The Verge | 22 | src-media-theverge |
| Best Buy | 22 | src-media-theverge |
| Highlights | 21 | src-gh-vllm-releases |
| Ask HN | 19 | src-hn-frontpage |
| Is Hiring | 18 | src-hn-frontpage |
| GeForce NOW | 17 | src-nvidia-blog |
| Committee | 15 | src-ep-itre |
| The Stepback | 15 | src-media-theverge |
| Hey HN | 15 | src-hn-frontpage |
| Datasette | 15 | src-kol-simonwillison |
| Installer No | 13 | src-media-theverge |
| Verge-iest | 13 | src-media-theverge |
| Installer | 13 | src-media-theverge |
| TechCrunch Founder Summit | 12 | src-media-techcrunch |
| The Algorithm | 11 | src-media-mit-techreview |
| YC S26 | 11 | src-hn-frontpage |
| Roundtables | 11 | src-media-mit-techreview |
| Disrupt | 11 | src-media-techcrunch |
| Sunday | 10 | src-media-theverge |
| FCC | 10 | src-media-theverge |
| Moscone West | 10 | src-media-techcrunch |
| October Prime Day | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| PlayStation | 9 | src-media-theverge |
| Reuters | 9 | src-media-theverge |
| Verge | 9 | src-media-theverge |
| Victoria Song | 9 | src-media-theverge |
| VCs | 9 | src-media-techcrunch |
| Startup Battlefield | 9 | src-media-techcrunch |
| At TechCrunch Disrupt | 8 | src-media-techcrunch |
| Open-source | 8 | src-hn-frontpage |
| Apple TV | 8 | src-media-theverge |
| Series A | 8 | src-media-techcrunch |
| Optimizer | 8 | src-media-theverge |
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

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
