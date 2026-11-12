from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.integrations.tuya import CameraService, TuyaError, TuyaPermissionError, get_camera_service
from app.integrations.tuya.camera import PtzRateLimited, SnapshotUnavailable
from app.schemas import (
    CameraEventList,
    CameraEventRead,
    CameraStatus,
    CameraSyncResult,
    PtzCommand,
    PtzResult,
    StreamResponse,
)
from app.security import verify_admin_api_key

# Todos los endpoints de cámara exigen ADMIN_API_KEY (contienen datos de privacidad y control físico).
router = APIRouter(prefix="/api/camera", tags=["Cámara PTZ Tuya"], dependencies=[Depends(verify_admin_api_key)])


def camera_service() -> CameraService:
    service = get_camera_service()
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración Tuya no configurada (TUYA_ACCESS_ID / TUYA_ACCESS_SECRET / TUYA_DEVICE_ID).",
        )
    return service


def _tuya_http_error(exc: TuyaError) -> HTTPException:
    if isinstance(exc, TuyaPermissionError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API de Tuya no autorizada para el proyecto [{exc.code}]: {exc.args[0]}",
        )
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Error de Tuya Cloud: {exc}")


@router.get("/status", response_model=CameraStatus, summary="Estado en vivo de la cámara")
def camera_status(service: CameraService = Depends(camera_service)) -> CameraStatus:
    try:
        return CameraStatus(**service.get_status())
    except TuyaError as exc:
        raise _tuya_http_error(exc) from exc


@router.get("/events", response_model=CameraEventList, summary="Historial de eventos guardados")
def camera_events(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None, max_length=40, description="humanoid_detection, abnormal_sound, alarm…"),
    start: datetime | None = Query(None, description="Desde (ISO 8601)."),
    end: datetime | None = Query(None, description="Hasta (ISO 8601)."),
    db: Session = Depends(get_db),
) -> CameraEventList:
    items, total = crud.list_camera_events(
        db, limit=limit, offset=offset, event_type=event_type, start=start, end=end
    )
    return CameraEventList(
        items=[CameraEventRead.model_validate(item) for item in items], total=total, limit=limit, offset=offset
    )


@router.post("/events/sync", response_model=CameraSyncResult, summary="Sincronizar eventos desde Tuya Cloud")
def sync_camera_events(
    service: CameraService = Depends(camera_service), db: Session = Depends(get_db)
) -> CameraSyncResult:
    try:
        return CameraSyncResult(**service.sync_events(db))
    except TuyaError as exc:
        raise _tuya_http_error(exc) from exc


@router.get("/latest", response_model=CameraEventRead, summary="Último evento de la cámara")
def latest_camera_event(
    event_type: str | None = Query(None, max_length=40), db: Session = Depends(get_db)
) -> CameraEventRead:
    event = crud.get_latest_camera_event(db, event_type)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aún no hay eventos de cámara.")
    return CameraEventRead.model_validate(event)


@router.post("/ptz", response_model=PtzResult, summary="Mover la cámara (PTZ) o ir a un preset")
def camera_ptz(command: PtzCommand, service: CameraService = Depends(camera_service)) -> PtzResult:
    try:
        return PtzResult(
            **service.ptz(direction=command.direction, preset=command.preset, duration_ms=command.duration_ms)
        )
    except PtzRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(max(1, round(exc.retry_after)))},
        ) from exc
    except TuyaError as exc:
        raise _tuya_http_error(exc) from exc


@router.get(
    "/snapshot",
    summary="Imagen actual o última imagen de alarma",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}, 503: {"description": "Sin mecanismo de captura disponible"}},
)
def camera_snapshot(service: CameraService = Depends(camera_service), db: Session = Depends(get_db)) -> Response:
    try:
        snap = service.snapshot(db)
    except SnapshotUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Snapshot no disponible: {exc}"
        ) from exc
    headers = {"Cache-Control": "no-store", "X-Snapshot-Source": snap.source}
    if snap.captured_at:
        headers["X-Captured-At"] = snap.captured_at.isoformat()
    return Response(content=snap.content, media_type=snap.media_type, headers=headers)


@router.get("/stream", response_model=StreamResponse, summary="URL temporal de vídeo en vivo")
def camera_stream(
    type: str = Query("hls", pattern="^(hls|rtsp|flv|rtmp)$"),
    service: CameraService = Depends(camera_service),
) -> StreamResponse:
    try:
        return StreamResponse(type=type, url=service.live_stream_url(type))
    except TuyaError as exc:
        raise _tuya_http_error(exc) from exc
