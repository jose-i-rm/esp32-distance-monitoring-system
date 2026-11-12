# Integración de la cámara PTZ Tuya

Guía de configuración y uso del módulo `backend/app/integrations/tuya`. El análisis de qué APIs
están disponibles con la cuenta actual está en [informe-apis-tuya.md](./informe-apis-tuya.md).

## 1. Componentes

| Archivo | Responsabilidad |
|---------|-----------------|
| [`client.py`](../backend/app/integrations/tuya/client.py) | `TuyaClient`: firma HMAC-SHA256, token con caché/renovación, errores tipados (`TuyaError`, `TuyaPermissionError`) y *wrappers* de dispositivo, logs, comandos, vídeo y captura. Reutilizable fuera de FastAPI. |
| [`camera.py`](../backend/app/integrations/tuya/camera.py) | `CameraService`: normaliza eventos, sincronización idempotente hacia PostgreSQL, PTZ con parada garantizada y límite de frecuencia, vídeo y snapshot. |
| [`__init__.py`](../backend/app/integrations/tuya/__init__.py) | `get_camera_service()`: instancia única por proceso (comparte el token). |
| [`routers/camera.py`](../backend/app/routers/camera.py) | Endpoints `/api/camera/*`. |
| [`models.py`](../backend/app/models.py) · [`0002_create_camera_events.py`](../backend/alembic/versions/0002_create_camera_events.py) | Tabla `camera_events`. |
| [`scripts/tuya_probe.py`](../backend/scripts/tuya_probe.py) | Diagnóstico de APIs disponibles (sin imprimir secretos). |

Uso del cliente de forma independiente:

```python
from app.integrations.tuya import TuyaClient

client = TuyaClient(access_id, access_secret, "https://openapi.tuyaus.com")
client.get_device_status(device_id)
client.send_commands(device_id, [{"code": "ptz_control", "value": "2"}])
client.send_commands(device_id, [{"code": "ptz_stop", "value": True}])
```

## 2. Configuración

1. En <https://platform.tuya.com> → *Cloud → Development → (proyecto) → Overview* copie el
   **Access ID** y el **Access Secret**. Verifique que el *Data Center* sea el mismo de la App
   (cuenta actual: *Western America* → `https://openapi.tuyaus.com`).
2. En *Devices → Link App Account* vincule la cuenta de Smart Life/Tuya donde está la cámara.
3. Cree `backend/.env` a partir de [`backend/.env.example`](../backend/.env.example) (el archivo
   `.env` está en `.gitignore`):

```dotenv
ADMIN_API_KEY=<python -c "import secrets; print(secrets.token_urlsafe(32))">
TUYA_ACCESS_ID=<access id>
TUYA_ACCESS_SECRET=<access secret>
TUYA_DEVICE_ID=<device id>
TUYA_ENDPOINT=https://openapi.tuyaus.com
TUYA_POLL_INTERVAL_SECONDS=0     # 300 para sincronizar eventos automáticamente
```

4. Migraciones y diagnóstico:

```bash
cd backend
alembic upgrade head
python scripts/tuya_probe.py              # solo lectura
python scripts/tuya_probe.py --ptz        # además prueba un giro corto + stop
uvicorn app.main:app --reload
```

En producción (Render/Railway/Fly) defina las mismas variables en el **gestor de secretos** del
proveedor; [`render.yaml`](../render.yaml) las declara con `sync: false` para que nunca se guarden en el repo.

## 3. Endpoints

Todos exigen `X-API-Key: <ADMIN_API_KEY>`. Si `ADMIN_API_KEY` no está definida responden **503**
(*fail-closed*), y si Tuya no está configurado responden **503** con el motivo.

| Método | Ruta | Descripción | Respuestas |
|--------|------|-------------|------------|
| `GET` | `/api/camera/status` | Estado en vivo (online, DPs). Omite `alarm_message`. | 200, 401, 502, 503 |
| `GET` | `/api/camera/events` | Eventos guardados. Filtros: `event_type`, `start`, `end`, `limit` (≤500), `offset`. | 200, 401 |
| `POST` | `/api/camera/events/sync` | Descarga eventos nuevos de Tuya y los guarda sin duplicados. | 200, 401, 502, 503 |
| `GET` | `/api/camera/latest` | Último evento (opcional `event_type`). | 200, 401, 404 |
| `POST` | `/api/camera/ptz` | `{"direction":"left","duration_ms":500}` · `{"direction":"stop"}` · `{"preset":2}` | 200, 401, 422, 429, 502 |
| `GET` | `/api/camera/snapshot` | `image/jpeg` (cabeceras `X-Snapshot-Source`, `X-Captured-At`). | 200, 401, 503 |
| `GET` | `/api/camera/stream?type=hls` | URL temporal de vídeo (`hls`, `rtsp`, `flv`, `rtmp`). | 200, 401, 503 |

