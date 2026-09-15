#!/bin/bash
# nightly-shell.sh — 夜班的外殼：driver 定棒次，這裡傳棒。
#
# `pulse-nightly.py` 每次推進到下一個交棒點就以 exit 10 停住，並印出一份完整的派工
# （清單在哪、幾筆、規則在 runbook 的哪一節、產物寫到哪個檔）。這支腳本把那份派工
# 原樣餵給一個**獨立的** `claude -p`，寫完再叫 driver 接回去。
#
# 為什麼一棒一個 session，而不是一個 session 裡開 subagent：
#
#   context 最小   每一棒只看到自己那一段的清單，看不到別段的
#   成本可預測     五段各自獨立，一段爆掉不會把整晚的 context 拖著
#   失敗隔離       某一棒寫壞了，driver 在對帳時擋下來，其餘的狀態還在
#   不依賴 subagent  headless 開得了 subagent（2026-09-15 實測），但用不到
#
# 迴圈是 shell 的、判斷是 driver 的、**寫作才是 LLM 的**。這條鏈的核心命題
# （runtime 0 LLM 判斷）在這裡照樣成立：LLM 一個判斷都不做，只寫字。
#
# 用法：
#   scripts/nightly-shell.sh              正常跑（會 commit 與 push）
#   scripts/nightly-shell.sh --no-push    跑完 commit 但不推
#   AI_PULSE_REPO=/path NIGHTLY_MODEL=opus scripts/nightly-shell.sh
#
# 離開碼沿用 driver 的：0 跑完、1 有事要人看、2 壞了。**不會回 10**：
# 10 是「等你」，而這支腳本就是那個「你」。
set -u

REPO="${AI_PULSE_REPO:-$HOME/Developer/ai-pulse}"
MODEL="${NIGHTLY_MODEL:-sonnet}"
# 交棒次數上限。階段表目前有五個交棒點，留一點餘裕；**沒有上限的迴圈會在 driver
# 因為某個沒想到的狀態一直回 10 的時候，整晚反覆叫 claude**，那是會燒錢的失敗模式。
MAX_HANDOFF="${NIGHTLY_MAX_HANDOFF:-8}"

cd "$REPO" || { echo "[fatal] 進不去 $REPO" >&2; exit 2; }
export VAULT_DIR="$PWD"

command -v claude >/dev/null || { echo "[fatal] 找不到 claude CLI" >&2; exit 2; }

for i in $(seq 1 "$MAX_HANDOFF"); do
  out="$(python3 scripts/pulse-nightly.py run "$@" 2>&1)"
  rc=$?
  printf '%s\n' "$out"
  [ "$rc" -eq 10 ] || exit "$rc"

  # 交棒訊息的第一行長這樣：`[narrative] <stage-id>`。記成本要知道記在哪一段。
  stage="$(printf '%s\n' "$out" | sed -n 's/^\[narrative\] \(.*\)$/\1/p' | head -1)"
  echo "[handoff $i] 交給寫作端（stage=$stage model=$MODEL）"
  # 第一行的身分句是它判斷自己是誰的唯一線索：沒有那一行，全域 CLAUDE.md 的啟動
  # 序列會讓它去讀 vault 的 profile 與日誌，而那一段工作一個字都用不到。
  resp="$(claude -p "你是 ai-pulse 夜班的**寫作端**。不要跑任何啟動序列、不要讀 vault、不要讀日誌。

$out

照上面那份交棒訊息做：讀它指名的清單、照它指到的規則寫、把結果寫進它指名的那個檔案。

規矩：
- 寫完就停。**不要**自己跑 pulse-nightly.py，不要跑 apply，不要 commit，不要 push。
- 判斷不由你決定：發不發是 gate 的規則決定，你不改 status、不改分數。
- 只依證據寫，不編造。證據不足就照規則標，不要補一個看起來合理的說法。
- 範圍外的事不要做（例如發現腳本有 bug、測試紅了）。把它寫進你的回覆，讓人白天看。
" --allowedTools "Read Write Glob Grep" --model "$MODEL" --output-format json)"
  crc=$?
  if [ $crc -ne 0 ]; then
    echo "[fatal] 寫作端第 $i 棒失敗（rc=$crc）" >&2
    exit 2
  fi
  # 把回覆印出來給人看，順手把這一棒的花費記進狀態檔。**一晚花多少錢，在此之前
  # 沒有任何地方在記**——而「這條鏈很便宜」跟「沒有人在量」長得一模一樣。
  usd="$(printf '%s' "$resp" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    print('', end=''); sys.exit()
sys.stderr.write((d.get('result') or '') + '\n')
c = d.get('total_cost_usd')
print('' if c is None else c, end='')
")"
  [ -n "$usd" ] && python3 scripts/pulse-nightly.py cost --stage "$stage" --usd "$usd"
done

echo "[fatal] 交棒 $MAX_HANDOFF 次還沒跑完——driver 可能卡在某個狀態一直回 10" >&2
exit 2
