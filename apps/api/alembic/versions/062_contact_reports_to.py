"""062 contacts.reports_to_contact_id for decision chain (v0.9 P2-06)

Revision ID: 062
Revises: 061
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "062"
down_revision: Union[str, None] = "061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reports_to_contact_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_contacts_reports_to_contact_id",
            "contacts",
            ["reports_to_contact_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_contacts_reports_to_contact_id", ["reports_to_contact_id"])


def downgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.drop_index("ix_contacts_reports_to_contact_id")
        batch_op.drop_constraint("fk_contacts_reports_to_contact_id", type_="foreignkey")
        batch_op.drop_column("reports_to_contact_id")
