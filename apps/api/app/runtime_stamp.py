"""运行时指纹：用于确认热重载是否真的加载了新代码。"""
from __future__ import annotations

from pathlib import Path

# 招标解析逻辑变更时请同步 bump（health + parse result_json 会带上）
TENDER_PARSER_VERSION = "2026-07-17-gac-product"


def health_payload() -> dict:
    api_root = Path(__file__).resolve().parent
    stamp_files = [
        api_root / "services" / "tender_parse_service.py",
        api_root / "main.py",
    ]
    mtimes = {}
    for p in stamp_files:
        try:
            mtimes[p.name] = int(p.stat().st_mtime)
        except OSError:
            mtimes[p.name] = None
    return {
        "status": "ok",
        "tender_parser_version": TENDER_PARSER_VERSION,
        "module_mtimes": mtimes,
    }
