"""数据范围：本人 vs 全公司。"""

from __future__ import annotations

from sqlalchemy.orm import Query

from app.dependencies import TenantContext


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def apply_content_list_scope(query: Query, ctx: TenantContext) -> Query:
    perms = _perm_set(ctx)
    if "content.list_all" not in perms:
        query = query.filter_by(author_id=ctx.user.id)
    return query


def can_view_content(ctx: TenantContext, author_id) -> bool:
    perms = _perm_set(ctx)
    if "content.view_all" in perms:
        return True
    if "content.view_own" in perms:
        return author_id == ctx.user.id
    return False


def apply_stats_scope(query: Query, ctx: TenantContext, view_all_perm: str) -> Query:
    perms = _perm_set(ctx)
    if view_all_perm not in perms:
        query = query.filter_by(author_id=ctx.user.id)
    return query
