from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno o `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ESP32 Distance Monitoring System"
    app_version: str = __version__
    environment: str = "development"

    database_url: str = "postgresql+psycopg://esp32:esp32@localhost:5432/esp32_monitoring"

    # Si está vacía, el endpoint POST no exige autenticación (solo recomendado en desarrollo).
    device_api_key: str = ""

    # Orígenes permitidos separados por coma. Ej: "https://usuario.github.io,http://localhost:5500"
    cors_origins: str = "*"

    # Crea las tablas al iniciar (útil con SQLite en desarrollo). En producción usar Alembic.
    auto_create_tables: bool = False

    # Clave de administración para los endpoints de cámara (cabecera X-API-Key).
    # Si está vacía, los endpoints /api/camera/* responden 503 (fail-closed).
    admin_api_key: str = ""

    # Tuya Cloud (proyecto Custom Development). Definir SOLO en .env o en el gestor de secretos.
    tuya_access_id: str = ""
    tuya_access_secret: SecretStr = SecretStr("")
    tuya_device_id: str = ""
    tuya_endpoint: str = "https://openapi.tuyaus.com"
    # Sondeo periódico de eventos de la cámara hacia PostgreSQL (0 = desactivado).
    tuya_poll_interval_seconds: int = 0
    # Pausa mínima entre comandos PTZ y duración máxima de un movimiento.
    ptz_min_interval_seconds: float = 1.0
    ptz_max_duration_ms: int = 3000

    @field_validator("tuya_endpoint")
    @classmethod
    def require_https_endpoint(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value and not value.startswith("https://"):
            raise ValueError("TUYA_ENDPOINT debe usar HTTPS")
        return value

    @property
    def tuya_configured(self) -> bool:
        return bool(self.tuya_access_id and self.tuya_access_secret.get_secret_value() and self.tuya_device_id)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Render/Railway/Fly entregan "postgres://" o "postgresql://"; SQLAlchemy necesita el driver psycopg v3.
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
