"""067 contract_templates + migrate contract.file_url to attachments (v1.0 P0)

Revision ID: 067
Revises: 066

file_url 列保留兼容；命中的 URL 写入 attachments（entity_type=contract）。
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "067"
down_revision: Union[str, None] = "066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contract_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_templates_tenant_id", "contract_templates", ["tenant_id"])

    # file_url → attachments（去重：同路径不重复写入）
    conn = op.get_bind()
    contracts = conn.execute(
        sa.text(
            """
            SELECT id, tenant_id, file_url, created_by_user_id
            FROM contracts
            WHERE file_url IS NOT NULL AND TRIM(file_url) != '' AND deleted_at IS NULL
            """
        )
    ).fetchall()
    for row in contracts:
        cid, tenant_id, file_url, uploader = row[0], row[1], row[2], row[3]
        exists = conn.execute(
            sa.text(
                """
                SELECT 1 FROM attachments
                WHERE tenant_id = :tid AND entity_type = 'contract'
                  AND entity_id = :eid AND storage_path = :path
                LIMIT 1
                """
            ),
            {"tid": str(tenant_id), "eid": str(cid), "path": file_url},
        ).fetchone()
        if exists:
            continue
        name = file_url.rstrip("/").split("/")[-1] or "contract-file"
        if len(name) > 255:
            name = name[:255]
        conn.execute(
            sa.text(
                """
                INSERT INTO attachments
                  (id, tenant_id, entity_type, entity_id, file_name, file_size, file_type,
                   storage_path, uploaded_by_user_id, created_at)
                VALUES
                  (:id, :tid, 'contract', :eid, :fname, 0, NULL, :path, :uid, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tid": str(tenant_id),
                "eid": str(cid),
                "fname": name,
                "path": file_url,
                "uid": str(uploader),
            },
        )


def downgrade() -> None:
    op.drop_index("ix_contract_templates_tenant_id", table_name="contract_templates")
    op.drop_table("contract_templates")
