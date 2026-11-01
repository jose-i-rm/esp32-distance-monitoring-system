"""Crear tabla measurements

Revision ID: 0001_create_measurements
Revises:
Create Date: 2026-11-01 11:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_measurements"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("distance_cm", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_measurements_timestamp", "measurements", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_measurements_timestamp", table_name="measurements")
    op.drop_table("measurements")
