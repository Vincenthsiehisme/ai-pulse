# 來源層：lifecycle 狀態機與健康分

> 這份文件是**規格**，`scripts/pulse-source-health.py` 是它的實作，
> `_config/gate.yaml` 的 `source_health:` 是它的門檻。三者不一致時以本檔為準，
> 並且**先改本檔再改碼**（紅線 9）。

## 為什麼需要這一層

三層判斷門禁裡，訊號層（quality-score）管單條訊號夠不夠格，事件層
（readiness-gate）管 Event 能不能發布，來源層管的是最前面那個問題：**這條來源
還活著嗎，還該不該花一次請求去抓它。**

在 2026-07-26 之前，這一層只有一半：`gate.yaml` 裡躺著一個 `source_health:` 區塊，
六個門檻寫得好好的，**沒有任何一行程式碼讀它**。`lifecycle` 欄位有五個值，
但升降級只有一條路徑真的會自動發生（robots 重驗把被誤殺的來源升回 `probing`）。
其餘的升降級全靠人記得。

這不是「還沒做完的功能」，是一個會咬人的狀態：來源壞掉沒有人會知道，
因為壞掉的來源不會讓任何東西變紅，它只是安靜地不再貢獻資料。
2026-07-24 漏抓 Claude Opus 5 就是這個形態——`src-openai-blog` 被一次 403
判成 `robots_ok: false` + `dormant`，整條 OpenAI 線靜靜關掉，
報告上不會少一行，只是那一格永遠空白。

## 五個狀態

```
draft ──(人)──► probing ──(人)──► active
                   │                 │
                   │  (機器：連續失敗) │  (機器：連續失敗)
                   ▼                 ▼
                degraded ◄───────────┘
                   │  │
   (機器：連續成功) │  │  (機器：連續失敗到隔離線)
                   ▲  ▼
                probing/active   quarantine_candidate（只報告，不自動寫）
                                        │
                                     (人)▼
                                     dormant
```

| 狀態 | 會被抓嗎 | 誰能設 | 意思 |
|---|---|---|---|
| `draft` | 否 | 人 | 登記了但還沒決定要不要跑 |
| `probing` | 是 | 人 / 機器（robots 復活、健康回復） | 會抓，但還沒通過人工 checklist |
| `active` | 是 | **只有人** | 通過 checklist，資料被信任 |
| `degraded` | 是 | 機器 | 連續失敗，仍然抓（才有機會自癒），但標記出來 |
| `dormant` | 否 | **只有人** | 停用 |

`draft` 與 `dormant` 不會被請求，但**仍然出現在每班的來源狀態表**，狀態欄寫
`skipped_lifecycle`。靜默丟棄是這個系統最危險的失敗模式，所以跳過也要留痕。

### 兩條刻意不對稱的規則

**升到 `active` 只有人能做。** 這是「被信任」的那條線，機器不發信任。
機器最多把來源放回 `probing`（會抓，但不宣稱可信）。

**降到 `dormant` 只有人能做。** `dormant` 等於停止抓取，而**停止抓取的來源沒有
任何自癒路徑**——不抓就永遠量不到它好了沒有。這正是 `src-openai-blog` 的死法。
所以自動降級最多降到 `degraded`：仍然每班抓，連續成功就自己回來。
達到隔離門檻的來源只會出現在報告的 `quarantine_candidate` 清單裡等人看。

機器可以撤銷的只有機器自己做過的降級。降級時會在 `_probe/source-health.json`
記下 `degraded_by: health`；沒有這個記號的 `degraded`（人手設的）機器不碰。

## 健康分

每條來源一個 0–100 的分數，起始 100。每班每條來源結算一次，門檻在
`_config/gate.yaml`：

```yaml
source_health:
  success_gain: 8              # 200
  not_modified_gain: 3         # 304
  failure_penalty: 15          # 5xx / 抓取例外
  severe_failure_penalty: 25   # 404 / 410：端點不在了
  degrade_after_consecutive: 2 # 連續幾次失敗 → degraded
  quarantine_after_consecutive: 5  # 連續幾次失敗 → 列入隔離候選（只報告）
  recover_after_consecutive: 3 # 連續幾次成功 → 撤銷機器做的降級
```

### 什麼算失敗——這一節是整份文件的重點

自動降級最容易犯的錯，是把**我們量不到**當成**來源壞了**。
方向搞反的代價不對稱：漏抓一條壞掉的來源，只是晚幾天發現；
把一條好來源自動關掉，是無聲的、而且沒有自癒路徑的資料遺失。
所以下面這張表往「不罰」那邊倒。

