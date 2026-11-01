from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import MeasurementCreate, MeasurementList, MeasurementRead
from app.security import verify_device_api_key

router = APIRouter(prefix="/api/v1/measurements", tags=["Mediciones"])


@router.post(
    "",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una medición",
    dependencies=[Depends(verify_device_api_key)],
)
def create_measurement(payload: MeasurementCreate, db: Session = Depends(get_db)) -> MeasurementRead:
    """Endpoint consumido por la ESP32-CAM cada 30 segundos."""
    return crud.create_measurement(db, payload)


@router.get("", response_model=MeasurementList, summary="Listar mediciones")
def list_measurements(
    limit: int = Query(100, ge=1, le=1000, description="Cantidad máxima de registros."),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación."),
    start: datetime | None = Query(None, description="Filtrar desde (ISO 8601)."),
    end: datetime | None = Query(None, description="Filtrar hasta (ISO 8601)."),
    db: Session = Depends(get_db),
) -> MeasurementList:
    """Devuelve el historial ordenado de la lectura más reciente a la más antigua."""
    items, total = crud.list_measurements(db, limit=limit, offset=offset, start=start, end=end)
    return MeasurementList(items=items, total=total, limit=limit, offset=offset)


@router.get("/latest", response_model=MeasurementRead, summary="Última medición")
def latest_measurement(db: Session = Depends(get_db)) -> MeasurementRead:
    measurement = crud.get_latest_measurement(db)
    if measurement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aún no hay mediciones registradas.")
    return measurement
