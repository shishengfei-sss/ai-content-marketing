"""创作方向数量：默认 3～5，用户指定时 1～10。"""

from __future__ import annotations

import re

MAX_PROPOSAL_COUNT = 10
MIN_PROPOSAL_COUNT = 1
DEFAULT_RANGE_MIN = 3
DEFAULT_RANGE_MAX = 5

_COUNT_RE = re.compile(
    r"(\d+)\s*(?:个|条)?\s*(?:个)?(?:创作)?(?:方向|标题|方案|备选|选题|角度)",
)
_COUNT_SIMPLE_RE = re.compile(r"(?:给出|生成|来|要|需要)\s*(\d+)\s*个")


def clamp_proposal_count(value: int) -> int:
    return max(MIN_PROPOSAL_COUNT, min(MAX_PROPOSAL_COUNT, int(value)))


def extract_proposal_count_from_text(text: str) -> int | None:
    """从用户描述中提取明确数量；未提及则返回 None（使用默认 3～5）。"""
    if not text or not text.strip():
        return None
    for pattern in (_COUNT_RE, _COUNT_SIMPLE_RE):
        match = pattern.search(text)
        if match:
            try:
                return clamp_proposal_count(int(match.group(1)))
            except (TypeError, ValueError):
                continue
    return None


def resolve_proposal_count(
    *,
    explicit: int | None = None,
    text: str | None = None,
) -> int | None:
    """返回指定数量；None 表示默认 3～5。"""
    if explicit is not None:
        try:
            return clamp_proposal_count(int(explicit))
        except (TypeError, ValueError):
            pass
    if text:
        found = extract_proposal_count_from_text(text)
        if found is not None:
            return found
    return None
