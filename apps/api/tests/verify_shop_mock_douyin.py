#!/usr/bin/env python3
"""抖音 Mock 验收：Stub 配置、发布流程、状态查询、数据同步、视频管理。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.shop_test_config import DOUYIN_STUB  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _find_endpoint(path_substring: str):
    """从 DOUYIN_STUB 中按路径子串查找端点。"""
    for ep in DOUYIN_STUB.endpoints:
        if path_substring in ep.path:
            return ep
    return None


def main() -> int:
    results: list[bool] = []

    # ── MOCK-DY-1 Stub 配置存在 & 内容发布端点 ──
    results.append(
        check(
            "MOCK-DY-1 抖音Stub配置存在",
            DOUYIN_STUB.name == "douyin"
            and DOUYIN_STUB.base_url == "http://mock.douyin.local"
            and len(DOUYIN_STUB.endpoints) == 5,
            f"name={DOUYIN_STUB.name}, endpoints={len(DOUYIN_STUB.endpoints)}",
        )
    )

    publish_ep = _find_endpoint("/api/publish")
    results.append(
        check(
            "MOCK-DY-1 发布流程Mock响应",
            publish_ep is not None
            and publish_ep.method == "POST"
            and publish_ep.response_status == 200
            and publish_ep.response_body.get("code") == 0
            and publish_ep.response_body.get("data", {}).get("publish_status") == "publishing",
            f"publish_status={publish_ep.response_body.get('data', {}).get('publish_status') if publish_ep else 'N/A'}",
        )
    )

    # ── MOCK-DY-2 发布状态查询端点 ──
    status_ep = _find_endpoint("/api/status")
    results.append(
        check(
            "MOCK-DY-2 发布状态查询Mock响应",
            status_ep is not None
            and status_ep.method == "GET"
            and status_ep.response_status == 200
            and status_ep.response_body.get("data", {}).get("publish_status") == "published"
            and "video_url" in status_ep.response_body.get("data", {}),
            f"publish_status={status_ep.response_body.get('data', {}).get('publish_status') if status_ep else 'N/A'}",
        )
    )

    # ── MOCK-DY-3 数据同步端点 ──
    sync_ep = _find_endpoint("/api/data/sync")
    results.append(
        check(
            "MOCK-DY-3 数据同步Mock响应",
            sync_ep is not None
            and sync_ep.method == "POST"
            and sync_ep.response_status == 200
            and sync_ep.response_body.get("code") == 0
            and "synced_at" in sync_ep.response_body.get("data", {})
            and "metrics" in sync_ep.response_body.get("data", {}),
            f"synced_at={'present' if sync_ep and 'synced_at' in sync_ep.response_body.get('data', {}) else 'missing'}",
        )
    )

    # ── MOCK-DY-4 视频列表端点 ──
    list_ep = _find_endpoint("/api/video/list")
    results.append(
        check(
            "MOCK-DY-4 视频列表Mock响应",
            list_ep is not None
            and list_ep.method == "GET"
            and list_ep.response_status == 200
            and list_ep.response_body.get("data", {}).get("total") == 2
            and len(list_ep.response_body.get("data", {}).get("items", [])) == 2,
            f"total={list_ep.response_body.get('data', {}).get('total') if list_ep else 'N/A'}",
        )
    )

    # ── MOCK-DY-5 视频删除端点 ──
    delete_ep = None
    for ep in DOUYIN_STUB.endpoints:
        if ep.method == "DELETE" and "/api/video" in ep.path:
            delete_ep = ep
            break
    results.append(
        check(
            "MOCK-DY-5 视频删除Mock响应",
            delete_ep is not None
            and delete_ep.method == "DELETE"
            and delete_ep.response_status == 200
            and delete_ep.response_body.get("data", {}).get("deleted") is True,
            f"deleted={delete_ep.response_body.get('data', {}).get('deleted') if delete_ep else 'N/A'}",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
