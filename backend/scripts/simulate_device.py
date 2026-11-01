"""Simulador de la ESP32-CAM: envía mediciones al backend como lo haría el dispositivo.

Uso:
    python scripts/simulate_device.py --url http://localhost:8000 --api-key <KEY> --interval 30
    python scripts/simulate_device.py --count 20 --interval 0     # carga rápida de datos de prueba

Solo usa la librería estándar de Python.
"""

import argparse
import json
import math
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def build_reading(step: int) -> dict:
    # Onda lenta + ruido para simular un objeto que se acerca y aleja.
    distance = 120 + 90 * math.sin(step / 6) + random.uniform(-3, 3)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "distance_cm": round(max(2.0, min(400.0, distance)), 2),
    }


def send(url: str, api_key: str, payload: dict) -> tuple[int, str]:
    request = urllib.request.Request(
        url.rstrip("/") + "/api/v1/measurements",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador de ESP32-CAM + HC-SR04")
    parser.add_argument("--url", default="http://localhost:8000", help="URL base del backend")
    parser.add_argument("--api-key", default="", help="Valor de DEVICE_API_KEY")
    parser.add_argument("--interval", type=float, default=30, help="Segundos entre lecturas")
    parser.add_argument("--count", type=int, default=0, help="Número de lecturas (0 = infinito)")
    args = parser.parse_args()

    step = 0
    try:
        while args.count == 0 or step < args.count:
            reading = build_reading(step)
            status, body = send(args.url, args.api_key, reading)
            local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{local} | Distancia: {reading['distance_cm']:.2f} cm -> HTTP {status}")
            if status not in (200, 201):
                print(f"  Respuesta: {body}", file=sys.stderr)
            step += 1
            if args.interval > 0 and (args.count == 0 or step < args.count):
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulación detenida.")
    except urllib.error.URLError as error:
        print(f"No fue posible conectar con {args.url}: {error.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
