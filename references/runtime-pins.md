# runtime 也要進「同樣的輸入給同樣的輸出」

> 消費者：`requirements.txt`、五個 `.github/workflows/*.yml` 的 pip 安裝步驟。
> 規格先於實作（紅線 9）。

## 這個檔為什麼存在

這條鏈對外的承諾是：

```
同樣的輸入 → 同樣的輸出
```

在此之前那句話只涵蓋 repo 裡的東西。五個 workflow 各自寫著

```
pip install requests pyyaml feedparser ruamel.yaml
```

**沒有版本。** 於是實際上成立的是：

```
同樣的 commit + 同樣的語料 + 不同日期安裝的套件 → 可能不同的輸出
```

而且不會有任何東西變紅——輸出只是「跟昨天不一樣」。

## 這不是預防性的，它有一個現成的受害者

`selftest` 有一條：

```
sources.yaml 是 ruamel round-trip 的不動點
```

那條測試直接綁死 **ruamel emitter 的縮排行為**。ruamel 換一個版本改縮排，
那條會紅——**紅在半夜、紅在一個沒有改過任何一行程式碼的 commit 上**。

2026-08-11 夜班已經演過一次同型事故（人手寫 4 空格、機器吐 2 空格，
第一次 `--apply` 重排 97 行，所有拿字串比對這個檔的東西當晚同時失效）。
那次的觸發者是人，下一次的觸發者會是 pip。

## 版本從哪裡來，以及這句話的誠實邊界

```
requests==2.33.1
PyYAML==6.0.3
feedparser==6.0.14
ruamel.yaml==0.19.1
```

這四個是**釘版本那天實際跑過 selftest 的版本**，不是「CI 之前用的版本」。
CI 之前用什麼沒有紀錄——沒有 lock、沒有 log，那個資訊已經不存在了。

可以確定的是：`_config/sources.yaml` 在 `ruamel.yaml==0.19.1` 底下是不動點，
也就是這個版本的 emitter 跟寫出那份檔案的那個版本行為一致。其餘三個沒有這種
可對照的痕跡，只有「selftest 全綠」。

**寫下來是為了讓下一個人知道這批數字的證據強度不一樣。**

## 為什麼不切子集

五個 workflow 之前各裝各的：

```
data-refresh              requests pyyaml feedparser ruamel.yaml
mutation                  requests pyyaml feedparser ruamel.yaml
pages                     pyyaml requests
verify-article-metadata   requests pyyaml
watchdog                  pyyaml
```

**五份手寫清單，就是 `SECTIONS` 與 `RUN_LIFECYCLES` 那兩次搬家的同一個病。**

具體會怎麼壞：`watchdog.yml` 只裝 `pyyaml`。哪天有人在 watchdog 的路徑上
加一個 `import requests`，它會在 runtime 炸——而 watchdog 的**全部功能就是
當死人開關**。一個自己死掉的死人開關不會通知任何人。

裝多幾個套件的成本是幾秒鐘。清單分岔的成本是靜默失效。

## `opencc` 刻意不在清單裡

`pulse-probe.py` 有這一段：

```python
try:
    import opencc  # noqa: F401
    simp_trad = True
except ImportError:
    simp_trad = False
```

**五個 workflow 從來沒有裝過它。** 14 份夜班報告每一份都印著：

```
- 簡繁正規化：**未啟用**（未啟用時，簡體別名不會命中繁體寫法，反之亦然）
```

這個行為是對的——量不到就說量不到（紅線 8），不是假裝有做。

但「從來沒裝過」這件事在此之前**只寫在報告的一行字裡**，沒有任何地方
把它記成一個決定。所以 selftest 的第三條檢查有一份**明列的例外表**，
`opencc` 在裡面，旁邊寫著理由。例外要看得見，不能靠沒有人注意到。

要不要啟用它是**另一個題目**：今天 27 條在跑的來源 `language` 全是 `en`，
啟用它改變不了任何東西。等第一條中文來源上線再談，而那時候該動的是
`requirements.txt` 加一行，不是把這段 try/except 拿掉。

## selftest 釘住三件事

```
1. requirements.txt 每一行都是 name==version    釘了範圍等於沒釘
2. workflow 只准 pip install -r requirements.txt  不准有第六份手寫清單
3. scripts/ 裡 import 的第三方套件都在清單或例外表裡
```

第 3 條是唯一會抓到「新增了一個 import 但忘記加相依」的那條。
它用 `sys.stdlib_module_names` 分辨標準庫，所以不需要維護一份標準庫清單。

## selftest 要在**人的機器**上跑得起來

第 3 條檢查第一版直接用 `sys.stdlib_module_names`——那一格是 **Python 3.10
才有的**。CI 跑 3.12 所以全綠，而人的機器上整支 selftest 當場
`AttributeError` 炸掉（macOS 內建的 `/usr/bin/python3` 到今天還是 3.9）。

**selftest 跑不起來的機器，等於那台機器上一條檢查都沒有。** 這比少一條檢查嚴重：
少一條是知道自己少了什麼，跑不起來是什麼都不知道。

而這個 repo 本來就在照顧舊 Python——其他腳本寫 `from __future__ import
annotations` 就是為了這件事。所以修法是加 fallback，不是要人升級：

```
有 sys.stdlib_module_names  → 用它
沒有                        → find_spec 看模組解析出來的檔案在不在標準庫目錄底下
```

`find_spec` **不會執行**那個模組，所以拿來問「這是什麼」是安全的。

那支 helper 吃一個哨兵值來分辨三種情況（照機器決定 / 強制 fallback / 直接給集合），
**因為兩條路徑都要測得到**。第一版把「強制 fallback」寫成傳 `None`，
而 `None` 當時的意思是「照機器決定」——那條斷言在測另一件事，而且它是綠的。

## 2026-08-13：fallback 第一版在 CI 上把 `yaml` 判成標準庫

fallback 只比 `origin.startswith(stdlib)`。而 site-packages 放在哪，
**各家 Python 不一樣**：

```
開發容器（Debian）   stdlib  /usr/lib/python3.11
                     site    /usr/local/lib/python3.11/dist-packages   ← 兩棵樹
CI（hostedtoolcache）stdlib  /opt/.../x64/lib/python3.12
                     site    /opt/.../x64/lib/python3.12/site-packages ← 在裡面
```

**標準 Python 安裝把 site-packages 放在 stdlib 目錄底下**——macOS、venv、
GitHub Actions 的 hostedtoolcache 都是。只有 Debian 系把它挪去 `/usr/local`，
而開發容器剛好是 Debian。

於是第一版在容器全綠，一進 CI 就把 `yaml` 判成標準庫，
「第三方套件都在清單裡」那條當場紅——而且是**四片變異全部 `[拒跑]`**，
因為 mutate.py 的第一件事就是確認基準線全綠。

修法是把 `purelib` / `platlib` 也排除掉。更重要的是把判斷抽成一支**純函式**、
目錄路徑用參數傳進去：

```python
_dep_origin_is_stdlib(origin, std_dir, site_dirs)
```

**這樣兩種佈局都能在同一台機器上測。** 第一版做不到——它只驗得到跑測試的那台
機器剛好是哪一種佈局，而那正是它為什麼綠著出門。

## 升級相依要走顯式流程

```
改 requirements.txt → 跑 selftest → 跑變異盤點 → 看 diff → merge
```

**不是讓夜班自己吃到最新版。** 這跟「升到 active 只有人能做」是同一條線：
會改變輸出的事情，要有人按下那個按鈕。
