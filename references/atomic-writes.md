# 狀態檔的寫入：為什麼一律走 tmp + rename

> 這份是**規格**，`scripts/lib/atomicwrite.py` 是它的實作。不一致時以本檔為準，
> 並且先改本檔再改碼（紅線 9）。

## 問題不是「檔案會壞」，是「壞掉的檔案讀得起來」

一天 12 班，每一班都在 GitHub Actions 的一台隨時可能被回收的 runner 上跑。
`ubuntu-latest` 有 6 小時上限、有 OOM killer、有 spot 回收，`continue-on-error: true`
的步驟被砍掉之後鏈還會繼續往下走。也就是說「寫到一半被砍」不是理論值。

真正咬人的不是崩潰本身，是崩潰之後那個檔案的樣子。實測：在 `y.dump()` 寫
`_config/sources.yaml` 的第 0.012 秒送 SIGKILL，留下一個 17,777 bytes 的檔案，
而它——

- **是合法的 YAML**，`yaml.safe_load()` 不會丟例外
- 四個 `*_sources:` 分節**整段不見**，載進來是一份沒有任何來源的設定
- 下一班 `pulse-probe.py` 讀它 → 零條可跑來源 → 那是 exit 3，一個硬 guard
- 但寫它的兩個步驟都掛 `continue-on-error: true`，整條 job 仍然 exit 0
- `git add -A` 把它 commit 掉（`1 insertion, 1178 deletions`），Pages 照常部署綠燈

同一個形態在 `_dashboards/health.md` 上也重現得出來（`ulimit -f 2`）：2048 bytes、
從半行截斷、frontmatter 沒有閉合的一頁，被 CI 提交上去。而這一頁**就是死人開關
本身**——看板告訴人「鏈是活的」的那一頁，自己是壞的。

這是這個 repo 反覆出現的同一種病的又一個病灶：**壞掉不會讓任何東西變紅。**
半份 `sources.yaml` 不會報錯，它只是讓系統從此什麼都看不見。

## 規則

**任何「下一班會讀回來」的檔案，一律 tmp + `os.replace()`。**

分界線不是檔案重不重要，是**壞掉之後會不會被當成事實讀回去**：

| 檔案 | 下一班誰讀它 | 半份的後果 |
|---|---|---|
| `_config/sources.yaml` | probe / score / cluster / render / monitor / recheck | 來源整批消失，鏈跑得很完美但什麼都看不見 |
| `_probe/state.json` | probe 的 `first_fetch_at` / cursor | 每條來源都變成「從沒抓過」＝整批重跑成 backfill，事件全掛 `stale_backfill` 永不發布 |
| `_probe/seen.json` | probe 的去重 | 舊項目重新被當成新項目收一次 |
| `_probe/source-health.json` | source-health 的連續計數與 `degraded_by` | 機器降級的記號掉了 ⇒ 機器不再撤銷自己做過的降級 |
| `_corpus/<day>/<id>.jsonl` | 同日下一班的 `load_day_flags`（sticky 欄位）、monitor 的 `last_success` | 當日快照缺一截，比率與 backfill 判定都跟著錯 |
| `_dashboards/health.md` | 人 | 死人開關自己壞掉 |

反過來，`dist/` 底下那些 render 產物**不在**這條規則裡：它們每班全量重生、
不被任何後續步驟讀回、而且 `dist/` 根本沒進版控。壞了下一班就好了。
`_probe/<day>/report.md` 同理，那是給人看的一次性報告。

## 實作

```python
from lib.atomicwrite import atomic_write_text, atomic_write_with

atomic_write_text(path, body)                      # 純文字
atomic_write_with(path, lambda fh: y.dump(doc, fh))  # 要交出 file handle 的（ruamel）
```

兩支都做同一件事：在**同一個目錄底下**開 `.<name>.tmp.<pid>`，寫完 `flush` +
`os.fsync`，再 `os.replace()` 蓋過去。三個細節都不是可有可無的：

- **同一個目錄**：`os.replace()` 只在同一個檔案系統上才是原子的。丟去 `/tmp`
  再搬過來就不是了。
- **`fsync` 才 `replace`**：少了它，rename 進去的可能是一個內容還在 page cache
  裡、斷電後變成一堆 NUL 的檔案。CI 上機率低，本機 cron 部署上不低。
- **失敗要刪 tmp**：否則 `git add -A` 會把一地 `.sources.yaml.tmp.4711` 提交進去。

`os.replace()` 在 POSIX 與 Windows 上都是原子取代（Python 3.3+）。所以讀的那一端
永遠只會看到「舊的完整版」或「新的完整版」，不存在第三種狀態——這正是重點：
**不是保證寫得成功，是保證失敗不會偽裝成成功。**

## 這條規則守不住什麼

守不住「兩個檔案要一起更新」。`--apply` 會同時寫 `sources.yaml` 與
`source-history.jsonl`，在兩次 `os.replace()` 之間被砍，仍然會留下一份改了
lifecycle 卻沒有對應歷史紀錄的狀態。跨檔案的交易要靠 git commit 那一層，
不在這一層解。寫在這裡免得有人以為裝了這個就沒事了（紅線 8）。
