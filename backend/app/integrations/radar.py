"""Seguimiento radar -> cámara PTZ.

La ESP32-S3 registra cada acercamiento con su ángulo en Firebase (/stats/last_alert). Este módulo lo
consulta periódicamente (lectura pública) y, ante un acercamiento nuevo, lleva la cámara Tuya al preset
más cercano a ese ángulo, espera a que se estabilice y guarda una foto del vídeo en vivo.

La cámara no admite posiciones absolutas: solo direcciones (ptz_control) y presets (ipc_preset_action),
que se guardan en la app Tuya Smart. ``PTZ_PRESET_ANGLES`` indica a qué ángulo del servo apunta cada uno.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.integrations.tuya.camera import CameraService, PtzRateLimited, SnapshotUnavailable
from app.integrations.tuya.client import TuyaError
from app.models import RadarCapture

logger = logging.getLogger(__name__)


def parse_preset_angles(spec: str) -> dict[int, int]:
    """``"1:0, 2:90, 3:180"`` -> ``{1: 0, 2: 90, 3: 180}``. Ignora entradas mal formadas."""
    presets: dict[int, int] = {}
    for item in spec.split(","):
        preset, _, angle = item.strip().partition(":")
        try:
            preset_n, angle_n = int(preset), int(angle)
        except ValueError:
            continue
        if 1 <= preset_n <= 6 and 0 <= angle_n <= 180:
            presets[preset_n] = angle_n
    return presets


def nearest_preset(angle: float, presets: dict[int, int]) -> int | None:
    if not presets:
        return None
    return min(presets, key=lambda p: (abs(presets[p] - angle), p))


class RadarWatcher:
    def __init__(
        self,
        camera: CameraService,
        db_url: str,
        presets: dict[int, int],
        *,
        settle_seconds: float = 4.0,
        cooldown_seconds: float = 30.0,
        max_captures: int = 50,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.camera = camera
        self.db_url = db_url.rstrip("/")
        self.presets = presets
        self.settle_seconds = settle_seconds
        self.cooldown_seconds = cooldown_seconds
        self.max_captures = max_captures
        self.http = http or httpx.Client(timeout=10)
        self.sleep = sleep
        self.clock = clock
        self.last_epoch: int | None = None
        self.last_capture_at: float | None = None

    def fetch_last_alert(self) -> dict[str, Any] | None:
        response = self.http.get(f"{self.db_url}/stats/last_alert.json")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None

    def check_once(self, db: Session) -> RadarCapture | None:
        """Procesa la última alerta si es nueva. La alerta existente al arrancar solo marca el punto de partida."""
        alert = self.fetch_last_alert()
        if not alert:
            if self.last_epoch is None:
                self.last_epoch = 0
            return None
        epoch = int(alert.get("epoch") or 0)
        if self.last_epoch is None:
            self.last_epoch = epoch
            return None
        if epoch <= self.last_epoch:
            return None
        self.last_epoch = epoch

        angle = alert.get("angle_deg")
        if alert.get("type") != "acercamiento" or angle is None:
            return None
        now = self.clock()
        if self.last_capture_at is not None and now - self.last_capture_at < self.cooldown_seconds:
            logger.info("Acercamiento a %s° ignorado: pausa entre capturas", angle)
            return None
        if db.scalar(select(RadarCapture.id).where(RadarCapture.alert_epoch == epoch)) is not None:
            return None
        self.last_capture_at = now
        return self.capture(db, alert)

    def capture(self, db: Session, alert: dict[str, Any]) -> RadarCapture:
        angle = int(alert["angle_deg"])
        preset = nearest_preset(angle, self.presets)
        record = RadarCapture(
            alert_epoch=int(alert["epoch"]),
            angle_deg=angle,
            distance_cm=float(alert.get("distance_cm") or 0),
            previous_cm=alert.get("previous_cm"),
            preset=preset,
            status="ok",
        )
        problems: list[str] = []
        if preset is None:
            problems.append("sin presets configurados (PTZ_PRESET_ANGLES): foto en la posición actual")
        else:
            try:
                self._goto_preset(preset)
                self.sleep(self.settle_seconds)
            except TuyaError as exc:
                problems.append(f"PTZ: {exc}")
        try:
            record.image = self.camera.live_frame()
        except (SnapshotUnavailable, TuyaError) as exc:
            record.status = "error"
            problems.append(f"foto: {exc}")
        record.detail = "; ".join(problems)[:255] or None
        db.add(record)
        db.commit()
        self._prune(db)
        logger.info("Captura radar: %s° -> preset %s (%s)", angle, preset, record.status)
        return record

    def _goto_preset(self, preset: int) -> None:
        try:
            self.camera.ptz(preset=preset)
        except PtzRateLimited as exc:
            self.sleep(exc.retry_after)
            self.camera.ptz(preset=preset)

    def _prune(self, db: Session) -> None:
        keep = select(RadarCapture.id).order_by(RadarCapture.captured_at.desc(), RadarCapture.id.desc())
        ids = db.scalars(keep.limit(self.max_captures)).all()
        if ids:
            db.execute(delete(RadarCapture).where(RadarCapture.id.not_in(ids)))
            db.commit()
