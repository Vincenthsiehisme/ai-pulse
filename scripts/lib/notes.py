# -*- coding: utf-8 -*-
"""notes.py — Event/Source note 的 frontmatter 解析與佔位詞常數（共用）。"""
from __future__ import annotations

import re

import yaml

# 新建 Event 的 body 佔位詞。**繁體**——這個 vault 是繁體中文的，佔位詞會直接
# 出現在 Obsidian 裡給人看，寫簡體只是因為當初從對岸專案移植時沒改。
#
# 這個常數以前在四個檔案各寫一份字面值（pulse-cluster / pulse-monitor /
# pulse-enrich-prep，加上 pulse-gate 的正則）。四份不同步的後果不是報錯而是靜默：
# 產生端改了、enrich-prep 沒改 → prep 一則都挑不到 → 潤稿鏈整條空轉，
# monitor 的「未潤稿」數字還會顯示 0，看起來一切正常。所以收成一份。
PLACEHOLDER = "待編輯"

# 偵測用正則：**必須同時認得簡體舊寫法。**
# vault 裡已經有用「待编辑」寫成的既有 Event，把舊寫法從這裡拿掉，
# 那些事件會在下一次門禁突然「通過」placeholder_content 檢查，
# 未潤稿的佔位文字就這樣上線了。這一行的舊寫法是相容包袱，不要清。
PLACEHOLDER_RE = re.compile(
    r"待編輯|待编辑|待補充|待补充|TBD|TODO|placeholder", re.I)


def parse_note(text):
    """回 (frontmatter_dict, body_str)。非 frontmatter 檔回 ({}, text)。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[3:end]) or {}
    return fm, text[end + 4:]


def dump_frontmatter(fm):
    return yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
