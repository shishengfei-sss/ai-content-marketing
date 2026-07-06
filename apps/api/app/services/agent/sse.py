"""Server-Sent Events 格式化辅助。"""

from __future__ import annotations

import json
from typing import Any


def format_sse(event: str, data: Any) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"
