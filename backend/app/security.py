import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_device_api_key(
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Valida la API Key del dispositivo cuando DEVICE_API_KEY está configurada."""
    expected = settings.device_api_key
    if not expected:
        return
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o ausente.",
            headers={"WWW-Authenticate": "API-Key"},
        )


def verify_admin_api_key(
    api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Protege los endpoints de cámara. Fail-closed: sin ADMIN_API_KEY configurada responde 503."""
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Endpoints de cámara deshabilitados: configure ADMIN_API_KEY.",
        )
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o ausente.",
            headers={"WWW-Authenticate": "API-Key"},
        )
