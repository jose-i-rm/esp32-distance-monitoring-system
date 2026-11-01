# Credenciales y configuración pendientes

Checklist de cuentas, secretos y variables que **deben completarse manualmente**. Ningún secreto se versiona en el repositorio.

## 1. Render (backend + PostgreSQL)

| # | Tarea | Dónde | Estado |
|---|-------|-------|--------|
| 1 | Crear cuenta en Render e iniciar sesión con GitHub | https://dashboard.render.com | ☐ |
| 2 | Autorizar a Render el acceso al repositorio | Render → *Account settings* → GitHub | ☐ |
| 3 | Crear el Blueprint desde `render.yaml` | Render → *New* → *Blueprint* | ☐ |
| 4 | Copiar el valor generado de `DEVICE_API_KEY` | Servicio `esp32-distance-api` → *Environment* | ☐ |
| 5 | Verificar `CORS_ORIGINS` = `https://jose-i-rm.github.io` | Servicio → *Environment* | ☐ |
| 6 | Anotar la URL pública (`https://esp32-distance-api.onrender.com` o similar) | Servicio → encabezado | ☐ |
| 7 | Programar un respaldo antes de que expire la BD gratuita (30 días) | Ver [base-de-datos.md](./base-de-datos.md#respaldo) | ☐ |

### Variables del servicio web

| Variable | Valor | Origen |
|----------|-------|--------|
| `DATABASE_URL` | Cadena de conexión interna | Automático (`fromDatabase`) |
| `DEVICE_API_KEY` | Cadena aleatoria | Automático (`generateValue`) |
| `CORS_ORIGINS` | `https://jose-i-rm.github.io` | `render.yaml` |
| `ENVIRONMENT` | `production` | `render.yaml` |
| `PYTHON_VERSION` | `3.12.8` | `render.yaml` |

## 2. GitHub (frontend)

| # | Tarea | Dónde | Estado |
|---|-------|-------|--------|
| 1 | Activar GitHub Pages con origen **GitHub Actions** | *Settings* → *Pages* → *Source* | ☑ Hecho |
| 2 | Crear la variable `API_BASE_URL` con la URL de Render | *Settings* → *Secrets and variables* → *Actions* → *Variables* | ☐ |
| 3 | Re-ejecutar el workflow **Deploy Frontend to GitHub Pages** | *Actions* | ☐ |

## 3. Firmware (ESP32-CAM)

| Parámetro | Valor |
|-----------|-------|
| URL de la API | `https://<servicio>.onrender.com/api/v1/measurements` |
| Cabecera `X-API-Key` | Valor de `DEVICE_API_KEY` de Render |
| Credenciales WiFi | Red 2.4 GHz doméstica |

Mantenga estos valores en un archivo `config.h`/`secrets.h` excluido de Git.

## 4. Alternativas (opcional)

| Proveedor | Credencial / configuración pendiente |
|-----------|--------------------------------------|
| Railway | Cuenta, proyecto con plugin PostgreSQL, variables `DEVICE_API_KEY` y `CORS_ORIGINS`. |
| Fly.io | `flyctl auth login`, `fly postgres create`, `fly secrets set DEVICE_API_KEY=...`. |
| Neon / Supabase | Cadena de conexión PostgreSQL para usar como `DATABASE_URL` permanente. |

## 5. Futuras integraciones

| Servicio | Credencial |
|----------|-----------|
| Hugging Face | `HF_API_TOKEN` (*Settings* → *Access Tokens*, rol *read*). |
| Broker MQTT | Host, puerto 8883, usuario y contraseña por dispositivo. |
| Almacenamiento de imágenes | Bucket y claves de acceso (R2 / S3 / Supabase). |

## Generar una API Key manualmente

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
