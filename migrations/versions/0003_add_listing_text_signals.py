"""Store the source text signals used by the condition detection.

Add the raw description, the energy class and the ``workToDo`` flag so the
renovation state can be recomputed without fetching the listing again.

Revision ID: 0003_listing_text
Revises: 0002_net_yield
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_listing_text"
down_revision = "0002_net_yield"
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

    if "description" not in columns:
        op.add_column("listing", sa.Column("description", sa.Text(), nullable=True))
    if "energy_class" not in columns:
        op.add_column("listing", sa.Column("energy_class", sa.String(), nullable=True))
    if "works_signalled" not in columns:
        op.add_column(
            "listing", sa.Column("works_signalled", sa.Boolean(), nullable=True)
        )


def downgrade() -> None:
    columns = _columns("listing")
    for column in ("works_signalled", "energy_class", "description"):
        if column in columns:
            op.drop_column("listing", column)
