# API REST

Base URL:

| Entorno | URL |
|---------|-----|
| Local | `http://localhost:8000` |
| Producción (Render) | `https://<servicio>.onrender.com` |

Documentación interactiva generada por FastAPI: **`/docs`** (Swagger UI) y **`/redoc`**. La especificación completa está en [openapi.json](./openapi.json) (regenerable con `python scripts/export_openapi.py` desde `backend/`).

## Autenticación

| Endpoint | Autenticación |
|----------|---------------|
| `POST /api/v1/measurements` | Cabecera `X-API-Key: <DEVICE_API_KEY>` (si está configurada en el servidor) |
| `GET /api/v1/*`, `/health` | Pública |
| `/api/camera/*` | Cabecera `X-API-Key: <ADMIN_API_KEY>` **obligatoria** (sin `ADMIN_API_KEY` en el servidor → 503) |

## Endpoints

| Método | Ruta | Descripción | Respuestas |
|--------|------|-------------|-----------|
| `POST` | `/api/v1/measurements` | Registra una medición | 201, 401, 422 |
| `GET` | `/api/v1/measurements` | Lista paginada (más recientes primero) | 200, 422 |
| `GET` | `/api/v1/measurements/latest` | Última medición | 200, 404 |
| `GET` | `/health` | Estado del servicio y de la base de datos | 200, 503 |
| `GET` | `/api/camera/status` | Estado en vivo de la cámara PTZ Tuya | 200, 401, 502, 503 |
| `GET` | `/api/camera/events` | Eventos de cámara guardados | 200, 401 |
| `POST` | `/api/camera/events/sync` | Sincroniza eventos desde Tuya Cloud | 200, 401, 502, 503 |
| `GET` | `/api/camera/latest` | Último evento de cámara | 200, 401, 404 |
| `POST` | `/api/camera/ptz` | Control PTZ / preset | 200, 401, 422, 429, 502 |
| `GET` | `/api/camera/snapshot` | Imagen JPEG | 200, 401, 503 |
| `GET` | `/api/camera/stream` | URL temporal de vídeo | 200, 401, 503 |

Detalle y ejemplos de los endpoints de cámara: [docs/tuya-camara.md](../docs/tuya-camara.md).

---

### `POST /api/v1/measurements`

**Request**

```http
POST /api/v1/measurements HTTP/1.1
Content-Type: application/json
X-API-Key: <DEVICE_API_KEY>

{
  "timestamp": "2026-11-01T11:08:55-05:00",
  "distance_cm": 214.05
}
```

| Campo | Tipo | Obligatorio | Validación |
|-------|------|-------------|-----------|
| `timestamp` | string (ISO 8601) | Sí | Se normaliza a UTC. Sin zona horaria → UTC. |
| `distance_cm` | number | Sí | `0 ≤ distance_cm ≤ 1000`; se redondea a 2 decimales. |

**Response `201 Created`**

```json
{
  "id": 1,
  "timestamp": "2026-11-01T16:08:55Z",
  "distance_cm": 214.05,
  "created_at": "2026-11-01T16:08:56.120431Z"
}
```

**Response `401 Unauthorized`**

```json
{ "detail": "API Key inválida o ausente." }
```

---

### `GET /api/v1/measurements`

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `limit` | int (1–1000) | 100 | Máximo de registros. |
| `offset` | int (≥ 0) | 0 | Desplazamiento. |
| `start` | datetime ISO 8601 | — | Desde (inclusive). |
| `end` | datetime ISO 8601 | — | Hasta (inclusive). |

**Response `200 OK`**

```json
{
  "items": [
    { "id": 2, "timestamp": "2026-11-01T16:09:25Z", "distance_cm": 4.92, "created_at": "2026-11-01T16:09:26Z" },
    { "id": 1, "timestamp": "2026-11-01T16:08:55Z", "distance_cm": 214.05, "created_at": "2026-11-01T16:08:56Z" }
  ],
  "total": 2,
  "limit": 100,
  "offset": 0
}
```

---

### `GET /api/v1/measurements/latest`

**Response `200 OK`** — objeto `Measurement`.
**Response `404 Not Found`** — `{"detail": "Aún no hay mediciones registradas."}`

---

### `GET /health`

**Response `200 OK`**

```json
{
  "status": "ok",
  "app": "ESP32 Distance Monitoring System",
  "version": "1.0.0",
  "environment": "production",
  "database": "ok",
  "timestamp": "2026-11-01T16:10:00Z"
}
```

Si la base de datos no responde: **`503`** con `"status": "degraded"` y `"database": "unavailable"`.

## Ejemplos

- [examples/curl.md](./examples/curl.md) — `curl` (Bash y PowerShell).
- [examples/requests.http](./examples/requests.http) — Extensión REST Client de VS Code.
- [../backend/scripts/simulate_device.py](../backend/scripts/simulate_device.py) — Simulador del dispositivo.

## Versionado

Las rutas usan el prefijo `/api/v1`. Cambios incompatibles se publicarán bajo `/api/v2` manteniendo `v1` durante la transición.
