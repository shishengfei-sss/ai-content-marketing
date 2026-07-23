"""入库文本净化，降低存储型 XSS 风险。"""
from __future__ import annotations

import html
import re

_SCRIPT_RE = re.compile(r"</?\s*script\b[^>]*>", re.IGNORECASE)
_EVENT_RE = re.compile(r"\son\w+\s*=", re.IGNORECASE)


def sanitize_plain_text(value: str | None) -> str | None:
    """去掉危险标签并转义 HTML 实体，保留可读文本。"""
    if value is None:
        return None
    text = str(value)
    text = _SCRIPT_RE.sub("", text)
    text = _EVENT_RE.sub(" ", text)
    # 转义后前端默认文本插值安全；测试断言不应再含字面 <script>
    text = html.escape(text, quote=False)
    return text.strip()
