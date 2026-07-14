"""056 tags + entity_tags (v0.9 P1)

Revision ID: 056
Revises: 055
"""

from __future__ import annotations

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tags_tenant_name"),
    )
    op.create_index("ix_tags_tenant_id", "tags", ["tenant_id"])

    op.create_table(
        "entity_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "entity_type", "entity_id", "tag_id", name="uq_entity_tags"
        ),
    )
    op.create_index("ix_entity_tags_tenant_id", "entity_tags", ["tenant_id"])
    op.create_index("ix_entity_tags_entity", "entity_tags", ["entity_type", "entity_id"])

    # 将 customers.tags JSON 列表迁移到规范表（尽力而为，失败跳过）
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, tenant_id, tags, created_by_user_id FROM customers WHERE tags IS NOT NULL")).fetchall()
    tag_cache: dict[tuple, object] = {}
    for row in rows:
        customer_id, tenant_id, tags_raw, created_by = row[0], row[1], row[2], row[3]
        names: list[str] = []
        if isinstance(tags_raw, list):
            names = [str(x).strip() for x in tags_raw if str(x).strip()]
        elif isinstance(tags_raw, str):
            try:
                parsed = json.loads(tags_raw)
                if isinstance(parsed, list):
                    names = [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                names = [p.strip() for p in tags_raw.split(",") if p.strip()]
        for name in names:
            key = (str(tenant_id), name)
            tag_id = tag_cache.get(key)
            if tag_id is None:
                tag_id = uuid.uuid4()
                bind.execute(
                    sa.text(
                        "INSERT INTO tags (id, tenant_id, name, color, category) VALUES (:id, :tid, :name, NULL, NULL)"
                    ),
                    {"id": str(tag_id), "tid": str(tenant_id), "name": name},
                )
                tag_cache[key] = tag_id
            bind.execute(
                sa.text(
                    "INSERT INTO entity_tags (id, tenant_id, entity_type, entity_id, tag_id, created_by_user_id) "
                    "VALUES (:id, :tid, 'customer', :eid, :tag_id, :uid)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": str(tenant_id),
                    "eid": str(customer_id),
                    "tag_id": str(tag_id),
                    "uid": str(created_by) if created_by is not None else None,
                },
            )


def downgrade() -> None:
    op.drop_index("ix_entity_tags_entity", table_name="entity_tags")
    op.drop_index("ix_entity_tags_tenant_id", table_name="entity_tags")
    op.drop_table("entity_tags")
    op.drop_index("ix_tags_tenant_id", table_name="tags")
    op.drop_table("tags")
