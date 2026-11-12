"""Crear tabla camera_events (eventos de la cámara PTZ Tuya)

Revision ID: 0002_create_camera_events
Revises: 0001_create_measurements
Create Date: 2026-11-11 13:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_camera_events"
down_revision: Union[str, None] = "0001_create_measurements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "camera_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("tuya_cmd", sa.String(40), nullable=True),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("image_bucket", sa.String(128), nullable=True),
        sa.Column("image_path", sa.String(512), nullable=True),
        sa.Column("image_key", sa.String(64), nullable=True),
        sa.Column("image_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("device_id", "event_time", "code", "event_type", name="uq_camera_events_dedup"),
    )
    op.create_index("ix_camera_events_event_time", "camera_events", ["event_time"])
    op.create_index("ix_camera_events_event_type", "camera_events", ["event_type"])
    op.create_index("ix_camera_events_device_time", "camera_events", ["device_id", "event_time"])


def downgrade() -> None:
    op.drop_index("ix_camera_events_device_time", table_name="camera_events")
    op.drop_index("ix_camera_events_event_type", table_name="camera_events")
    op.drop_index("ix_camera_events_event_time", table_name="camera_events")
    op.drop_table("camera_events")
