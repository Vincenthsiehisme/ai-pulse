<#
setup-vault.ps1 ??撱箇? AI-Pulse vault嚗?甈⊥改?

?冽?嚗?    .\setup-vault.ps1 -VaultPath "E:\path\to\AI-Pulse"

??嚗遣鞈?憭???撖?.gitignore ????Dataview ?銵冽 ??git init ??擐活 commit
銝???銝?撖思遙雿歇摮??獢??舫?銴銵?摰嚗?#>

param(
    [Parameter(Mandatory = $true)]
    [string]$VaultPath
)

$ErrorActionPreference = "Stop"

# 蝯曹??函 BOM ??UTF-8嚗??git diff ?芷??Obsidian ?鈭Ⅳ
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-IfAbsent([string]$Path, [string]$Content) {
    if (Test-Path $Path) {
        Write-Host "  skip (撌脣???: $Path" -ForegroundColor DarkGray
        return
    }
    $dir = Split-Path $Path -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
    Write-Host "  created: $Path" -ForegroundColor Green
}

Write-Host "`n== 1. 撱箇?鞈?憭?==" -ForegroundColor Cyan
$dirs = @(
    "Events",           # Event note嚗銝鈭祕蝭暺?
    "Sources",          # 靘? note
    "Tracks",           # ?剖之銝餌?
    "Actors",           # ?砍 / 鈭箇
    "_config",          # sources / entities / gate / people
    "_corpus",          # M1 ?賢??憪???jsonl
    "_probe",           # M1 閫皜砍??    "_dashboards",      # Dataview ?亥岷??    "_evidence_raw",    # git-ignored嚗?憪?payload
    "scripts"
)
foreach ($d in $dirs) {
    $p = Join-Path $VaultPath $d
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
        Write-Host "  created: $d\" -ForegroundColor Green
    } else {
        Write-Host "  skip (撌脣???: $d\" -ForegroundColor DarkGray
    }
}
# _evidence_raw 鋡?gitignore嚗?閬?placeholder ????憭?Write-IfAbsent (Join-Path $VaultPath "_evidence_raw\.keep") ""

Write-Host "`n== 2. .gitignore ==" -ForegroundColor Cyan
Write-IfAbsent (Join-Path $VaultPath ".gitignore") @'
# ?梁???嚗?憪?payload 瘞訾??脩??改?SKILL.md 蝝? 6嚗?_evidence_raw/

# Obsidian ?犖撌乩?????憭?閮剖?閬脩??改?workspace 銝?嚗?.obsidian/workspace*
.obsidian/cache
.trash/

# Python
__pycache__/
*.pyc
.venv/

# OS
Thumbs.db
.DS_Store
'@

Write-Host "`n== 3. Dataview ?銵冽 ==" -ForegroundColor Cyan

Write-IfAbsent (Join-Path $VaultPath "_dashboards\health.md") @'
# health ???∩犖?澆??圈悅摨?
**?方??孵?嚗????單?瘝??典?嚗??舐????隤扎?*
蝟餌絞??甇餅?????荔??芣?霈?last_success ????
## 頞? 2 憭拇???????皞?蝝?嚗?
```dataview
TABLE last_success, lifecycle, consecutive_failures
FROM "Sources"
WHERE date(now) - date(last_success) > dur(2 days)
SORT last_success ASC
```

## ?券靘???敺?????
```dataview
TABLE last_success, health
FROM "Sources"
SORT last_success ASC
```
'@

Write-IfAbsent (Join-Path $VaultPath "_dashboards\source-health.md") @'
# source-health

```dataview
TABLE track, lifecycle, health, consecutive_failures, last_success
FROM "Sources"
SORT health ASC
```
'@

Write-IfAbsent (Join-Path $VaultPath "_dashboards\blocked-queue.md") @'
# blocked-queue ??瘝??蝳?靽?
```dataview
TABLE first_observed_at, company, blockers
FROM "Events"
WHERE status = "blocked"
SORT first_observed_at DESC
```
'@

Write-IfAbsent (Join-Path $VaultPath "_dashboards\watch-queue.md") @'
# watch-queue ???????

