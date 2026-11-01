from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["Salud"])


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def health(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
        timestamp=datetime.now(timezone.utc),
    )
