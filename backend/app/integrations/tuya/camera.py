"""Servicio de dominio para la cámara PTZ Tuya.

Traduce las respuestas de Tuya Cloud a eventos normalizados, los persiste sin duplicados
y encapsula PTZ, vídeo en vivo y snapshot.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.tuya.client import TuyaClient, TuyaError
from app.models import CameraEvent

logger = logging.getLogger(__name__)

# DP ptz_control (enum "0".."7"), sentido horario empezando arriba.
PTZ_DIRECTIONS: dict[str, str] = {
    "up": "0",
    "up_right": "1",
    "right": "2",
    "down_right": "3",
    "down": "4",
    "down_left": "5",
    "left": "6",
    "up_left": "7",
}

# Campo "cmd" de alarm_message / movement_detect_pic -> tipo normalizado.
ALARM_CMD_TYPES: dict[str, str] = {
    "ipc_human": "humanoid_detection",
    "ipc_bang": "abnormal_sound",
    "ipc_motion": "motion_detection",
    "ipc_move": "motion_detection",
    "ipc_face": "face_detection",
    "ipc_baby_cry": "baby_cry",
    "ipc_doorbell": "doorbell",
    "ipc_car": "vehicle_detection",
    "ipc_cat": "pet_detection",
    "ipc_dog": "pet_detection",
}

ALARM_CODES = {"alarm_message", "movement_detect_pic", "initiative_message"}

# event_id de /v1.0/devices/{id}/logs
LOG_EVENT_TYPES: dict[int, str] = {
    1: "online",
    2: "offline",
    3: "activated",
    4: "reset",
    5: "command",
    6: "firmware_update",
    9: "restart",
}

# Rango máximo que se consulta a Tuya en una sincronización (los logs se conservan ~7 días).
MAX_LOOKBACK = timedelta(days=7)
DEFAULT_LOOKBACK = timedelta(hours=24)
MAX_PAGES = 20


class SnapshotUnavailable(Exception):
    """No hay ningún mecanismo de captura disponible con la suscripción actual."""


@dataclass
class Snapshot:
    content: bytes
    media_type: str
    source: str
    captured_at: datetime | None


def _ms_to_dt(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def decode_alarm_payload(value: str) -> dict[str, Any] | None:
    """Decodifica el base64 JSON de ``alarm_message``/``movement_detect_pic`` (si aplica)."""
    if not value or len(value) < 8:
        return None
    try:
        payload = json.loads(base64.b64decode(value, validate=False))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_log_entry(device_id: str, log: dict[str, Any]) -> dict[str, Any] | None:
    """Convierte una entrada de ``/v1.0/devices/{id}/logs`` en columnas de ``CameraEvent``."""
    event_id = int(log.get("event_id", 0))
    event_time = _ms_to_dt(log["event_time"])
    base: dict[str, Any] = {
        "device_id": device_id,
        "event_time": event_time,
        "source": "tuya_logs",
        "tuya_cmd": None,
        "value": None,
        "image_bucket": None,
        "image_path": None,
        "image_key": None,
        "image_expires_at": None,
    }

    if event_id != 7:
        event_type = LOG_EVENT_TYPES.get(event_id)
        if event_type is None:
            return None
        return {**base, "event_type": event_type, "code": event_type, "raw": {"event_id": event_id}}

    code = str(log.get("code", "unknown"))
    value = str(log.get("value", ""))
    raw: dict[str, Any] = {"event_id": event_id, "code": code, "event_from": log.get("event_from")}

    if code in ALARM_CODES:
        payload = decode_alarm_payload(value)
        if payload is not None:
            cmd = payload.get("cmd")
            event_type = ALARM_CMD_TYPES.get(str(cmd), "alarm")
            files = payload.get("files") or []
            image: dict[str, Any] = {}
            # Formato v5.0 en logs: [[bucket, ruta, clave_aes, expiración_epoch_s], ...]
            if files and isinstance(files[0], list) and len(files[0]) >= 3:
                bucket, path, key = files[0][:3]
                expires = files[0][3] if len(files[0]) > 3 else None
                image = {
                    "image_bucket": bucket,
                    "image_path": path,
                    "image_key": key,
                    "image_expires_at": (
                        datetime.fromtimestamp(int(expires), tz=timezone.utc) if expires else None
                    ),
                }
            raw["payload"] = {k: v for k, v in payload.items() if k != "files"}
            raw["has_image"] = bool(image)
            return {**base, **image, "event_type": event_type, "code": code, "tuya_cmd": cmd, "raw": raw}
        # Mensajes en texto plano (p. ej. "alarm"/"disalarm" en algunos firmwares).
        lowered = value.lower()
        event_type = "disalarm" if "disalarm" in lowered else "alarm"
        return {**base, "event_type": event_type, "code": code, "value": value[:255], "raw": raw}

    if code in {"alarm", "disalarm"}:
        return {**base, "event_type": code, "code": code, "value": value[:255], "raw": raw}

    return {**base, "event_type": "dp_report", "code": code, "value": value[:255], "raw": raw}


class CameraService:
    def __init__(
        self,
        client: TuyaClient,
        device_id: str,
        *,
        ptz_min_interval_seconds: float = 1.0,
        ptz_max_duration_ms: int = 3000,
    ) -> None:
        self.client = client
        self.device_id = device_id
        self.ptz_min_interval_seconds = ptz_min_interval_seconds
        self.ptz_max_duration_ms = ptz_max_duration_ms
        self._ptz_lock = threading.Lock()
        self._last_ptz = 0.0

    # ----------------------------------------------------------------- estado
    def get_status(self) -> dict[str, Any]:
        device = self.client.get_device(self.device_id)
        status = self.client.get_device_status(self.device_id)
        dps = {item["code"]: item.get("value") for item in status}
        for sensitive in ("alarm_message", "movement_detect_pic", "initiative_message"):
            if sensitive in dps:
                dps[sensitive] = "<omitido>"
        return {
            "device_id": self.device_id,
            "name": device.get("name"),
            "product_name": device.get("product_name"),
            "category": device.get("category"),
            "online": bool(device.get("online")),
            "time_zone": device.get("time_zone"),
            "update_time": _ms_to_dt(device["update_time"] * 1000) if device.get("update_time") else None,
            "status": dps,
        }

    # ---------------------------------------------------------------- eventos
    def fetch_events(self, start: datetime, end: datetime, *, page_size: int = 100) -> list[dict[str, Any]]:
        start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
        events: list[dict[str, Any]] = []
        row_key: str | None = None
        for _ in range(MAX_PAGES):
            result = self.client.get_device_logs(
                self.device_id,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                types="1,2,7",
                size=page_size,
                start_row_key=row_key,
            )
            for log in result.get("logs") or []:
                parsed = parse_log_entry(self.device_id, log)
                if parsed:
                    events.append(parsed)
            row_key = result.get("next_row_key")
            if not result.get("has_next") or not row_key or not result.get("logs"):
                break
        return events

    def sync_events(self, db: Session, *, since: datetime | None = None) -> dict[str, int]:
        """Descarga eventos nuevos desde Tuya y los guarda sin duplicados."""
        now = datetime.now(timezone.utc)
        if since is None:
            last = db.scalar(
                select(CameraEvent.event_time)
                .where(CameraEvent.device_id == self.device_id)
                .order_by(CameraEvent.event_time.desc())
                .limit(1)
            )
            if last is not None:
                last = _as_utc(last)
            since = (last - timedelta(minutes=1)) if last else now - DEFAULT_LOOKBACK
        since = max(since, now - MAX_LOOKBACK)

        fetched = self.fetch_events(since, now)
        if not fetched:
            return {"fetched": 0, "inserted": 0}
        oldest = min(event["event_time"] for event in fetched)
        existing = {
            (_as_utc(row.event_time), row.code, row.event_type)
            for row in db.execute(
                select(CameraEvent.event_time, CameraEvent.code, CameraEvent.event_type).where(
                    CameraEvent.device_id == self.device_id, CameraEvent.event_time >= oldest
                )
            )
        }
        inserted = 0
        for event in fetched:
            key = (event["event_time"], event["code"], event["event_type"])
            if key in existing:
                continue
            existing.add(key)
            db.add(CameraEvent(**event))
            inserted += 1
        db.commit()
        return {"fetched": len(fetched), "inserted": inserted}

    # -------------------------------------------------------------------- PTZ
    def ptz(self, *, direction: str | None = None, preset: int | None = None, duration_ms: int = 500) -> dict[str, Any]:
        with self._ptz_lock:
            wait = self.ptz_min_interval_seconds - (time.monotonic() - self._last_ptz)
            if wait > 0:
                raise PtzRateLimited(wait)
            self._last_ptz = time.monotonic()

            if preset is not None:
                self.client.send_commands(self.device_id, [{"code": "ipc_preset_action", "value": str(preset)}])
                return {"action": "preset", "preset": preset}

            if direction == "stop":
                self.client.send_commands(self.device_id, [{"code": "ptz_stop", "value": True}])
                return {"action": "stop"}

            if direction not in PTZ_DIRECTIONS:
                raise ValueError(f"Dirección PTZ no válida: {direction}")
            duration_ms = max(0, min(duration_ms, self.ptz_max_duration_ms))
            self.client.send_commands(self.device_id, [{"code": "ptz_control", "value": PTZ_DIRECTIONS[direction]}])
            if duration_ms:
                try:
                    time.sleep(duration_ms / 1000)
                finally:
                    # Siempre detener para no dejar la cámara girando.
                    self.client.send_commands(self.device_id, [{"code": "ptz_stop", "value": True}])
            return {"action": "move", "direction": direction, "duration_ms": duration_ms}

    # ------------------------------------------------------------------ vídeo
    def live_stream_url(self, stream_type: str = "hls") -> str:
        return self.client.allocate_stream(self.device_id, stream_type)

    # --------------------------------------------------------------- snapshot
    def alarm_image_url(self, bucket: str, file_path: str) -> str:
        result = self.client.request(
            "GET",
            f"/v1.0/devices/{self.device_id}/movement-configs",
            query={"bucket": bucket, "file_path": file_path},
        )
        return result if isinstance(result, str) else result.get("url") or result.get("file_url")

    def snapshot(self, db: Session) -> Snapshot:
        """Obtiene una imagen de la cámara probando, en orden:

        1. Fotograma del vídeo en vivo (RTSP/HLS) con ffmpeg — requiere *IoT Video Live Stream*.
        2. Última imagen de alarma (detección humanoide/sonido) — requiere la API ``movement-configs``.
        """
        reasons: list[str] = []

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                url = self.live_stream_url("rtsp")
                return Snapshot(_grab_frame(ffmpeg, url), "image/jpeg", "live_stream", datetime.now(timezone.utc))
            except TuyaError as exc:
                reasons.append(f"live_stream: {exc}")
            except (subprocess.SubprocessError, OSError) as exc:
                reasons.append(f"live_stream: ffmpeg falló ({exc.__class__.__name__})")
        else:
            reasons.append("live_stream: ffmpeg no está instalado")

        event = db.scalar(
            select(CameraEvent)
            .where(CameraEvent.device_id == self.device_id, CameraEvent.image_path.is_not(None))
            .order_by(CameraEvent.event_time.desc())
            .limit(1)
        )
        if event is None:
            reasons.append("alarm_image: no hay eventos con imagen sincronizados")
        else:
            try:
                url = self.alarm_image_url(event.image_bucket or "", event.image_path or "")
                encrypted = httpx.get(url, timeout=15).raise_for_status().content
                image = decrypt_alarm_image(encrypted, event.image_key or "")
                return Snapshot(image, "image/jpeg", f"alarm_image:{event.event_type}", event.event_time)
            except TuyaError as exc:
                reasons.append(f"alarm_image: {exc}")
            except (httpx.HTTPError, ValueError) as exc:
                reasons.append(f"alarm_image: {exc.__class__.__name__}")

        raise SnapshotUnavailable("; ".join(reasons))


class PtzRateLimited(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Espere {retry_after:.1f} s antes del siguiente comando PTZ.")
        self.retry_after = retry_after


def decrypt_alarm_image(data: bytes, key: str) -> bytes:
    """Descifra una imagen de alarma Tuya.

    Formato: 4 bytes de versión + 16 bytes de IV + 44 bytes reservados + datos AES-128-CBC
    (clave = cadena de 16 caracteres incluida en el mensaje de alarma). Si los datos ya son
    un JPEG en claro, se devuelven sin cambios.
    """
    if data[:3] == b"\xff\xd8\xff":
        return data
    if len(key) != 16 or len(data) <= 64:
        raise ValueError("Imagen cifrada o clave con formato inesperado")
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    iv, ciphertext = data[4:20], data[64:]
    decryptor = Cipher(algorithms.AES(key.encode()), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    try:
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError:
        return padded


def _grab_frame(ffmpeg: str, url: str, timeout: float = 20.0) -> bytes:
    args = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if url.startswith("rtsp"):
        args += ["-rtsp_transport", "tcp"]
    args += ["-i", url, "-frames:v", "1", "-f", "image2", "-vcodec", "mjpeg", "pipe:1"]
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=True)  # noqa: S603
    if not result.stdout:
        raise subprocess.SubprocessError("ffmpeg no devolvió datos")
    return result.stdout
