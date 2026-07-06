"""Agent Tool Registry 单元测试。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))

from fastapi import HTTPException

from app.services.agent.tools import (
    TOOL_REGISTRY,
    AgentToolContext,
    execute_tool,
    list_available_tools,
)


class _Role:
    def __init__(self, codes: list[str]):
        self.permissions = [type("P", (), {"permission_code": c})() for c in codes]


class _Membership:
    def __init__(self, codes: list[str]):
        self.role = _Role(codes)


def _ctx(perms: list[str]) -> AgentToolContext:
    return AgentToolContext(
        db=None,
        tenant_id=uuid4(),
        user=type("U", (), {"id": uuid4()})(),
        membership=_Membership(perms),
        permissions=frozenset(perms),
    )


def test_registry_at_least_eight_tools():
    assert len(TOOL_REGISTRY) >= 8


def test_list_tools_excludes_publish_without_permission():
    admin_tools = {t["name"] for t in list_available_tools(_ctx(["content.create", "content.publish"]))}
    editor_tools = {t["name"] for t in list_available_tools(_ctx(["content.create", "content.view_own"]))}
    assert "publish_content" in admin_tools
    assert "publish_content" not in editor_tools


async def _run_get_quota():
    from app.database import SessionLocal
    from app.models import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).first()
        if not tenant:
            return
        membership = _Membership(["content.create"])
        tool_ctx = AgentToolContext(
            db=db,
            tenant_id=tenant.id,
            user=type("U", (), {"id": uuid4()})(),
            membership=membership,
            permissions=frozenset(["content.create"]),
        )
        result = await execute_tool(tool_ctx, "get_quota", {})
        assert "used_count" in result
        assert "remaining" in result
    finally:
        db.close()


def test_get_quota_tool():
    asyncio.run(_run_get_quota())


async def _run_revise_not_found():
    from app.database import SessionLocal
    from app.models import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).first()
        if not tenant:
            return
        tool_ctx = AgentToolContext(
            db=db,
            tenant_id=tenant.id,
            user=type("U", (), {"id": uuid4()})(),
            membership=_Membership(["content.edit"]),
            permissions=frozenset(["content.edit"]),
        )
        try:
            await execute_tool(
                tool_ctx,
                "revise_content",
                {"content_id": str(uuid4()), "instruction": "缩短"},
            )
            assert False, "expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
    finally:
        db.close()


def test_revise_content_not_found():
    asyncio.run(_run_revise_not_found())


def test_revise_content_tool_schema():
    from app.services.agent.tools import TOOL_REGISTRY

    spec = TOOL_REGISTRY["revise_content"]
    assert "content_id" in spec.parameters["properties"]


def test_unknown_tool_raises():
    try:
        asyncio.run(execute_tool(_ctx(["content.create"]), "no_such_tool", {}))
        assert False, "expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 404
