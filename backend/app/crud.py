from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Measurement
from app.schemas import MeasurementCreate


def _to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def create_measurement(db: Session, data: MeasurementCreate) -> Measurement:
    measurement = Measurement(timestamp=data.timestamp, distance_cm=round(data.distance_cm, 2))
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    return measurement


def list_measurements(
    db: Session,
    *,
    limit: int,
    offset: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[Measurement], int]:
    filters = []
    if start is not None:
        filters.append(Measurement.timestamp >= _to_utc(start))
    if end is not None:
        filters.append(Measurement.timestamp <= _to_utc(end))

    total = db.scalar(select(func.count()).select_from(Measurement).where(*filters)) or 0
    stmt = (
        select(Measurement)
        .where(*filters)
        .order_by(Measurement.timestamp.desc(), Measurement.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all()), total


def get_latest_measurement(db: Session) -> Measurement | None:
    stmt = select(Measurement).order_by(Measurement.timestamp.desc(), Measurement.id.desc()).limit(1)
    return db.scalars(stmt).first()
