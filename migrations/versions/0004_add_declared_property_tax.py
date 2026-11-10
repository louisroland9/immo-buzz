"""Add the declared property tax column.

Store the property tax declared in the listing text alongside the estimated
value. ``property_tax`` stays ``NULL`` when the source does not mention it.

Revision ID: 0004_declared_tax
Revises: 0003_listing_text
Create Date: 2026-11-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_declared_tax"
down_revision = "0003_listing_text"
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

    if "property_tax" not in columns:
        op.add_column("listing", sa.Column("property_tax", sa.Float(), nullable=True))


def downgrade() -> None:
    columns = _columns("listing")
    if "property_tax" in columns:
        op.drop_column("listing", "property_tax")
