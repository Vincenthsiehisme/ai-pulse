---
generated_day: '2026-10-02'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**67 天**（2026-07-24 … 2026-10-02），去重後 **4509** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 98 | 5 |
| September | 55 | 7 |
| LLMs | 51 | 13 |
| Amazon | 46 | 5 |
| LLM | 46 | 11 |
| They | 44 | 9 |
| There | 44 | 7 |
| One | 38 | 10 |
| Trump | 37 | 4 |
| Here | 36 | 8 |
| Pro | 34 | 6 |
| Muse | 34 | 5 |
| July | 31 | 9 |
| When | 31 | 9 |
| CEO | 31 | 5 |
| AI-powered | 30 | 9 |
| U.S | 30 | 8 |
| Python | 28 | 4 |
| August | 28 | 8 |
| Android | 28 | 4 |
| Astra | 28 | 5 |
| June | 27 | 7 |
| San Francisco | 27 | 9 |
| Research | 26 | 6 |
| China | 25 | 8 |
| Last | 25 | 6 |
| October | 25 | 7 |
| After | 25 | 6 |
| With | 24 | 10 |
| Pixel | 23 | 3 |
| Building | 22 | 10 |
| Linux | 22 | 5 |
| Learn | 21 | 5 |
| Rust | 20 | 3 |
| Samsung | 20 | 5 |
| Wednesday | 19 | 4 |
| Opus | 19 | 5 |
| AI-generated | 19 | 7 |
| These | 18 | 6 |
| Flash | 17 | 5 |
| Europe | 17 | 7 |
| Tuesday | 17 | 6 |
| Fable | 17 | 5 |
| Elon Musk | 17 | 5 |
| SpaceX | 17 | 5 |
| Don | 17 | 5 |
| Industry | 16 | 2 |
| India | 16 | 4 |
| May | 16 | 7 |
| Mac | 16 | 4 |
| Chinese | 16 | 8 |
| API | 16 | 5 |
| RAM | 16 | 2 |
| Over | 16 | 4 |
| Xbox | 16 | 2 |
| The AI | 16 | 6 |
| Security | 15 | 8 |
| European Union | 15 | 3 |
| Thursday | 15 | 4 |
| Monday | 15 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 127 | src-hn-frontpage |
| TechCrunch Disrupt | 54 | src-media-techcrunch |
| The Download | 53 | src-media-mit-techreview |
| Tags | 30 | src-kol-simonwillison |
| Hi HN | 20 | src-hn-frontpage |
| Highlights | 18 | src-gh-vllm-releases |
| Launch HN | 17 | src-hn-frontpage |
| Register | 17 | src-media-techcrunch |
| MIT Technology Review | 16 | src-media-mit-techreview |
| Committee | 15 | src-ep-itre |
| Ask HN | 15 | src-hn-frontpage |
| Opt | 14 | src-media-theverge |
| Tool | 13 | src-kol-simonwillison |
| The Verge | 13 | src-media-theverge |
| Is Hiring | 13 | src-hn-frontpage |
| GeForce NOW | 12 | src-nvidia-blog |
| Hey HN | 12 | src-hn-frontpage |
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
| Marvel | 7 | src-media-theverge |
| At TechCrunch Disrupt | 7 | src-media-techcrunch |
| FCC | 7 | src-media-theverge |
| The Algorithm | 7 | src-media-mit-techreview |
| Installer No | 7 | src-media-theverge |
| Verge-iest | 7 | src-media-theverge |
| Installer | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Valve | 7 | src-media-theverge |
| A Blog | 7 | src-hf-blog |
| Code | 6 | src-hn-frontpage |
| Netflix | 6 | src-media-theverge |
| Open-source | 6 | src-hn-frontpage |
| Galaxy Z Fold | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| Series A | 6 | src-media-techcrunch |
| Victoria Song | 6 | src-media-theverge |
| VCs | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Sunday | 5 | src-media-theverge |
| Woot | 5 | src-media-theverge |
| Nscale | 5 | src-media-techcrunch |
| AI Stage | 5 | src-media-techcrunch |
| Lenovo | 5 | src-media-theverge |
| Real World AI | 5 | src-media-techcrunch |
| Stage | 5 | src-media-techcrunch |
| Bose | 5 | src-media-theverge |
| Innovators Under | 5 | src-media-mit-techreview |
| Self-hosted | 5 | src-hn-frontpage |
| Walmart | 5 | src-media-theverge |
| Optimizer | 5 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
