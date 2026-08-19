"""演示种子脚本打印的 Web / H5 入口基址（本机 vs 内网演示机）。"""
from __future__ import annotations

import os

_DEMO201_H5 = "http://192.168.20.201:8089"
_DEMO201_WEB = "http://192.168.20.201:8088"


def demo_origins() -> tuple[str, str]:
    """返回 (h5_origin, web_origin)。"""
    preset = os.environ.get("SHOP_DEMO_ENV", "").strip().lower()
    if preset in {"demo201", "201", "demo-server"}:
        return _DEMO201_H5, _DEMO201_WEB
    h5 = os.environ.get("SHOP_DEMO_H5_ORIGIN", "http://localhost:5174").rstrip("/")
    web = os.environ.get("SHOP_DEMO_WEB_ORIGIN", "http://localhost:5173").rstrip("/")
    return h5, web


def h5_link(path: str) -> str:
    h5, _ = demo_origins()
    if not path.startswith("/"):
        path = "/" + path
    return f"{h5}{path}"


def web_link(path: str) -> str:
    _, web = demo_origins()
    if not path.startswith("/"):
        path = "/" + path
    return f"{web}{path}"
