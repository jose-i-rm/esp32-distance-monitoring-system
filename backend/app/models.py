from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, func
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
