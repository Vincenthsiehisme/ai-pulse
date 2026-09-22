---
generated_day: '2026-09-22'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**57 天**（2026-07-24 … 2026-09-22），去重後 **3849** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 92 | 5 |
| LLMs | 45 | 13 |
| September | 44 | 7 |
| LLM | 43 | 11 |
| Amazon | 42 | 5 |
| They | 39 | 9 |
| There | 39 | 7 |
| July | 31 | 9 |
| Here | 30 | 8 |
| One | 29 | 9 |
| Trump | 29 | 4 |
| When | 27 | 9 |
| Pro | 27 | 6 |
| August | 27 | 8 |
| Research | 26 | 6 |
| U.S | 26 | 7 |
| AI-powered | 25 | 9 |
| Python | 25 | 4 |
| June | 24 | 7 |
| Android | 23 | 4 |
| CEO | 22 | 5 |
| Astra | 22 | 5 |
| China | 21 | 6 |
| Linux | 21 | 5 |
| After | 21 | 6 |
| Building | 20 | 10 |
| San Francisco | 20 | 9 |
| Last | 20 | 6 |
| Pixel | 20 | 3 |
| Rust | 19 | 3 |
| Samsung | 19 | 4 |
| With | 18 | 9 |
| Europe | 17 | 7 |
| Wednesday | 17 | 4 |
| Industry | 16 | 2 |
| Learn | 16 | 5 |
| Fable | 16 | 5 |
| These | 16 | 6 |
| RAM | 16 | 2 |
| AI-generated | 16 | 6 |
| Flash | 15 | 5 |
| European Union | 15 | 3 |
| Some | 15 | 8 |
| May | 15 | 6 |
| Chinese | 15 | 7 |
| Elon Musk | 15 | 5 |
| SpaceX | 15 | 5 |
| The AI | 15 | 6 |
| Muse | 15 | 4 |
| Thursday | 14 | 4 |
| Tuesday | 14 | 5 |
| Opus | 14 | 5 |
| API | 14 | 5 |
| October | 14 | 5 |
| Over | 14 | 4 |
| India | 13 | 3 |
| Flock | 13 | 4 |
| While | 13 | 4 |
| Don | 13 | 5 |
| Monday | 12 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 105 | src-hn-frontpage |
| The Download | 45 | src-media-mit-techreview |
| TechCrunch Disrupt | 34 | src-media-techcrunch |
| Tags | 23 | src-kol-simonwillison |
| Highlights | 18 | src-gh-vllm-releases |
| Hi HN | 17 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Launch HN | 15 | src-hn-frontpage |
| MIT Technology Review | 13 | src-media-mit-techreview |
| The Verge | 12 | src-media-theverge |
| Opt | 11 | src-media-theverge |
| Ask HN | 11 | src-hn-frontpage |
| YC S26 | 11 | src-hn-frontpage |
| Best Buy | 11 | src-media-theverge |
| GeForce NOW | 10 | src-nvidia-blog |
| Is Hiring | 10 | src-hn-frontpage |
| Register | 10 | src-media-techcrunch |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Hey HN | 9 | src-hn-frontpage |
| Tool | 8 | src-kol-simonwillison |
| According | 8 | src-media-theverge |
| The Stepback | 8 | src-media-theverge |
| Bloomberg | 8 | src-media-theverge |
| Switch | 8 | src-media-theverge |
| Datasette | 8 | src-kol-simonwillison |
| Disrupt | 8 | src-media-techcrunch |
| Marvel | 7 | src-media-theverge |
| FCC | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| November | 7 | src-media-theverge |
| Roundtables | 7 | src-media-mit-techreview |
| The Algorithm | 6 | src-media-mit-techreview |
| Netflix | 6 | src-media-theverge |
| Galaxy Z Fold | 6 | src-media-theverge |
| Installer No | 6 | src-media-theverge |
| Verge-iest | 6 | src-media-theverge |
| Installer | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Valve | 6 | src-media-theverge |
| A Blog | 6 | src-hf-blog |
| Grand Theft Auto | 6 | src-media-theverge |
| Series A | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| At TechCrunch Disrupt | 5 | src-media-techcrunch |
| Lenovo | 5 | src-media-theverge |
| Innovators Under | 5 | src-media-mit-techreview |
| Self-hosted | 5 | src-hn-frontpage |
| Get | 5 | src-media-techcrunch |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Latest | 4 | src-kol-interconnects |
| Equity | 4 | src-media-techcrunch |
| Wall Street | 4 | src-media-techcrunch |
| Sunday | 4 | src-media-theverge |
| Peacock | 4 | src-media-theverge |
| RAMageddon | 4 | src-media-theverge |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
