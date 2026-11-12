"""Diagnóstico de capacidades de Tuya Cloud para la cámara PTZ.

Prueba las APIs relevantes y muestra una matriz "API -> disponible / código de error".
No imprime secretos ni tokens; las URLs de vídeo se truncan.

Uso (desde backend/, con .env configurado):
    python scripts/tuya_probe.py            # solo lectura
    python scripts/tuya_probe.py --ptz      # además mueve la cámara 0.5 s a la derecha y la detiene
    python scripts/tuya_probe.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.integrations.tuya.client import TuyaClient, TuyaError  # noqa: E402


def _safe(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Los valores de alarm_message incluyen la clave AES de la imagen: no se vuelcan.
    return [{k: log.get(k) for k in ("code", "event_id", "event_time")} for log in logs[:10]]


def _mask_url(url: str) -> str:
    return url.split("?")[0][:60] + "…" if url else url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ptz", action="store_true", help="Probar un movimiento PTZ real (corto) y detenerlo.")
    parser.add_argument("--json", type=Path, help="Guardar el resultado (sin secretos) en un archivo JSON.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.tuya_configured:
        print("Faltan TUYA_ACCESS_ID / TUYA_ACCESS_SECRET / TUYA_DEVICE_ID en el entorno.")
        return 2

    client = TuyaClient(
        settings.tuya_access_id, settings.tuya_access_secret.get_secret_value(), settings.tuya_endpoint
    )
    device = settings.tuya_device_id
    now_ms = int(time.time() * 1000)
    day_ms = 24 * 3600 * 1000
    results: list[dict[str, Any]] = []

    def probe(name: str, fn: Callable[[], Any], summarize: Callable[[Any], Any] = lambda r: r) -> Any:
        try:
            value = fn()
            results.append({"api": name, "ok": True, "summary": summarize(value)})
            print(f"[OK]   {name}")
            return value
        except TuyaError as exc:
            results.append({"api": name, "ok": False, "code": exc.code, "error": exc.args[0]})
            print(f"[FAIL] {name} -> {exc.code}: {exc.args[0]}")
        except Exception as exc:  # noqa: BLE001
            results.append({"api": name, "ok": False, "error": exc.__class__.__name__})
            print(f"[FAIL] {name} -> {exc.__class__.__name__}")
        return None

    probe("GET /v1.0/token", lambda: client.uid is not None or True, lambda _: "token obtenido")
    probe(
        "GET /v1.0/devices/{id}",
        lambda: client.get_device(device),
        lambda r: {k: r.get(k) for k in ("name", "category", "product_name", "online", "time_zone")},
    )
    probe(
        "GET /v1.0/devices/{id}/status",
        lambda: client.get_device_status(device),
        lambda r: {i["code"]: ("<omitido>" if i["code"] == "alarm_message" else i["value"]) for i in r},
    )
    probe(
        "GET /v1.0/devices/{id}/specifications",
        lambda: client.get_specifications(device),
        lambda r: {
            "functions": [f["code"] for f in r.get("functions", [])],
            "status": [s["code"] for s in r.get("status", [])],
        },
    )
    probe(
        "GET /v1.0/devices/{id}/functions",
        lambda: client.get_functions(device),
        lambda r: {f["code"]: f.get("values") for f in r.get("functions", [])},
    )
    probe(
        "GET /v1.0/devices/{id}/logs (type=7, 7 días)",
        lambda: client.get_device_logs(device, start_time_ms=now_ms - 7 * day_ms, end_time_ms=now_ms, size=50),
        lambda r: {"count": len(r.get("logs", [])), "has_next": r.get("has_next"), "sample": _safe(r.get("logs", []))},
    )
    probe(
        "GET /v1.0/devices/{id}/logs (type=1,2 online/offline, 7 días)",
        lambda: client.get_device_logs(
            device, start_time_ms=now_ms - 7 * day_ms, end_time_ms=now_ms, types="1,2", size=20
        ),
        lambda r: {"count": len(r.get("logs", [])), "sample": _safe(r.get("logs", []))},
    )
    probe(
        "GET /v2.0/cloud/thing/{id}/report-logs",
        lambda: client.get_report_logs(
            device,
            codes=["movement_detect_pic", "alarm_message", "initiative_message", "humanoid_filter"],
            start_time_ms=now_ms - 7 * day_ms,
            end_time_ms=now_ms,
            size=20,
        ),
        lambda r: {"count": len(r.get("logs", [])), "sample": _safe(r.get("logs", []))},
    )
    probe(
        "GET /v2.0/cloud/thing/{id}/model",
        lambda: client.request("GET", f"/v2.0/cloud/thing/{device}/model"),
        lambda r: "ok" if r else r,
    )
    for stream_type in ("hls", "rtsp", "flv", "rtmp"):
        probe(
            f"POST /v1.0/devices/{{id}}/stream/actions/allocate ({stream_type})",
            lambda st=stream_type: client.allocate_stream(device, st),
            _mask_url,
        )
    probe(
        "GET /v1.0/devices/{id}/webrtc-configs",
        lambda: client.get_webrtc_config(device),
        lambda r: sorted(r.keys()) if isinstance(r, dict) else r,
    )
    probe(
        "GET /v2.0/cloud/thing/{id}/shadow/properties",
        lambda: client.request("GET", f"/v2.0/cloud/thing/{device}/shadow/properties"),
        lambda r: len(r.get("properties", [])),
    )
    probe(
        "GET /v1.0/devices/{id}/movement-configs (URL imagen de alarma)",
        lambda: client.request(
            "GET", f"/v1.0/devices/{device}/movement-configs", query={"bucket": "x", "file_path": "/x.jpeg"}
        ),
        lambda _: "autorizado",
    )
    probe(
        "POST /v1.0/cameras/{id}/actions/capture",
        lambda: client.trigger_capture(device),
        lambda r: r,
    )

    if args.ptz:
        probe(
            "POST /v1.0/devices/{id}/commands ptz_control=2 (derecha)",
            lambda: client.send_commands(device, [{"code": "ptz_control", "value": "2"}]),
        )
        time.sleep(0.5)
        probe(
            "POST /v1.0/devices/{id}/commands ptz_stop",
            lambda: client.send_commands(device, [{"code": "ptz_stop", "value": True}]),
        )

    client.close()
    if args.json:
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Resultado guardado en {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
