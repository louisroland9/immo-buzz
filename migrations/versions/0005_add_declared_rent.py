"""Add the declared monthly rent column.

Store the current rent declared in the listing text alongside the estimated
value. ``monthly_rent`` stays ``NULL`` when the source does not mention it.

Revision ID: 0005_declared_rent
Revises: 0004_declared_tax
Create Date: 2026-11-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_declared_rent"
down_revision = "0004_declared_tax"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("listing")
    if not columns:
        # Fresh databases get the complete table from SQLModel.create_all().
        return

    if "monthly_rent" not in columns:
        op.add_column("listing", sa.Column("monthly_rent", sa.Float(), nullable=True))


def downgrade() -> None:
    columns = _columns("listing")
    if "monthly_rent" in columns:
        op.drop_column("listing", "monthly_rent")
