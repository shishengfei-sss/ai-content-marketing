#!/usr/bin/env python3
"""v0.6 Phase B/C 验收：顾问配置 API、prompt 组装、创作页 UI（TADV-CFG）。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_CREATE = API_ROOT.parent / "web" / "src" / "views" / "Create.vue"
MP_CREATE = API_ROOT.parent / "mp" / "src" / "pages" / "create" / "create.vue"

os.environ["VERIFY_LIVE_API"] = "0"
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req

WELCOME_MARKERS = ("营销创作顾问", "选题", "公众号", "合规")


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def step_va1_api(results: list[bool]) -> None:
    token = login("13900000099", "test123456")
    code, data = req("GET", "/assistants", token=token)
    results.append(check("VA1-1 GET /assistants 200", code == 200, str(data)))
    if code == 200 and isinstance(data, list):
        active = data
        results.append(check("VA1-2 活跃顾问 ≤1", len(active) <= 1, str(len(active))))
        if active:
            welcome = active[0].get("welcome_message") or ""
            has_caps = sum(1 for m in WELCOME_MARKERS if m in welcome) >= 2
            results.append(
                check(
                    "VA1-3 welcome_message 含能力描述",
                    has_caps,
                    welcome[:120],
                )
            )


def step_va1_prompt(results: list[bool]) -> None:
    from app.services.prompt_builder import build_system_prompt

    prompt = build_system_prompt("wechat", content_format="article", assistant=None)
    results.append(
        check(
            "VA1-4 默认 prompt 无财税营销专家",
            "财税营销专家" not in prompt,
            prompt[:80],
        )
    )
    results.append(
        check(
            "VA1-5 默认 prompt 含通用顾问语义",
            "营销" in prompt or "创作顾问" in prompt,
            "",
        )
    )


def step_va1_ui(results: list[bool]) -> None:
    web = WEB_CREATE.read_text(encoding="utf-8") if WEB_CREATE.is_file() else ""
    mp = MP_CREATE.read_text(encoding="utf-8") if MP_CREATE.is_file() else ""
    results.append(
        check(
            "VA1-6 Web 无助手切换 UI",
            "assistant-picker--clickable" not in web.split("<style")[0]
            and "industryCode" not in web,
            "Create.vue",
        )
    )
    results.append(
        check(
            "VA1-7 Web 使用 API welcome",
            "buildWelcomeText" not in web or "welcome_message" in web,
            "",
        )
    )
    results.append(
        check(
            "VA1-8 H5 无行业助手切换",
            "industryCode" not in mp and "showAssistantPicker" not in mp,
            "create.vue",
        )
    )
    results.append(
        check(
            "VA1-9 Web 已移除创作场景 UI",
            "loadSceneTemplates" not in web and "scene-panel" not in web and "templatesApi" not in web,
            "Create.vue",
        )
    )
    results.append(
        check(
            "VA1-10 H5 已移除创作场景 UI",
            "loadSceneTemplates" not in mp and "scene-bar" not in mp and "scene-sheet" not in mp,
            "create.vue",
        )
    )


STEPS = {
    "1a-api": step_va1_api,
    "1a-prompt": step_va1_prompt,
    "1a-ui": step_va1_ui,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="v0.6 advisor config verification")
    parser.add_argument("--step", choices=list(STEPS.keys()))
    args = parser.parse_args()

    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_1a: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
