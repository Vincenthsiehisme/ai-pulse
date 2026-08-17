# 一條沒有留下痕跡的步驟：digest 那一段為什麼看不見

> 消費者：`scripts/pulse-digest-apply.py`、`scripts/pulse-monitor.py`、
> `scripts/enrich-runbook.md` 的 digest 那兩節、`_config/gate.yaml` 的
> `monitor.digest_stale_after_days`、`scripts/selftest.py` 的判準。
> 規格先於實作（紅線 9）：這一頁先寫，碼才動。

## 觸發這一頁的那一晚

2026-08-16 的夜班有跑、有 push（`2e65b46`，19:08Z），而且**沒有產出文章**。
那個 commit 只動了四個檔，全是 worklist：

```
_github/desc-zh.json  _probe/digest-worklist.json
_probe/enrich-worklist.json  _probe/narrative-worklist.json
```

`Digests/2026-08-16.md` 不存在。而當天的 worklist 上有素材：

```
date=2026-08-16  mode=retrospective  素材=1 則（evt-2026-07-07-81e525，41 天前的 pending signal）
```

拿那份真的 worklist 試過，寫一份最小的三段稿（A ＋ D ＋ C）機檢全過、離開碼 0。
**所以不是規則太嚴寫不出來。**

那為什麼沒寫？**從 repo 裡看不出來。** 兩個解釋都說得通，而且都無法從證據排除：

```
(a) 那一步根本沒跑     排程 prompt 的「做完了」清單裡沒有 digest-apply
                       （那份 prompt 寫在 apply 存在之前）
(b) 跑了但沒寫         runbook 7.6 從頭到尾沒提 mode: retrospective，
                       模型拿到「1 則 41 天前的舊事件」可能判斷沒東西可寫
```

08-14、08-15 都寫出來了，兩天都是 `mode: normal` ＋ 3 則新素材。
**唯一的空日就是唯一失敗的那天**——這支持 (b)，但 n=1，不是結論。

## 真正的根因不是那一晚

不管是 (a) 還是 (b)，結果都一樣看不見：commit 訊息正常、`pulse-monitor` 全綠、
`_dashboards/health.md` 沒有 digest 那一格（`grep digest` 兩個檔都是 0 筆）。

**一條新鏈被接進無人值守的流程，而沒有同時被接進觀測層。**

這個 repo 知道這個病。`health.md` 有 GitHub 中文描述覆蓋率那一行，是因為那條線
曾經整整消失過而沒有人發現；`monitor` 有 `enrich_stale_after_days`，是因為
2026-08-05 push 被沙箱 proxy 擋掉而三個警報一條都沒叫。digest 這條鏈一個都沒有。

而且 `enrich-runbook` 的 7.6 寫著「退件或當掉就把完整輸出原樣寫進摘要」——
**那是把觀測責任交給一個無人值守的模型的自我報告**，而 2026-08-12 那晚
（摘要看起來完全正常，實際拿舊清單把 10 則已潤的整批重寫）正是在證明
那種報告不可信。那句話寫下的前一天，這個結論才剛被寫進
`references/enrich-idempotence.md`。

## 一、結構性的不對稱

```
7.5 digest-prep   成功會留痕跡  _probe/digest-worklist.json 進版控
7.6 digest-apply  只有成功才留痕跡  Digests/<date>.md
```

於是：

```
今晚沒素材        → worklist 更新、沒有文章
今晚有素材但沒寫  → worklist 更新、沒有文章    ← 在 git 裡一模一樣
```

紅線 8 說「量不到就寫量不到」。這一步違反了它：它把「沒發生」跟「失敗了」
寫成同一個狀態，而那個狀態是**檔案不存在**——一個沒有辦法帶理由的表達方式。

### 修法：apply 每次執行都留一份紀錄

```
_probe/digest-apply-last.json     進版控
{
  "date": "2026-08-16",
  "at": "2026-08-16 19:12Z",
  "outcome": "written | rejected | refused | no_worklist | date_mismatch",
  "mode": "retrospective",
  "material": 1,
  "sections": 3,
  "problems": [ {"rule": "...", "where": "...", "why": "..."} ]
}
```

**關鍵是它要寫在退件那條路上**，不然它就跟 `Digests/<date>.md` 一樣只記錄成功。

它證明的是「apply 被呼叫過，結果是什麼」。它**不能**證明「該跑而沒跑」——
那要靠下一節。兩件事分開量，因為要人做的動作不同：退件要去看理由改稿，
沒跑要去看排程。

## 二、monitor 認不得 digest

### 判準不能用「今天」

