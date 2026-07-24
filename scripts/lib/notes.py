# -*- coding: utf-8 -*-
"""notes.py — Event/Source note 的 frontmatter 解析（共用）。"""
from __future__ import annotations

import yaml


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
