"""Crear tabla radar_captures (fotos automáticas radar -> cámara PTZ)

Revision ID: 0003_create_radar_captures
Revises: 0002_create_camera_events
Create Date: 2026-11-19 11:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_create_radar_captures"
down_revision: Union[str, None] = "0002_create_camera_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "radar_captures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_epoch", sa.Integer(), nullable=False, unique=True),
        sa.Column("angle_deg", sa.Integer(), nullable=False),
        sa.Column("distance_cm", sa.Float(), nullable=False),
        sa.Column("previous_cm", sa.Float(), nullable=True),
        sa.Column("preset", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(255), nullable=True),
        sa.Column("image", sa.LargeBinary(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_radar_captures_captured_at", "radar_captures", ["captured_at"])


def downgrade() -> None:
    op.drop_index("ix_radar_captures_captured_at", table_name="radar_captures")
    op.drop_table("radar_captures")
