"""Store the listing coordinates.

Add the nullable latitude/longitude columns so a geo search (city + radius)
can be replayed or mapped without fetching the listings again.

Revision ID: 0006_coordinates
Revises: 0005_declared_rent
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_coordinates"
down_revision = "0005_declared_rent"
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

    if "latitude" not in columns:
        op.add_column("listing", sa.Column("latitude", sa.Float(), nullable=True))
    if "longitude" not in columns:
        op.add_column("listing", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    columns = _columns("listing")
    if "latitude" in columns:
        op.drop_column("listing", "latitude")
    if "longitude" in columns:
        op.drop_column("listing", "longitude")
