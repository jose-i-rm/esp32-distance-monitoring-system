# Despliegue en Render

El repositorio incluye un **Blueprint** en [`/render.yaml`](../../render.yaml) que crea:

- `esp32-monitoring-db`: PostgreSQL (plan free).
- `esp32-distance-api`: servicio web Python con FastAPI (plan free).

## Pasos

1. Inicie sesión en https://dashboard.render.com con su cuenta de GitHub.
2. **New → Blueprint** y seleccione el repositorio `esp32-distance-monitoring-system`.
3. Render detecta `render.yaml`; confirme con **Apply**.
4. Espere a que finalice el build. El comando de inicio ejecuta:
   ```bash
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Abra `https://<servicio>.onrender.com/health` → debe responder `"status": "ok"`.
6. En **Environment** copie el valor de `DEVICE_API_KEY` (generado automáticamente) y configúrelo en el firmware.
7. Si usa un dominio de frontend distinto a `https://jose-i-rm.github.io`, actualice `CORS_ORIGINS`.

## Despliegue manual (sin Blueprint)

| Campo | Valor |
|-------|-------|
| Runtime | Python 3 |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Variables | `PYTHON_VERSION=3.12.8`, `DATABASE_URL`, `DEVICE_API_KEY`, `CORS_ORIGINS`, `ENVIRONMENT=production` |

Use la **Internal Database URL** de la base de datos de Render como `DATABASE_URL`.

## Consideraciones del plan gratuito

- **Arranque en frío:** el servicio se suspende tras 15 minutos sin tráfico y tarda ~50 s en responder la primera petición. El firmware debe usar un timeout HTTP ≥ 20 s y reintentar.
- **Expiración de PostgreSQL:** las bases gratuitas expiran a los 30 días.

## Base de datos permanente

Para evitar la expiración, cree una base en [Neon](https://neon.tech) o [Supabase](https://supabase.com) y reemplace `DATABASE_URL` en el servicio web:

```
postgresql://usuario:password@host/esp32_monitoring?sslmode=require
```

Elimine luego la sección `databases` y la referencia `fromDatabase` de `render.yaml` si ya no la necesita.
