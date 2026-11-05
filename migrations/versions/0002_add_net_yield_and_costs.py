"""Add net yield, property tax and condominium fee estimates.

Rename ``estimated_yield`` to ``estimated_gross_yield`` and add the new cost
columns introduced by the reworked yield engine.

Revision ID: 0002_net_yield
Revises: 0001_add_sold
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_net_yield"
down_revision = "0001_add_sold"
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

    if "estimated_yield" in columns and "estimated_gross_yield" not in columns:
        op.alter_column(
            "listing",
            "estimated_yield",
            new_column_name="estimated_gross_yield",
        )

    columns = _columns("listing")
    if "estimated_net_yield" not in columns:
        op.add_column(
            "listing", sa.Column("estimated_net_yield", sa.Float(), nullable=True)
        )
        op.create_index(
            "ix_listing_estimated_net_yield",
            "listing",
            ["estimated_net_yield"],
            unique=False,
        )
    if "estimated_property_tax" not in columns:
        op.add_column(
            "listing", sa.Column("estimated_property_tax", sa.Float(), nullable=True)
        )
    if "estimated_condo_fees" not in columns:
        op.add_column(
            "listing", sa.Column("estimated_condo_fees", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    columns = _columns("listing")
    if "estimated_condo_fees" in columns:
        op.drop_column("listing", "estimated_condo_fees")
    if "estimated_property_tax" in columns:
        op.drop_column("listing", "estimated_property_tax")
    if "estimated_net_yield" in columns:
        op.drop_index("ix_listing_estimated_net_yield", table_name="listing")
        op.drop_column("listing", "estimated_net_yield")
    if "estimated_gross_yield" in columns and "estimated_yield" not in columns:
        op.alter_column(
            "listing",
            "estimated_gross_yield",
            new_column_name="estimated_yield",
        )
