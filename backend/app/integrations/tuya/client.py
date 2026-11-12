"""Cliente reutilizable para Tuya Cloud OpenAPI (proyectos *Custom Development*).

Implementa la firma HMAC-SHA256 vigente de Tuya ("new signature", 2021+), la obtención
y renovación automática del token y wrappers para las APIs usadas por la cámara PTZ.

Se usa `httpx` en lugar de `tuya-iot-python-sdk` porque el SDK oficial está inactivo
(última versión 0.6.6 de 2021), arrastra `paho-mqtt`/`requests` y registra peticiones
completas en modo DEBUG. La firma es idéntica a la de ``TuyaOpenAPI`` del SDK, por lo que
ambos son intercambiables.

Seguridad:
    * El Access Secret nunca se registra ni se incluye en excepciones.
    * El ``access_token`` se mantiene solo en memoria.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

EMPTY_BODY_SHA256 = hashlib.sha256(b"").hexdigest()

# Códigos de error de Tuya que indican token inválido/expirado.
TOKEN_ERROR_CODES = {1010, 1011, 1012}

# 1106: permission deny · 1114: servicio no habilitado
# 28841101/28841106: API no suscrita · 28841105: servicio suscrito pero no autorizado al proyecto
PERMISSION_ERROR_CODES = {1106, 1114, 28841002, 28841101, 28841105, 28841106}


class TuyaError(Exception):
    """Error devuelto por Tuya Cloud (``success=false``) o de transporte."""

    def __init__(self, message: str, code: int | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path

    def __str__(self) -> str:
        prefix = f"[{self.code}] " if self.code is not None else ""
        suffix = f" ({self.path})" if self.path else ""
        return f"{prefix}{self.args[0]}{suffix}"


class TuyaPermissionError(TuyaError):
    """La API no está autorizada para el proyecto (servicio no suscrito o expirado)."""


@dataclass
class _Token:
    access_token: str
    refresh_token: str
    expires_at: float  # epoch (s)
    uid: str | None = None


def _sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest() if body else EMPTY_BODY_SHA256


def build_string_to_sign(method: str, path: str, query: dict[str, Any] | None, body: bytes) -> str:
    """``METHOD\\nContent-SHA256\\nHeaders\\nURL`` con la query ordenada alfabéticamente."""
    url = path
    params = {k: v for k, v in (query or {}).items() if v is not None}
    if params:
        url += "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    return "\n".join([method.upper(), _sha256_hex(body), "", url])


def sign_request(
    *,
    access_id: str,
    access_secret: str,
    timestamp_ms: str,
    nonce: str,
    string_to_sign: str,
    access_token: str = "",
) -> str:
    message = access_id + access_token + timestamp_ms + nonce + string_to_sign
    return hmac.new(access_secret.encode(), message.encode(), hashlib.sha256).hexdigest().upper()


class TuyaClient:
    """Cliente síncrono, thread-safe, con caché de token.

    Ejemplo::

        client = TuyaClient(access_id, access_secret, endpoint)
        client.get_device_status(device_id)
    """

    def __init__(
        self,
        access_id: str,
        access_secret: str,
        endpoint: str = "https://openapi.tuyaus.com",
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not access_id or not access_secret:
            raise ValueError("TUYA_ACCESS_ID y TUYA_ACCESS_SECRET son obligatorios.")
        if not endpoint.startswith("https://"):
            raise ValueError("TUYA_ENDPOINT debe usar HTTPS.")
        self._access_id = access_id
        self._access_secret = access_secret
        self.endpoint = endpoint.rstrip("/")
        self._http = httpx.Client(base_url=self.endpoint, timeout=timeout, transport=transport)
        self._token: _Token | None = None
        self._lock = threading.Lock()

    def __repr__(self) -> str:  # nunca exponer el secreto
        return f"<TuyaClient endpoint={self.endpoint} access_id={self._access_id[:4]}***>"

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------ token
    def _ensure_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token.expires_at - 60:
                return self._token.access_token
            if self._token:
                try:
                    self._token = self._fetch_token(f"/v1.0/token/{self._token.refresh_token}")
                    return self._token.access_token
                except TuyaError:
                    logger.info("Refresh token de Tuya inválido; solicitando uno nuevo.")
            self._token = self._fetch_token("/v1.0/token", {"grant_type": 1})
            return self._token.access_token

    def _fetch_token(self, path: str, query: dict[str, Any] | None = None) -> _Token:
        result = self._send("GET", path, query=query, token="")
        return _Token(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_at=time.time() + int(result.get("expire_time", 7200)),
            uid=result.get("uid"),
        )

    def invalidate_token(self) -> None:
        with self._lock:
            self._token = None

    # --------------------------------------------------------------- requests
    def _send(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> Any:
        raw_body = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
        if token is None:
            token = self._ensure_token()
        t = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        sign = sign_request(
            access_id=self._access_id,
            access_secret=self._access_secret,
            timestamp_ms=t,
            nonce=nonce,
            string_to_sign=build_string_to_sign(method, path, query, raw_body),
            access_token=token,
        )
        headers = {
            "client_id": self._access_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "t": t,
            "nonce": nonce,
            "Content-Type": "application/json",
        }
        if token:
            headers["access_token"] = token

        params = {k: v for k, v in (query or {}).items() if v is not None}
        url = path + ("?" + urlencode(sorted(params.items())) if params else "")
        try:
            response = self._http.request(method, url, content=raw_body or None, headers=headers)
        except httpx.HTTPError as exc:
            raise TuyaError(f"Error de red con Tuya Cloud: {exc.__class__.__name__}", path=path) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TuyaError(f"Respuesta no JSON (HTTP {response.status_code})", path=path) from exc

        if not payload.get("success", False):
            code = payload.get("code")
            msg = payload.get("msg", "error desconocido")
            error_cls = TuyaPermissionError if code in PERMISSION_ERROR_CODES else TuyaError
            raise error_cls(msg, code=code, path=path)
        return payload.get("result")

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """Petición firmada; reintenta una vez si el token expiró."""
        try:
            return self._send(method, path, query=query, body=body)
        except TuyaError as exc:
            if exc.code in TOKEN_ERROR_CODES:
                self.invalidate_token()
                return self._send(method, path, query=query, body=body)
            raise

    @property
    def uid(self) -> str | None:
        self._ensure_token()
        return self._token.uid if self._token else None

    # ----------------------------------------------------------- dispositivo
    def get_device(self, device_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1.0/devices/{device_id}")

    def get_device_status(self, device_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/v1.0/devices/{device_id}/status")

    def get_specifications(self, device_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1.0/devices/{device_id}/specifications")

    def get_functions(self, device_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1.0/devices/{device_id}/functions")

    # -------------------------------------------------------------- eventos
    def get_device_logs(
        self,
        device_id: str,
        *,
        start_time_ms: int,
        end_time_ms: int,
        types: str = "7",
        size: int = 100,
        start_row_key: str | None = None,
    ) -> dict[str, Any]:
        """Historial de eventos (``type=7`` = reporte de DPs: alarmas, detección, etc.)."""
        return self.request(
            "GET",
            f"/v1.0/devices/{device_id}/logs",
            query={
                "type": types,
                "start_time": start_time_ms,
                "end_time": end_time_ms,
                "size": size,
                "start_row_key": start_row_key,
            },
        )

    def get_report_logs(
        self,
        device_id: str,
        *,
        codes: list[str],
        start_time_ms: int,
        end_time_ms: int,
        size: int = 100,
        last_row_key: str | None = None,
    ) -> dict[str, Any]:
        """Historial de reportes por código de DP (API v2 *thing model*)."""
        return self.request(
            "GET",
            f"/v2.0/cloud/thing/{device_id}/report-logs",
            query={
                "codes": ",".join(codes),
                "start_time": start_time_ms,
                "end_time": end_time_ms,
                "size": size,
                "last_row_key": last_row_key,
            },
        )

    # ------------------------------------------------------------- comandos
    def send_commands(self, device_id: str, commands: list[dict[str, Any]]) -> bool:
        return bool(self.request("POST", f"/v1.0/devices/{device_id}/commands", body={"commands": commands}))

    # ---------------------------------------------------------------- vídeo
    def allocate_stream(self, device_id: str, stream_type: str = "hls") -> str:
        """URL temporal de vídeo en vivo (servicio *IoT Video Live Stream*)."""
        result = self.request(
            "POST",
            f"/v1.0/devices/{device_id}/stream/actions/allocate",
            body={"type": stream_type},
        )
        return result["url"]

    def get_webrtc_config(self, device_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1.0/devices/{device_id}/webrtc-configs")

    def trigger_capture(self, device_id: str) -> dict[str, Any]:
        """Captura bajo demanda (asíncrona: la imagen llega por el Message Service)."""
        return self.request("POST", f"/v1.0/cameras/{device_id}/actions/capture", body={})
