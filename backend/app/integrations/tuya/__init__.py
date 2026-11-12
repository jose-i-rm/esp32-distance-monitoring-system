"""Integración con Tuya Cloud (cámara PTZ)."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.integrations.tuya.camera import CameraService
from app.integrations.tuya.client import TuyaClient, TuyaError, TuyaPermissionError

__all__ = ["CameraService", "TuyaClient", "TuyaError", "TuyaPermissionError", "get_camera_service"]


@lru_cache
def get_camera_service() -> CameraService | None:
    """Instancia única por proceso (reutiliza el token). ``None`` si Tuya no está configurado."""
    settings = get_settings()
    if not settings.tuya_configured:
        return None
    client = TuyaClient(
        settings.tuya_access_id,
        settings.tuya_access_secret.get_secret_value(),
        settings.tuya_endpoint,
    )
    return CameraService(
        client,
        settings.tuya_device_id,
        ptz_min_interval_seconds=settings.ptz_min_interval_seconds,
        ptz_max_duration_ms=settings.ptz_max_duration_ms,
    )
