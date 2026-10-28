"""Add the sold flag to listings.

Revision ID: 0001_add_sold
Revises:
Create Date: 2026-10-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_add_sold"
down_revision = None
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("listing")
    if not columns or "sold" in columns:
        # Fresh databases get the complete table from SQLModel.create_all().
        return

    op.add_column(
        "listing",
        sa.Column("sold", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_listing_sold", "listing", ["sold"], unique=False)


def downgrade() -> None:
    columns = _columns("listing")
    if "sold" not in columns:
        return

    op.drop_index("ix_listing_sold", table_name="listing")
    op.drop_column("listing", "sold")