Ejemplos:

```bash
KEY="<ADMIN_API_KEY>"; API=http://localhost:8000
curl -H "X-API-Key: $KEY" $API/api/camera/status
curl -X POST -H "X-API-Key: $KEY" $API/api/camera/events/sync
curl -H "X-API-Key: $KEY" "$API/api/camera/events?event_type=humanoid_detection&limit=10"
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"direction":"right","duration_ms":600}' $API/api/camera/ptz
curl -H "X-API-Key: $KEY" -o snapshot.jpg $API/api/camera/snapshot
```

Ejemplo de evento:

```json
{
  "id": 1,
  "device_id": "<device id>",
  "event_time": "2026-11-11T18:18:50.246000Z",
  "event_type": "humanoid_detection",
  "code": "alarm_message",
  "tuya_cmd": "ipc_human",
  "value": null,
  "has_image": true,
  "image_expires_at": "2026-12-11T18:18:50Z",
  "source": "tuya_logs",
  "created_at": "2026-11-11T18:18:55.493509Z"
}
```

## 4. Esquema `camera_events`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | serial PK | |
| `device_id` | varchar(64) | ID Tuya de la cámara |
| `event_time` | timestamptz | Momento del evento (UTC) — índice |
| `event_type` | varchar(40) | `humanoid_detection`, `abnormal_sound`, `motion_detection`, `alarm`, `disalarm`, `online`, `offline`, `dp_report`… — índice |
| `code` | varchar(64) | DP de origen (`alarm_message`, `ptz_control`…) |
| `tuya_cmd` | varchar(40) | `cmd` original (`ipc_human`, `ipc_bang`…) |
| `value` | varchar(255) | Valor del DP (eventos que no son de alarma) |
| `image_bucket`, `image_path` | varchar | Referencia a la imagen en el almacenamiento de Tuya |
| `image_key` | varchar(64) | Clave AES de la imagen — **sensible, nunca se expone** |
| `image_expires_at` | timestamptz | Caducidad de la imagen en Tuya |
| `source` | varchar(20) | `tuya_logs` (futuro: `tuya_mq`) |
| `raw` | json | Metadatos originales para auditoría (sin `files` ni claves) |
| `created_at` | timestamptz | Inserción |

Restricción única `(device_id, event_time, code, event_type)` → la sincronización es idempotente.

## 5. Dashboard

La sección **Cámara PTZ Tuya** de [`frontend/index.html`](../frontend/index.html)
([`js/camera.js`](../frontend/js/camera.js)) muestra el estado, los últimos eventos (sin los
cambios de parámetros), un pad PTZ de 8 direcciones + stop, **vídeo en vivo**, **Tomar foto** / **Descargar foto** y *Sincronizar*.
Pide la URL del backend y la clave de administración; la clave se guarda solo en
`sessionStorage`. El origen del dashboard debe estar en `CORS_ORIGINS`.

## 6. Próximos pasos

1. ~~Autorizar *IoT Video Live Stream* en el proyecto~~ ✅ Hecho (2026-11-12): `/stream` (HLS/RTSP/FLV/RTMP) y WebRTC responden OK. El dashboard reproduce el HLS con hls.js (Tuya lo sirve con `Access-Control-Allow-Origin: *`, H.264 + AAC) y toma las fotos del propio vídeo. Los primeros segundos Tuya emite una pantalla negra de «conectando»; el panel no guarda fotos de esa pantalla.
2. Reproducir HLS en el dashboard con `hls.js` (URL pedida al backend en cada sesión).
3. Sustituir el sondeo por **Message Service (Pulsar)** (`tuya-connector-python`) para recibir
   eventos en tiempo real sin consumir la cuota de llamadas.
4. Correlacionar eventos de cámara con mediciones del radar (ver [arquitectura híbrida](../diagrams/07-arquitectura-hibrida.md)).
