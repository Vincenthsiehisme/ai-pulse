"""狀態檔的原子寫入 —— 規格見 references/atomic-writes.md。

為什麼要有這個檔：問題不是「檔案會壞」，是**壞掉的檔案讀得起來**。

實測：在 `y.dump()` 寫 `_config/sources.yaml` 的第 0.012 秒送 SIGKILL，留下的
17,777 bytes 是**合法的 YAML**，只是四個 `*_sources:` 分節整段不見。
`yaml.safe_load()` 不丟例外，寫它的步驟掛 `continue-on-error: true` 所以 job
仍然 exit 0，`git add -A` 把它 commit 掉（1 insertion, 1178 deletions），
Pages 綠燈部署。下一班的 probe 讀到零條來源，那才是 exit 3——但那時
`sources.yaml` 已經在 main 上了。

`_dashboards/health.md` 也重現得出來（`ulimit -f 2`）：一頁 frontmatter 沒閉合的
2048 bytes 被 CI 提交。而那一頁就是死人開關本身。

所以規則是：**任何「下一班會讀回來」的檔案，一律 tmp + os.replace()。**
分界線不是重不重要，是壞掉之後會不會被當成事實讀回去。`dist/` 的 render 產物
與 `_probe/<day>/report.md` 不在此列——每班全量重生、沒有後續消費者。

這一層保證的不是「寫得成功」，是「失敗不會偽裝成成功」（紅線 8）。
它守不住的是跨檔案的交易：`--apply` 同時寫 sources.yaml 與 source-history.jsonl，
兩次 replace 之間被砍仍然會不一致，那一層歸 git commit 管。
"""
import os
from pathlib import Path

__all__ = ["atomic_write_text", "atomic_write_with"]


def _tmp_for(path: Path) -> Path:
    # 必須跟目標同一個目錄：os.replace() 只在同一個檔案系統上才是原子的。
    # 前綴一個點 + .tmp 後綴，是為了讓萬一漏刪的殘骸在 git status 裡一眼認得出來。
    return path.with_name(f".{path.name}.tmp.{os.getpid()}")


def atomic_write_with(path, writer, encoding="utf-8"):
    """開一個同目錄暫存檔交給 writer(fh) 寫，寫完 fsync 再 os.replace() 蓋過去。

    writer 收到的是已開啟的 text-mode file handle（ruamel 的 `y.dump(doc, fh)`
    這種必須自己拿 handle 的 API 走這支）。writer 丟例外時暫存檔會被刪掉，
    目標檔一個位元組都不動。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(path)
    try:
        with tmp.open("w", encoding=encoding) as fh:
            writer(fh)
            fh.flush()
            # fsync 一定要在 replace 之前：少了它，rename 進去的可能是一個內容
            # 還在 page cache 裡的檔案，斷電後變成一堆 NUL。
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        # 不清掉的話 `git add -A` 會把一地 .sources.yaml.tmp.4711 提交進去。
        # BaseException 而非 Exception：KeyboardInterrupt / SystemExit 一樣要清。
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    _fsync_dir(path.parent)
    return path


def atomic_write_text(path, text, encoding="utf-8"):
    """`path.write_text(text)` 的原子版。"""
    return atomic_write_with(path, lambda fh: fh.write(text), encoding=encoding)


def _fsync_dir(d: Path):
    # 讓 rename 本身也落地。失敗不致命（有些平台 / 檔案系統不給 fsync 目錄），
    # 這只是把「已經是原子的取代」再往下推一層耐久度，不影響正確性。
    try:
        fd = os.open(str(d), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
