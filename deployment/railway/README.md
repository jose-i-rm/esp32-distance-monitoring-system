# Despliegue en Railway (alternativa)

1. Cree un proyecto en https://railway.com → **Deploy from GitHub repo**.
2. En el servicio, configure **Settings → Root Directory** = `backend`.
3. Copie [`railway.json`](./railway.json) a `backend/railway.json` (Railway lee la configuración desde el directorio raíz del servicio) o configure manualmente:
   - Build: `pip install -r requirements.txt`
   - Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Healthcheck: `/health`
4. **New → Database → PostgreSQL**.
5. En las variables del servicio web:

| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referencia) |
| `DEVICE_API_KEY` | Clave generada |
| `CORS_ORIGINS` | `https://jose-i-rm.github.io` |
| `ENVIRONMENT` | `production` |
| `NIXPACKS_PYTHON_VERSION` | `3.12` |

6. **Settings → Networking → Generate Domain** para obtener la URL pública.

> Alternativamente, Railway detecta el `Dockerfile` de `backend/` y el `Procfile`.
