import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.integrations.radar import RadarWatcher, parse_preset_angles
from app.integrations.tuya import TuyaError, get_camera_service
from app.routers import camera, health, measurements

settings = get_settings()
logger = logging.getLogger(__name__)


def _sync_camera_events_once() -> None:
    service = get_camera_service()
    if service is None:
        return
    with SessionLocal() as db:
        result = service.sync_events(db)
    if result["inserted"]:
        logger.info("Eventos de cámara sincronizados: %s", result)


async def _camera_poller(interval: int) -> None:
    while True:
        try:
            await asyncio.to_thread(_sync_camera_events_once)
        except TuyaError as exc:
            logger.warning("Sincronización Tuya fallida: %s", exc)
        except Exception:  # noqa: BLE001 - el sondeo no debe detener la API
            logger.exception("Error inesperado sincronizando eventos de cámara")
        await asyncio.sleep(interval)


def _radar_check_once(watcher: RadarWatcher) -> None:
    with SessionLocal() as db:
        watcher.check_once(db)


async def _radar_poller(watcher: RadarWatcher, interval: float) -> None:
    while True:
        try:
            await asyncio.to_thread(_radar_check_once, watcher)
        except Exception:  # noqa: BLE001 - el seguimiento no debe detener la API
            logger.exception("Error en el seguimiento radar -> cámara")
        await asyncio.sleep(interval)


def _build_radar_watcher() -> RadarWatcher | None:
    service = get_camera_service()
    if service is None or not settings.firebase_db_url or settings.radar_watch_interval_seconds <= 0:
        return None
    return RadarWatcher(
        service,
        settings.firebase_db_url,
        parse_preset_angles(settings.ptz_preset_angles),
        settle_seconds=settings.ptz_settle_seconds,
        cooldown_seconds=settings.radar_capture_cooldown_seconds,
        max_captures=settings.radar_max_captures,
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    tasks = []
    if settings.tuya_poll_interval_seconds > 0 and settings.tuya_configured:
        tasks.append(asyncio.create_task(_camera_poller(max(30, settings.tuya_poll_interval_seconds))))
    watcher = _build_radar_watcher()
    if watcher is not None:
        tasks.append(asyncio.create_task(_radar_poller(watcher, max(1.0, settings.radar_watch_interval_seconds))))
    yield
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API REST de la plataforma de vigilancia híbrida: mediciones del radar ESP32 + HC-SR04 "
        "y eventos/control de la cámara PTZ Tuya."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
    expose_headers=["X-Snapshot-Source", "X-Captured-At", "Retry-After"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/camera"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.include_router(health.router)
app.include_router(measurements.router)
app.include_router(camera.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
