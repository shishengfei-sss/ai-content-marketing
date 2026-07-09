"""预检验收：创作页 preflight + UI 去快捷选题/场景。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_CREATE = API_ROOT.parent / "web" / "src" / "views" / "Create.vue"
MP_CREATE = API_ROOT.parent / "mp" / "src" / "pages" / "create" / "create.vue"
WEB_CLIENT = API_ROOT.parent / "web" / "src" / "api" / "client.js"
MP_API = API_ROOT.parent / "mp" / "src" / "utils" / "api.js"
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    web_vue = WEB_CREATE.read_text(encoding="utf-8") if WEB_CREATE.is_file() else ""
    mp_vue = MP_CREATE.read_text(encoding="utf-8") if MP_CREATE.is_file() else ""
    web_client = WEB_CLIENT.read_text(encoding="utf-8") if WEB_CLIENT.is_file() else ""
    mp_api = MP_API.read_text(encoding="utf-8") if MP_API.is_file() else ""

    results.append(
        check(
            "VP1-1 Web 无快捷选题",
            "type: 'quick'" not in web_vue and "handleQuickStart" not in web_vue,
            "Create.vue",
        )
    )
    results.append(
        check(
            "VP1-2 Web 无场景选择",
            'v-model="scene"' not in web_vue
            and "filteredScenes" not in web_vue
            and "runPreflight" in web_vue,
            "Create.vue",
        )
    )
    results.append(
        check(
            "VP1-3 H5 无快捷选题/场景",
            "handleQuick" not in mp_vue
            and "scenePickerOptions" not in mp_vue
            and "runPreflight" in mp_vue,
            "create.vue",
        )
    )
    results.append(
        check(
            "VP1-4 client preflight API",
            "preflight" in web_client and "preflight" in mp_api,
            "api",
        )
    )

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=token,
        body={"industry_code": "finance", "title": "Preflight E2E"},
    )
    sid = session.get("id") if code == 200 else None

    if sid:
        code1, pre1 = req(
            "POST",
            f"/agent/sessions/{sid}/preflight",
            token=token,
            body={
                "message": "你好",
                "platform": "wechat",
                "content_format": "article",
                "llm_source": "platform",
            },
        )
        results.append(
            check(
                "VP1-5 寒暄 clarify",
                code1 == 200 and pre1.get("ready") is False and pre1.get("action") == "clarify",
                str(pre1),
            )
        )

        code2, pre2 = req(
            "POST",
            f"/agent/sessions/{sid}/preflight",
            token=token,
            body={
                "message": "抖音视频脚本：新公司注册与税务合规，面向首次创业老板",
                "platform": "douyin",
                "content_format": "video_script",
                "llm_source": "platform",
            },
        )
        results.append(
            check(
                "VP1-6 充分信息 proceed",
                code2 == 200 and pre2.get("ready") is True and bool(pre2.get("topic")),
                str(pre2),
            )
        )

    proc = subprocess.run([sys.executable, "tests/verify_wf3.py"], cwd=API_ROOT)
    results.append(check("VP1-7 回归 verify_wf3", proc.returncode == 0, str(proc.returncode)))

    failed = [i for i, ok in enumerate(results) if not ok]
    if failed:
        print(f"\n=== Preflight 失败 {len(failed)}/{len(results)} ===")
        return 1
    print("\n=== Preflight 全部通过 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
