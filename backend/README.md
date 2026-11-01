# Backend — FastAPI

API REST que recibe, valida y almacena las mediciones de la ESP32-CAM.

## Ejecución rápida

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs

## Variables de entorno

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://esp32:esp32@localhost:5432/esp32_monitoring` | Acepta `postgres://`, `postgresql://` o `sqlite:///`. |
| `DEVICE_API_KEY` | *(vacío)* | Clave exigida en `X-API-Key` para `POST`. Vacío = sin autenticación. |
| `CORS_ORIGINS` | `*` | Orígenes permitidos separados por coma. |
| `ENVIRONMENT` | `development` | Etiqueta informativa expuesta en `/health`. |
| `AUTO_CREATE_TABLES` | `false` | Crea tablas al iniciar (solo desarrollo con SQLite). |

## Scripts

| Comando | Descripción |
|---------|-------------|
| `pytest -q` | Pruebas (SQLite en memoria). |
| `python scripts/simulate_device.py --api-key KEY` | Simula la ESP32 enviando lecturas cada 30 s. |
| `python scripts/export_openapi.py` | Regenera `../api/openapi.json`. |
| `alembic revision --autogenerate -m "..."` | Nueva migración. |

Documentación: [../docs/arquitectura.md](../docs/arquitectura.md) · [../api/README.md](../api/README.md).
