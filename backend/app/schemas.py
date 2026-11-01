from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

# El HC-SR04 mide de forma fiable entre 2 y 400 cm; se deja margen para lecturas atípicas.
MIN_DISTANCE_CM = 0.0
MAX_DISTANCE_CM = 1000.0


class MeasurementCreate(BaseModel):
    timestamp: datetime = Field(
        ...,
        description="Momento de la lectura (ISO 8601). Si no incluye zona horaria se asume UTC.",
        examples=["2026-11-01T16:08:55Z"],
    )
    distance_cm: float = Field(
        ..., ge=MIN_DISTANCE_CM, le=MAX_DISTANCE_CM, description="Distancia medida en centímetros.", examples=[214.05]
    )

    @field_validator("timestamp")
    @classmethod
    def normalize_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    distance_cm: float
    created_at: datetime

    @field_validator("timestamp", "created_at")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        # Algunos motores (p. ej. SQLite) devuelven datetimes sin zona; se almacenan siempre en UTC.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class MeasurementList(BaseModel):
    items: list[MeasurementRead]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str
    timestamp: datetime
