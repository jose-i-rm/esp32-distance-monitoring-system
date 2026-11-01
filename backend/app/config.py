from functools import lru_cache

from pydantic import field_validator
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
