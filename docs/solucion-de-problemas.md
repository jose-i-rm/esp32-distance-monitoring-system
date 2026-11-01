# Solución de problemas

## Backend

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `connection refused` a PostgreSQL | Servicio detenido o URL incorrecta | Verifique `DATABASE_URL` y que PostgreSQL/Docker esté activo. |
| `ModuleNotFoundError: app` al ejecutar Alembic | Directorio incorrecto | Ejecute `alembic` dentro de `backend/`. |
| `relation "measurements" does not exist` | Migraciones no aplicadas | `alembic upgrade head`. |
| `401 API Key inválida o ausente` | Cabecera faltante o distinta | Enviar `X-API-Key` con el valor exacto de `DEVICE_API_KEY`. |
| `422 Unprocessable Entity` | JSON inválido | Revise que `timestamp` sea ISO 8601 y `distance_cm` numérico entre 0 y 1000. |
| `/health` responde 503 | Base de datos inaccesible | Revise estado de la BD en el proveedor. |

## Dashboard

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| "Sin conexión" | URL errónea o API dormida | Revise la URL en **⚙ Configuración**; en Render gratuito espere ~50 s. |
| Error CORS en la consola | Origen no permitido | Añada el dominio del dashboard a `CORS_ORIGINS` (sin `/` final). |
| "Mixed content" bloqueado | Dashboard HTTPS llamando API HTTP | Use la URL **https** del backend. |
| Dispositivo "Fuera de línea" con datos recientes | Reloj del dispositivo desfasado | Verifique la sincronización NTP y la zona horaria del `timestamp` enviado. |

## Comunicación ESP32 → API

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `HTTP -1` / `connection refused` en red local | Firewall de Windows o `--host 127.0.0.1` | Ejecute uvicorn con `--host 0.0.0.0` y permita el puerto 8000. |
| Timeout en la primera petición a Render | El servicio gratuito estaba suspendido | Aumente el timeout HTTP del firmware a ≥ 20 s y reintente. |
| Horas desplazadas 5 h en el dashboard | `timestamp` sin zona horaria interpretado como UTC | Enviar `-05:00` o la hora en UTC con sufijo `Z`. |

## Render

- **El servicio se suspende tras 15 min sin tráfico** (plan gratuito). Las peticiones de la ESP32 cada 30 s lo mantienen activo mientras el dispositivo esté encendido.
- **Logs:** Render → servicio → *Logs*.
- **Base de datos expirada:** cree una nueva y restaure el respaldo, o migre a Neon/Supabase.
