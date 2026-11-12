from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CameraEventRead(BaseModel):
    """Evento de cámara expuesto por la API (sin la clave AES de la imagen)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    event_time: datetime
    event_type: str
    code: str
    tuya_cmd: str | None = None
    value: str | None = None
    has_image: bool = False
    image_expires_at: datetime | None = None
    source: str
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def derive_has_image(cls, data: Any) -> Any:
        if hasattr(data, "image_path"):
            return {
                **{field: getattr(data, field, None) for field in cls.model_fields if field != "has_image"},
                "has_image": bool(data.image_path),
            }
        return data

    @field_validator("event_time", "created_at", "image_expires_at")
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class CameraEventList(BaseModel):
    items: list[CameraEventRead]
    total: int
    limit: int
    offset: int


class CameraSyncResult(BaseModel):
    fetched: int
    inserted: int


class CameraStatus(BaseModel):
    device_id: str
    name: str | None = None
    product_name: str | None = None
    category: str | None = None
    online: bool
    time_zone: str | None = None
    update_time: datetime | None = None
    status: dict[str, Any]


PtzDirection = Literal["up", "up_right", "right", "down_right", "down", "down_left", "left", "up_left", "stop"]


class PtzCommand(BaseModel):
    direction: PtzDirection | None = Field(None, description="Dirección del movimiento o `stop`.")
    duration_ms: int = Field(500, ge=0, le=3000, description="Duración del giro; luego se envía ptz_stop. 0 = continuo.")
    preset: int | None = Field(None, ge=1, le=6, description="Ir a la posición predefinida (ipc_preset_action).")

    @model_validator(mode="after")
    def exactly_one_action(self) -> "PtzCommand":
        if (self.direction is None) == (self.preset is None):
            raise ValueError("Indique `direction` o `preset` (solo uno).")
        return self


class PtzResult(BaseModel):
    action: str
    direction: str | None = None
    duration_ms: int | None = None
    preset: int | None = None


class StreamResponse(BaseModel):
    type: str
    url: str
    note: str = "URL temporal firmada por Tuya; expira en pocos minutos. No compartir."
