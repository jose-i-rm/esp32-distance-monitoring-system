# Despliegue en Fly.io (alternativa)

Requisitos: [flyctl](https://fly.io/docs/flyctl/install/) y una cuenta en Fly.io.

```bash
fly auth login

# 1. Copiar la configuración al directorio del backend (contexto de build)
cp deployment/fly/fly.toml backend/fly.toml      # PowerShell: Copy-Item deployment\fly\fly.toml backend\
cd backend

# 2. Crear la app sin desplegar
fly launch --no-deploy --copy-config

# 3. Base de datos: Fly Managed Postgres o una externa (Neon/Supabase)
fly secrets set \
  DATABASE_URL="postgresql://usuario:password@host/esp32_monitoring?sslmode=require" \
  DEVICE_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

# 4. Desplegar (construye backend/Dockerfile)
fly deploy

# 5. Verificar
fly status
curl https://esp32-distance-api.fly.dev/health
```

- `primary_region = "bog"` (Bogotá) minimiza la latencia desde Colombia.
- El `Dockerfile` ejecuta `alembic upgrade head` antes de iniciar Uvicorn.
- Con `auto_stop_machines` la máquina se detiene sin tráfico y arranca con la siguiente petición.
- Si el nombre `esp32-distance-api` ya existe, cambie `app` en [`fly.toml`](./fly.toml).
