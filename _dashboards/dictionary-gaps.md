---
generated_day: '2026-08-01'
generator: scripts/pulse-dictionary-gaps.py
---

# 字典補漏候選（跨天累積）

語料範圍：**9 天**（2026-07-24 … 2026-08-01），去重後 **941** 列。
晉升門檻：跨 ≥2 來源、≥3 次（`gate.yaml` 的 `clustering.unknown_entity`，與 `_probe/<日>/report.md`
的當班區塊讀同一份）。

**這一頁不會自己改字典。** 它只是把「機器一直看到、字典裡卻沒有」的詞
累積起來給人看。要不要收，是人的決定——收錄邊界見
`_config/entities.yaml` 的 `meta`。

## 達標候選

| 候選 | 次數 | 來源數 |
|---|---|---|
| LLMs | 20 | 9 |
| Industry | 16 | 2 |
| Research | 16 | 2 |
| July | 14 | 7 |
| LLM | 13 | 8 |
| June | 12 | 6 |
| Building | 11 | 8 |
| Here | 11 | 7 |
| Union | 10 | 2 |
| Energy | 9 | 2 |
| U.S | 9 | 4 |
| One | 9 | 6 |
| Thursday | 8 | 3 |
| Amazon | 8 | 3 |
| Apple | 8 | 3 |
| Wednesday | 6 | 2 |
| Security | 6 | 3 |
| Tuesday | 6 | 4 |
| Monday | 6 | 4 |
| Gemma | 6 | 5 |
| Learn | 6 | 3 |
| When | 6 | 4 |
| Pro | 6 | 4 |
| Trump | 6 | 4 |
| There | 6 | 5 |
| Source | 5 | 2 |
| Python | 5 | 3 |
| Understanding | 5 | 3 |
| San Francisco | 5 | 4 |
| Power | 5 | 5 |
| China | 5 | 4 |
| Models | 5 | 4 |
| Learning | 5 | 3 |
| With | 5 | 5 |
| January | 5 | 4 |
| Opus | 5 | 3 |
| Fable | 5 | 3 |
| Advancing | 5 | 3 |
| AI-native | 5 | 3 |
| These | 5 | 3 |
| SpaceX | 5 | 3 |
| RAM | 5 | 2 |
| Flash | 4 | 2 |
| Making | 4 | 4 |
| Updated | 4 | 2 |
| Part | 4 | 3 |
| They | 4 | 3 |
| Anatomy | 4 | 4 |
| Built | 4 | 2 |
| American | 4 | 4 |
| Plus | 4 | 4 |
| Cybersecurity | 4 | 4 |
| Mythos | 4 | 4 |
| Some | 4 | 4 |
| However | 4 | 3 |
| Let | 4 | 3 |
| Mac | 4 | 3 |
| Chinese | 4 | 3 |
| Rust | 4 | 2 |
| Word | 4 | 3 |

## 單來源高頻（觀察用，不列入晉升）

冷啟階段來源少、詞彙不重疊時，「跨多來源」門檻結構上難以成立，
上面那張表會永遠是空的——看起來機制在跑，實際永遠不輸出。
這一區讓收割機制在那個階段也看得見，**但它不是一份比較寬鬆的晉升清單**，
是一份觀察清單，不得直接寫進字典。

| 候選 | 次數 | 唯一來源 |
|---|---|---|
| Show HN | 21 | src-hn-frontpage |
| Committee | 15 | src-ep-itre |
| Highlights | 14 | src-gh-vllm-releases |
| European Union | 12 | src-ep-itre |
| Draft | 10 | src-ep-itre |
| AMENDMENTS | 9 | src-ep-itre |
| Establishing | 9 | src-ep-itre |
| Regulations | 9 | src-ep-itre |
| European Biotech Act | 9 | src-ep-itre |
| The Download | 9 | src-media-mit-techreview |
| Qwen | 8 | src-qwen-blog |
| Minutes | 7 | src-ep-itre |
| Co-Scientist | 5 | src-deepmind-blog |
| Energy Source | 4 | src-ep-itre |
| Internal Market | 4 | src-ep-itre |
| Consumer Protection | 4 | src-ep-itre |
| Release Notes | 4 | src-gh-vllm-releases |
| Hi HN | 4 | src-hn-frontpage |
| Tags | 4 | src-kol-simonwillison |
| Flash Cyber | 3 | src-deepmind-blog |
| Defence Source | 3 | src-ep-itre |
| Video | 3 | src-ep-itre |
| Disclaimer | 3 | src-ep-itre |
| Only | 3 | src-ep-itre |
| Fix | 3 | src-gh-vllm-releases |
| GeForce NOW | 3 | src-nvidia-blog |
| Open | 3 | src-kol-interconnects |
| Enough Data Part | 3 | src-kol-lilianweng |
| LLM Research Papers | 3 | src-kol-raschka |
| List | 3 | src-kol-raschka |
| Qwen3 | 3 | src-qwen-blog |
| MODELSCOPE DEMO DISCORD | 3 | src-qwen-blog |
| FACE MODELSCOPE DISCORD | 3 | src-qwen-blog |
| Qwen2.5 | 3 | src-qwen-blog |
| AI-generated | 3 | src-media-techcrunch |
| TechCrunch Disrupt | 3 | src-media-techcrunch |
| Sam Altman | 3 | src-media-techcrunch |
| The Verge | 3 | src-media-theverge |
| Montana | 3 | src-media-mit-techreview |

## 這一頁不保證什麼

- **不保證候選是實體。** 收割只做拉丁字與括號內字串的字面規則
  （`pulse-probe.harvest_candidates`），沒有任何語意判斷。
- **中文的無括號新詞抽不出來。** 中文沒有詞邊界，這是已知缺口，
  不是這一頁漏算。中文來源進來之後這一頁會系統性低估。
- **次數是「相異項目」不是「出現行數」。** 同一則新聞在 feed 上掛三天，
  只算一次。跨天直接累加行數會虛胖一倍——那個坑 `items_observed` 踩過。
- **簡繁不互通。** 正規化那一層刻意不做簡繁轉換，所以同一個詞的兩種寫法
  會分別計數，兩邊都可能因此構不到門檻。
