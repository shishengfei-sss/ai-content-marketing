"""105 shop merchant suspend/close audit fields (M2)

Revision ID: 105
Revises: 104
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "105"
down_revision: Union[str, None] = "104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("shop_merchant_accounts", "suspended_at"):
        op.add_column(
            "shop_merchant_accounts", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
        )
    if not _has_column("shop_merchant_accounts", "closed_at"):
        op.add_column("shop_merchant_accounts", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("shop_merchant_accounts", "closed_by"):
        op.add_column("shop_merchant_accounts", sa.Column("closed_by", sa.Uuid(), nullable=True))
    if not _has_column("shop_merchant_accounts", "close_reason_code"):
        op.add_column(
            "shop_merchant_accounts", sa.Column("close_reason_code", sa.String(length=40), nullable=True)
        )
    if not _has_column("shop_merchant_accounts", "close_reason_text"):
        op.add_column("shop_merchant_accounts", sa.Column("close_reason_text", sa.Text(), nullable=True))
    # FK 可能已存在（部分失败后重跑）
    try:
        op.create_foreign_key(
            "fk_shop_merchant_accounts_closed_by",
            "shop_merchant_accounts",
            "users",
            ["closed_by"],
            ["id"],
        )
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_constraint("fk_shop_merchant_accounts_closed_by", "shop_merchant_accounts", type_="foreignkey")
    except Exception:
        pass
    for col in ("close_reason_text", "close_reason_code", "closed_by", "closed_at", "suspended_at"):
        if _has_column("shop_merchant_accounts", col):
            op.drop_column("shop_merchant_accounts", col)
