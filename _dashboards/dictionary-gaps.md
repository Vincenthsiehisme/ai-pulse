---
generated_day: '2026-09-16'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**51 天**（2026-07-24 … 2026-09-16），去重後 **3458** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| Apple | 84 | 5 |
| LLMs | 41 | 12 |
| Amazon | 39 | 5 |
| LLM | 36 | 11 |
| There | 36 | 7 |
| They | 33 | 9 |
| July | 30 | 9 |
| Here | 30 | 8 |
| September | 27 | 6 |
| One | 27 | 9 |
| Research | 26 | 6 |
| August | 26 | 8 |
| Python | 24 | 4 |
| U.S | 24 | 7 |
| When | 24 | 9 |
| Pro | 24 | 6 |
| Trump | 23 | 4 |
| AI-powered | 22 | 9 |
| June | 22 | 7 |
| Android | 21 | 4 |
| Pixel | 20 | 3 |
| CEO | 20 | 5 |
| Building | 19 | 10 |
| China | 19 | 6 |
| Linux | 19 | 5 |
| Astra | 19 | 5 |
| With | 18 | 9 |
| Rust | 18 | 3 |
| After | 18 | 6 |
| Samsung | 18 | 4 |
| Europe | 17 | 7 |
| Wednesday | 17 | 4 |
| San Francisco | 17 | 9 |
| Industry | 16 | 2 |
| European Union | 15 | 3 |
| Some | 15 | 8 |
| Elon Musk | 15 | 5 |
| SpaceX | 15 | 5 |
| Last | 15 | 6 |
| Flash | 14 | 4 |
| Fable | 14 | 4 |
| These | 14 | 6 |
| RAM | 14 | 2 |
| AI-generated | 14 | 5 |
| The AI | 14 | 5 |
| Thursday | 13 | 4 |
| API | 13 | 5 |
| While | 13 | 4 |
| Over | 13 | 4 |
| Tuesday | 12 | 5 |
| Monday | 12 | 4 |
| Learn | 12 | 4 |
| India | 12 | 3 |
| May | 12 | 5 |
| Opus | 12 | 4 |
| OpenRouter | 12 | 4 |
| Duo | 12 | 3 |
| Draft | 11 | 2 |
| Texas | 11 | 6 |
| Flock | 11 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 95 | src-hn-frontpage |
| The Download | 41 | src-media-mit-techreview |
| Tags | 20 | src-kol-simonwillison |
| TechCrunch Disrupt | 19 | src-media-techcrunch |
| Highlights | 17 | src-gh-vllm-releases |
| Hi HN | 16 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Launch HN | 13 | src-hn-frontpage |
| YC S26 | 11 | src-hn-frontpage |
| Opt | 10 | src-media-theverge |
| Ask HN | 10 | src-hn-frontpage |
| The Verge | 10 | src-media-theverge |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| GeForce NOW | 9 | src-nvidia-blog |
| Best Buy | 9 | src-media-theverge |
| Tool | 8 | src-kol-simonwillison |
| Switch | 8 | src-media-theverge |
| MIT Technology Review | 8 | src-media-mit-techreview |
| Is Hiring | 8 | src-hn-frontpage |
| According | 7 | src-media-theverge |
| Marvel | 7 | src-media-theverge |
| The Stepback | 7 | src-media-theverge |
| November | 7 | src-media-theverge |
| FCC | 6 | src-media-theverge |
| The Algorithm | 6 | src-media-mit-techreview |
| Bloomberg | 6 | src-media-theverge |
| Galaxy Z Fold | 6 | src-media-theverge |
| Spider-Man | 6 | src-media-theverge |
| Decoder | 6 | src-media-theverge |
| Datasette | 6 | src-kol-simonwillison |
| Valve | 6 | src-media-theverge |
| Grand Theft Auto | 6 | src-media-theverge |
| Series A | 6 | src-media-techcrunch |
| Co-Scientist | 5 | src-deepmind-blog |
| Netflix | 5 | src-media-theverge |
| Installer No | 5 | src-media-theverge |
| Verge-iest | 5 | src-media-theverge |
| Installer | 5 | src-media-theverge |
| Hey HN | 5 | src-hn-frontpage |
| Innovators Under | 5 | src-media-mit-techreview |
| A Blog | 5 | src-hf-blog |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Mathematics | 4 | src-hn-frontpage |
| Latest | 4 | src-kol-interconnects |
| Equity | 4 | src-media-techcrunch |
| Sunday | 4 | src-media-theverge |
| At TechCrunch Disrupt | 4 | src-media-techcrunch |
| Peacock | 4 | src-media-theverge |
| RAMageddon | 4 | src-media-theverge |
| Zig | 4 | src-hn-frontpage |
| Woot | 4 | src-media-theverge |
| Sure | 4 | src-media-theverge |
| Disney | 4 | src-media-theverge |
| Self-hosted | 4 | src-hn-frontpage |
| Roundtables | 4 | src-media-mit-techreview |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
