#!/usr/bin/env python3
"""换平台/形态改稿：识别与 schema。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

from tests.http_client import check
from app.schemas import ContentReviseRequest
from app.services.agent.preflight_service import is_content_revise_request
from app.services.content_revise_service import _REVISE_SYSTEM


def main() -> int:
    results: list[bool] = []
    phrase = "输出视频脚本"
    results.append(check("VADAPT-1 输出视频脚本算改稿", is_content_revise_request(phrase), ""))
    results.append(
        check(
            "VADAPT-2 改成小红书笔记算改稿",
            is_content_revise_request("改成小红书笔记"),
            "",
        )
    )
    req = ContentReviseRequest(
        instruction=phrase,
        platform="xhs",
        content_format="video_script",
        video_duration_sec=30,
    )
    results.append(check("VADAPT-3 schema 接受 platform", req.platform == "xhs", ""))
    results.append(check("VADAPT-4 schema 接受 format", req.content_format == "video_script", ""))
    results.append(check("VADAPT-5 改稿 system 含换平台", "换平台" in _REVISE_SYSTEM or "形态" in _REVISE_SYSTEM, ""))

    web = (API_ROOT.parent / "web" / "src" / "views" / "Create.vue").read_text(encoding="utf-8")
    mp = (API_ROOT.parent / "mp" / "src" / "pages" / "create" / "create.vue").read_text(encoding="utf-8")
    results.append(check("VADAPT-6 Web 有 FORMAT_ADAPT_RE", "FORMAT_ADAPT_RE" in web, ""))
    results.append(check("VADAPT-7 Web 有 parseAdaptTarget", "parseAdaptTarget" in web, ""))
    results.append(check("VADAPT-8 H5 有 parseAdaptTarget", "parseAdaptTarget" in mp, ""))
    results.append(check("VADAPT-9 Web 改稿传 content_format", "content_format:" in web and "parseAdaptTarget" in web, ""))

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_format_adapt: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
