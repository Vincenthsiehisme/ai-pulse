---
generated_day: '2026-09-21'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**56 天**（2026-07-24 … 2026-09-21），去重後 **3777** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 88 | 5 |
| LLMs | 45 | 13 |
| Amazon | 41 | 5 |
| LLM | 40 | 11 |
| September | 39 | 7 |
| They | 39 | 9 |
| There | 38 | 7 |
| July | 30 | 9 |
| Here | 30 | 8 |
| One | 28 | 9 |
| When | 27 | 9 |
| Pro | 27 | 6 |
| Trump | 27 | 4 |
| August | 27 | 8 |
| Research | 26 | 6 |
| U.S | 26 | 7 |
| AI-powered | 25 | 9 |
| June | 24 | 7 |
| Python | 24 | 4 |
| Android | 23 | 4 |
| CEO | 22 | 5 |
| China | 21 | 6 |
| Building | 20 | 10 |
| Linux | 20 | 5 |
| Pixel | 20 | 3 |
| After | 20 | 6 |
| Astra | 20 | 5 |
| Rust | 19 | 3 |
| Last | 19 | 6 |
| Samsung | 19 | 4 |
| San Francisco | 18 | 9 |
| With | 18 | 9 |
| Europe | 17 | 7 |
| Wednesday | 17 | 4 |
| Industry | 16 | 2 |
| Learn | 16 | 5 |
| These | 16 | 6 |
| RAM | 16 | 2 |
| Flash | 15 | 5 |
| European Union | 15 | 3 |
| Some | 15 | 8 |
| May | 15 | 6 |
| Fable | 15 | 4 |
| Chinese | 15 | 7 |
| Elon Musk | 15 | 5 |
| SpaceX | 15 | 5 |
| AI-generated | 15 | 6 |
| The AI | 15 | 6 |
| Thursday | 14 | 4 |
| Over | 14 | 4 |
| India | 13 | 3 |
| Flock | 13 | 4 |
| API | 13 | 5 |
| October | 13 | 5 |
| While | 13 | 4 |
| Muse | 13 | 3 |
| Tuesday | 12 | 5 |
| Monday | 12 | 4 |
| Opus | 12 | 4 |
| Mac | 12 | 4 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 102 | src-hn-frontpage |
| The Download | 44 | src-media-mit-techreview |
| TechCrunch Disrupt | 30 | src-media-techcrunch |
| Tags | 23 | src-kol-simonwillison |
| Highlights | 17 | src-gh-vllm-releases |
| Hi HN | 16 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Launch HN | 14 | src-hn-frontpage |
| The Verge | 12 | src-media-theverge |
| MIT Technology Review | 12 | src-media-mit-techreview |
| Opt | 11 | src-media-theverge |
| Ask HN | 11 | src-hn-frontpage |
| YC S26 | 11 | src-hn-frontpage |
| GeForce NOW | 10 | src-nvidia-blog |
| Best Buy | 10 | src-media-theverge |
| Is Hiring | 10 | src-hn-frontpage |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| Tool | 8 | src-kol-simonwillison |
| According | 8 | src-media-theverge |
| The Stepback | 8 | src-media-theverge |
| Switch | 8 | src-media-theverge |
| Datasette | 8 | src-kol-simonwillison |
| Disrupt | 8 | src-media-techcrunch |
| Marvel | 7 | src-media-theverge |
| FCC | 7 | src-media-theverge |
| Bloomberg | 7 | src-media-theverge |
| Decoder | 7 | src-media-theverge |
| Hey HN | 7 | src-hn-frontpage |
| November | 7 | src-media-theverge |
| Register | 7 | src-media-techcrunch |
| The Algorithm | 6 | src-media-mit-techreview |
| Netflix | 6 | src-media-theverge |
| Galaxy Z Fold | 6 | src-media-theverge |
| Installer No | 6 | src-media-theverge |
| Verge-iest | 6 | src-media-theverge |
| Installer | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Valve | 6 | src-media-theverge |
| Roundtables | 6 | src-media-mit-techreview |
| A Blog | 6 | src-hf-blog |
| Grand Theft Auto | 6 | src-media-theverge |
| Series A | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Lenovo | 5 | src-media-theverge |
| Innovators Under | 5 | src-media-mit-techreview |
| Self-hosted | 5 | src-hn-frontpage |
| Get | 5 | src-media-techcrunch |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Latest | 4 | src-kol-interconnects |
| Equity | 4 | src-media-techcrunch |
| Sunday | 4 | src-media-theverge |
| At TechCrunch Disrupt | 4 | src-media-techcrunch |
| Peacock | 4 | src-media-theverge |
| RAMageddon | 4 | src-media-theverge |
| Zig | 4 | src-hn-frontpage |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