| 每班觀測到的 status | 記成 | 為什麼 |
|---|---|---|
| `200` | 成功 `+8` | — |
| `200` 但 0 筆 | **成功** `+8` | 安靜的 feed 是健康的 feed。`src-mistral-news` 連兩天 200／0 筆——那是他們那陣子沒發東西，不是端點壞了。把「沒新聞」罰成失敗，等於逼系統偏好吵的來源。 |
| `304` | 成功 `+3` | 有回應、內容沒變。分數給得比 200 少，只是為了讓長期沒更新的來源慢慢往下飄，不是懲罰。 |
| `5xx` | 失敗 `−15` | 站方伺服器錯誤，通常是暫時的 |
| 抓取例外（`error`） | 失敗 `−15` | 逾時、解析炸掉、連線中斷 |
| `404` / `410` | 重度失敗 `−25` | 端點真的不在了。這是唯一一種「明確是來源那邊變了」的訊號，罰得最重也最該罰。 |
| `401` / `403` | **中性，不記分** | 量測失敗，不是站方政策。可能是 WAF 擋容器 IP、可能是路徑寫錯、也可能真的要登入——這三種在我們這一端**分不出來**。分不出來就不判。 |
| `429` | **中性，不記分** | 這是站方在說「你太快了」。罰它等於因為我們自己的請求頻率去扣來源的分。該調的是 `quota_per_run`。 |
| `robots_disallow` / `robots_unknown` | **中性，不記分** | robots 是合規政策，不是健康度，歸 `pulse-robots-recheck.py` 管。混在一起會讓一次 robots 假陰性同時觸發降級，變成 07-24 事故的加強版。 |
| `unsupported_adapter` | **中性，不記分** | 這是設定檔的 bug 不是來源的問題，selftest 的幽靈來源檢查已經會擋。 |
| `skipped_lifecycle` | **中性，不記分** | 根本沒去抓，沒有任何觀測 |

### 連續計數怎麼走

- 成功（200 / 304）→ 連續失敗數歸零，連續成功數 +1
- 失敗（5xx / error / 404 / 410）→ 連續成功數歸零，連續失敗數 +1
- 中性 → **兩個計數都不動**

中性不歸零是刻意的。若中性會歸零，一條每班在 404 與 403 之間輪流的來源
永遠湊不滿連續失敗數，會一直掛在那裡假裝健康。中性只是「這一班沒有資訊」，
不該被當成好消息。

## 每班的資料流

```
pulse-probe.py
   │  每條來源一筆 stat（id / status / items / error）
   ├─► _probe/<day>/report.md          人看的（本來就有）
   └─► _probe/source-runs.jsonl        機器看的，每班一個 JSON 物件（本次新增）
                                         │
                              pulse-source-health.py
                                         │
                     ┌───────────────────┼────────────────────┐
                     ▼                   ▼                    ▼
        _probe/source-health.json   _config/sources.yaml   _probe/source-history.jsonl
          分數與連續計數                lifecycle（--apply）      每一次異動
```

`_probe/source-runs.jsonl` 是 append-only，一班一行。之前沒有這個檔——
`pulse-probe.main()` 算出來的 stats 只餵給 markdown 報告，
所以健康分**根本沒有機器可讀的輸入**。這條管線要先接上，健康分才有東西可算。

## 用法

```bash
VAULT_DIR=... python scripts/pulse-source-health.py            # 只看，不改
VAULT_DIR=... python scripts/pulse-source-health.py --apply    # 寫回 lifecycle
VAULT_DIR=... python scripts/pulse-source-health.py --json
```

每班由 `.github/workflows/data-refresh.yml` 的 `Source health (0 LLM)` 這一步
掛 `--apply` 跑，位置在確定性 pipeline 之後（它吃的是 `pulse-probe` 這一班剛
append 進去的觀測）。敢一上線就掛 `--apply`，是因為這支能自動寫的只有
`probing/active → degraded`，而 `degraded` 仍然每班被抓、連續成功三班會自己回來；
`dormant` 永遠只有人能寫。這一步做不出「無聲關掉一條好來源」那種傷害。
`continue-on-error: true`：來源健康是觀測，觀測失敗不該讓整條資料鏈紅燈。

跟 `pulse-robots-recheck.py` 一樣，寫回用 ruamel round-trip
（`sources.yaml` 的註解是文件的一部分，不能被 dump 洗掉），
每一筆異動 append 進 `_probe/source-history.jsonl`。

## 目前的實況（2026-07-26 量到的，不是設計意圖）

- **沒有任何一條來源是 `active`。** 28 條可跑的來源全部掛在 `probing`，
  另有 5 條 `dormant`。也就是 `probing → active` 這條升級路徑從上線到今天
  一次都沒發生過——它需要人跑 checklist，而那個 checklist 沒有人跑過。
  這一層的自動降級因此目前只會作用在 `probing → degraded`。
- 這不是本次要修的東西，但寫在這裡免得日後有人看著狀態機以為 `active`
  是常態。誰要開始跑 checklist，`active` 才有意義。

## 回滾

這一層只寫兩個地方，兩個都可逆：

1. `_config/sources.yaml` 的 `lifecycle` 欄位 —— 把 `--apply` 拿掉就完全不寫；
   已經寫下去的可以照 `_probe/source-history.jsonl` 一筆一筆回推。
2. `_probe/source-health.json` —— 刪掉即可，下一班會從 100 分重新起算。

`_probe/source-runs.jsonl` 只增不改，刪掉會失去歷史但不影響鏈的運作。