閮剛?銝停銝撣??芰?敺?霅????? blocked 銝?嚗locked ?臬?靽殷?watch ?臬?霅?
```dataview
TABLE first_observed_at, company, next_signal
FROM "Events"
WHERE status = "watch"
SORT first_observed_at DESC
```
'@

Write-IfAbsent (Join-Path $VaultPath "_dashboards\latest-shift.md") @'
# latest-shift ???餈撣? Event

```dataview
TABLE first_observed_at, company, track, confidence, heat
FROM "Events"
WHERE status = "published"
SORT first_observed_at DESC
LIMIT 20
```
'@

Write-IfAbsent (Join-Path $VaultPath "_dashboards\dictionary-gaps.md") @'
# dictionary-gaps ??摮鋆?

?閰??券ㄐ蝝舐?嚗 `_probe/<date>/report.md`嚗?甈?run ?Ｙ?嚗??祇?靘迤摨行皞???敶撌脫???閰?
## 敺???鈭箏極憛恬?

| ? | 擐活?箇 | 頝其?皞 | 瘙箏? |
|---|---|---|---|
'@

Write-Host "`n== 4. README ==" -ForegroundColor Cyan
Write-IfAbsent (Join-Path $VaultPath "README.md") @'
# AI-Pulse

?翠I?? AI ?Ｘ平?撘??untime 0 LLM / 0 Claude嚗???瑞閬?嚗?????
**??函? vault**嚗??犖?亥?摨怠????橘?銝??git repo??
## ?曉??畾?
M1 閫皜祆?嚗????啗???皜砍????????閰?????gate??
瘥?Ｗ `_probe/<date>/report.md`嚗??拙摮?
- **author 摮??* ??瘙箏?鈭箇撅文潔??澆???- **撖阡??賭葉??* ??瘙箏?摮敺?芷

閫皜祆?銝予?找?閬隞颱?閮剖?嚗??敺??舀???
## 鞈?憭?
| 頝臬? | ?批捆 | ? |
|---|---|---|
| `Events/` | Event note嚗銝鈭祕蝭暺? | ??|
| `Sources/` | 靘? note | ??|
| `_config/` | sources / entities / gate / people | ??|
| `_corpus/` | ??隤? jsonl | ??|
| `_probe/` | 閫皜砍??| ??|
| `_evidence_raw/` | ?? payload | ??git-ignored |

## ?臬??

`_config/people.yaml` ??`Actors/` 摨??犖??note **銝?**?脣隞颱?撠?頛詨??'@

Write-Host "`n== 5. git ==" -ForegroundColor Cyan
Push-Location $VaultPath
try {
    if (-not (Test-Path (Join-Path $VaultPath ".git"))) {
        git init | Out-Null
        Write-Host "  git init 摰?" -ForegroundColor Green
    } else {
        Write-Host "  skip: 撌脫 git repo" -ForegroundColor DarkGray
    }
    git add -A | Out-Null
    $staged = git diff --cached --name-only
    if ($staged) {
        git commit -m "scaffold: AI-Pulse vault ??蝯?" | Out-Null
        Write-Host "  擐活 commit 摰?" -ForegroundColor Green
    } else {
        Write-Host "  skip: ?∟??游 commit" -ForegroundColor DarkGray
    }
} finally {
    Pop-Location
}

Write-Host @"

== 摰??銝?????隞嗡? ==

1. ?身摰??暸?_config\
     sources.yaml  entities.yaml  gate.yaml  people.yaml
   ??pulse-probe.py ?暸?scripts\

2. Obsidian ???冗??vault嚗?閬??Ｘ??亥?摨怠???鞈?憭橘?
     閮剖? ??蝷曄黎憭? ????摰璅∪? ??摰?銝血???Dataview
     閮剖? ??瑼???? ?????獢?? _corpus ??_evidence_raw
     嚗??撠??”鋡?jsonl 瘣?嚗?
3. 鋆?鞈港蒂蝛箄?
     pip install requests PyYAML feedparser
     `$env:VAULT_DIR="$VaultPath"
     python scripts\pulse-probe.py --dry-run

4. 憯???endpoint 靽桀?敺?甇??頝?甈∴?蝣箄? _corpus\ ??_probe\ ?镼選?
   ?嗅???撌乩????具?
"@ -ForegroundColor Cyan