這條鏈跟 Actions 只靠時鐘耦合，而 `pulse-monitor.py` 兩邊都會被叫到
（Actions 16:09Z 的 `--write-health`、夜班 19:2xZ 的收尾）。用「今天有沒有
文章」當判準的話，Actions 那一邊每天都會誤報——它跑的時候夜班還沒開始。

**所以判準一律用天數**，跟 `enrich_chain_line` 同一個形狀：

```
最後一篇 digest 是幾天前          > digest_stale_after_days  → 叫
最後一次 apply 的結果不是 written  且它比最後一篇文章新       → 叫
```

第二條抓的是「跑了但退件」：那種情況 `Digests/` 可能還停在前天，而
apply 的紀錄是昨天的——兩個數字擺在一起才分得出「沒跑」跟「退件」。

### 門檻是一個新的 key，不共用

`monitor.digest_stale_after_days`，跟 `enrich_stale_after_days` 是**兩個 key**，
理由同 `_config/gate.yaml` 裡 `watchdog.stale_after_days` 那一段：共用一個 key 的話，
哪天有人為了讓其中一個安靜而調鬆它，會連另一個一起調鬆。

門檻 2。理由：**空日也應該要有文章**——`mode: retrospective` 一定會挑出一則
（除非所有已上線事件都用過），所以「連兩天沒有 digest」不是淡季，是壞了。
近 30 天實測 14 天是空日（47%），這條規則本來就是為那 47% 設計的。

## 三、`sources` 這一格有消費者、沒有生產者

`pulse-digest-prep.load_featured()` 讀 `Digests/*.md` 的 `fm["sources"]`，
而 `pulse-digest-apply.py` 寫的十個欄位裡沒有它。實測：

```
load_featured() 讀到: set()        ← Digests/ 裡有兩篇
現況        → 空日挑中 evt-2026-07-07-81e525（NVIDIA Vera，41 天）
接上之後    → 空日挑中 evt-2026-07-17-484ed7（Gemini 3.5 Flash Cyber，31 天）
```

`pending_signals` 按 `-days_since` 排序，而 Vera 的條件是 `independent_sources < 2`
（它就是 1），所以它永遠不會離開清單。**每一個空日都會挑到同一則**，而空日是
近 30 天的 47%。

這是 `references/source-capabilities.md` 記過的同一個形狀：`next_signal` 那一格
在 frontmatter 裡有消費者、107 則已上線事件裡有值的是 0 則。讀過那一段之後
還是漏接了一次。

修法：apply 寫 `sources: [被引用到的 event id]`。判準要**端到端**釘：
寫檔 → 讀回 → `load_featured()` 非空。只釘「apply 有寫這一格」的話，
prep 那邊改了 key 名字不會有任何東西紅（M296 那條線）。

## 四、排程 prompt 的「做完了」清單

那份 prompt（不在這個 repo 裡，由人貼進排程任務）現在寫的是：

```
pulse-enrich-prep.py 的輸出出現在你的紀錄裡
pulse-digest-prep.py 的輸出出現在你的紀錄裡
pulse-render.py
git push
pulse-monitor.py
```

**`pulse-digest-apply.py` 不在裡面。** 一個照這份清單自檢的模型，跑完 7.5
就滿足了「五件都做完」。

但問題不只是少一行。**那份清單本身是硬編碼的步驟名，而它旁邊那句話寫著
「不要停在任何固定編號，那一節有幾步就做幾步」**——兩者互相矛盾，而模型會
照清單走，因為清單具體。

正確的判準是機械可查、而且不會隨著加步驟過期的：

> runbook 自動化那一節裡每一個 `python scripts/*.py` 都出現在你的執行紀錄裡。

這一頁管不到那份 prompt（它在排程設定裡），但把判準寫在這裡，
下次有人改 prompt 時有東西可以對。

## 五、runbook 7.6 沒有提空日

`digest-framework` §四整節在講空日規則，而 `enrich-runbook` 的 7.6
一個字都沒提。要補的是一句話：

> **`mode: retrospective` 一樣要寫。** 空日不是「沒東西可寫」，是
> 「今天寫的是回頭看」。開頭那句「今天沒有新事件」由 apply 自動加，不用你寫。
> 素材只有一則也照寫——一則寫深比三則各說一句好，這是框架第一節就寫的。

## 不做的：豁免不拿掉

7.6 的「失敗不擋 push」現在還是對的（`Digests/` 沒有下游消費者，寫不出來
不影響當天的發布）。**但豁免要配一個會叫的警報，不然豁免就是靜音。**
上面第一、二節就是那個警報。

`/daily/` render 接上的時候，回來把豁免與這一句一起拿掉。
