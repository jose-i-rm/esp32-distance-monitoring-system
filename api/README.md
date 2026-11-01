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
| `GET` | Pública |

## Endpoints

| Método | Ruta | Descripción | Respuestas |
|--------|------|-------------|-----------|
| `POST` | `/api/v1/measurements` | Registra una medición | 201, 401, 422 |
| `GET` | `/api/v1/measurements` | Lista paginada (más recientes primero) | 200, 422 |
| `GET` | `/api/v1/measurements/latest` | Última medición | 200, 404 |
| `GET` | `/health` | Estado del servicio y de la base de datos | 200, 503 |

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
