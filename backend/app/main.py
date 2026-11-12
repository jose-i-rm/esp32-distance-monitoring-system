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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    poller = None
    if settings.tuya_poll_interval_seconds > 0 and settings.tuya_configured:
        poller = asyncio.create_task(_camera_poller(max(30, settings.tuya_poll_interval_seconds)))
    yield
    if poller:
        poller.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller


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
    allow_methods=["GET", "POST", "OPTIONS"],
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
