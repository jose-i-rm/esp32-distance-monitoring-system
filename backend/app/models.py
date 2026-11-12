from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Measurement(Base):
    """Lectura de distancia enviada por la ESP32-CAM."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    distance_cm: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Measurement id={self.id} timestamp={self.timestamp} distance_cm={self.distance_cm}>"


class CameraEvent(Base):
    """Evento reportado por la cámara PTZ Tuya (detección humanoide, sonido anormal, alarma…)."""

    __tablename__ = "camera_events"
    __table_args__ = (
        UniqueConstraint("device_id", "event_time", "code", "event_type", name="uq_camera_events_dedup"),
        Index("ix_camera_events_device_time", "device_id", "event_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Momento del evento según Tuya (UTC).
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Tipo normalizado: humanoid_detection, abnormal_sound, motion_detection, alarm, disalarm, online, offline, dp_report…
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Código del DP de origen (alarm_message, movement_detect_pic…) o tipo de log (online/offline).
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    # Comando Tuya original del mensaje de alarma (ipc_human, ipc_bang…).
    tuya_cmd: Mapped[str | None] = mapped_column(String(40), nullable=True)
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Referencia a la imagen de alarma en el almacenamiento de Tuya (bucket + ruta).
    image_bucket: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Clave AES de la imagen. Dato sensible: nunca se expone en la API.
    image_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="tuya_logs")
    # Respuesta original de Tuya para auditoría (sin secretos del proyecto).
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<CameraEvent id={self.id} type={self.event_type} time={self.event_time}>"
