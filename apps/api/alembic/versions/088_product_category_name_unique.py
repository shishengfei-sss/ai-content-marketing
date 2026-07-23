"""088 product_categories tenant+name unique

Revision ID: 088
Revises: 087
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "088"
down_revision: Union[str, None] = "087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "product_categories" not in inspector.get_table_names():
        return

    rows = conn.execute(
        sa.text(
            """
            SELECT id, tenant_id, name, created_at
            FROM product_categories
            ORDER BY tenant_id, name, created_at ASC
            """
        )
    ).fetchall()
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (str(row.tenant_id), str(row.name))
        if key not in seen:
            seen[key] = 0
            continue
        seen[key] += 1
        new_name = f"{row.name}-dup{seen[key]}"
        while (str(row.tenant_id), new_name) in seen:
            seen[key] += 1
            new_name = f"{row.name}-dup{seen[key]}"
        seen[(str(row.tenant_id), new_name)] = 0
        conn.execute(
            sa.text("UPDATE product_categories SET name = :name WHERE id = :id"),
            {"name": new_name[:100], "id": row.id},
        )

    indexes = {ix["name"] for ix in inspector.get_indexes("product_categories")}
    uniques = {uq["name"] for uq in inspector.get_unique_constraints("product_categories")}
    if "uq_product_categories_tenant_name" in indexes or "uq_product_categories_tenant_name" in uniques:
        return

    with op.batch_alter_table("product_categories") as batch_op:
        batch_op.create_unique_constraint(
            "uq_product_categories_tenant_name",
            ["tenant_id", "name"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "product_categories" not in inspector.get_table_names():
        return
    uniques = {uq["name"] for uq in inspector.get_unique_constraints("product_categories")}
    indexes = {ix["name"] for ix in inspector.get_indexes("product_categories")}
    if "uq_product_categories_tenant_name" not in uniques and "uq_product_categories_tenant_name" not in indexes:
        return
    with op.batch_alter_table("product_categories") as batch_op:
        batch_op.drop_constraint("uq_product_categories_tenant_name", type_="unique")
