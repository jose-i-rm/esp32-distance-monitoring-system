# Despliegue en Render (backend de la cámara PTZ)

El código vive en GitHub; Render solo **ejecuta** el backend FastAPI que guarda las credenciales de Tuya y hace de puente seguro entre el dashboard (GitHub Pages) y Tuya Cloud. Se redespliega automáticamente con cada push a `main` que modifique `backend/`.

> GitHub Pages solo sirve archivos estáticos: si las claves de Tuya estuvieran en el dashboard, cualquiera podría leerlas y mover la cámara. Por eso el backend se ejecuta aparte.

El Blueprint [`/render.yaml`](../../render.yaml) crea:

- `esp32-distance-api`: servicio web **Docker** (plan free) con `ffmpeg` incluido (fotos desde el vídeo en vivo).
- Base de datos **SQLite** dentro del contenedor (`/tmp`). Render elimina las PostgreSQL gratuitas a los 30 días; los eventos de la cámara se vuelven a sincronizar desde Tuya Cloud (7 días de historial) con el sondeo cada 5 min.

## Pasos

1. Entre en https://dashboard.render.com con **Sign in with GitHub**.
2. **New → Blueprint** → autorice el acceso al repositorio `jose-i-rm/esp32-distance-monitoring-system` y selecciónelo.
3. Render detecta `render.yaml` y pide los valores marcados `sync: false`. Cópielos de `backend/.env` (local, nunca del repositorio):

   | Variable | Origen |
   |----------|--------|
   | `TUYA_ACCESS_ID` | Tuya Developer Platform → Cloud → proyecto → *Authorization Key* → Access ID |
   | `TUYA_ACCESS_SECRET` | Ídem → Access Secret |
   | `TUYA_DEVICE_ID` | Device ID de la cámara |

4. **Apply**. El primer build (imagen Docker + ffmpeg) tarda unos 5 min.
5. Compruebe `https://esp32-distance-api.onrender.com/health` → `"status": "ok"`.
6. En el servicio → **Environment**, copie `ADMIN_API_KEY` (generada por Render). Es la clave que se introduce en el panel **Cámara PTZ Tuya** del dashboard; **no** la publique.

El dashboard ya apunta a `https://esp32-distance-api.onrender.com` (`CAMERA_API_URL` en [`frontend/js/config.js`](../../frontend/js/config.js)). Si Render asigna otro nombre, actualice ese valor.

## Consideraciones del plan gratuito

- **Arranque en frío:** el servicio se suspende tras 15 min sin tráfico; la primera petición tarda ~1 min. El panel muestra «Conectando… (el backend gratuito puede tardar ~1 min en despertar)».
- **Datos efímeros:** la SQLite se reinicia con cada despliegue o suspensión. Las lecturas del HC-SR04 no se ven afectadas (viven en Firebase).
- Para conservar el historial de eventos de la cámara, use una PostgreSQL permanente ([Neon](https://neon.tech) o [Supabase](https://supabase.com)) y cambie `DATABASE_URL`:

  ```
  postgresql://usuario:password@host/esp32_monitoring?sslmode=require
  ```

## Despliegue manual (sin Blueprint)

| Campo | Valor |
|-------|-------|
| Runtime | Docker |
| Dockerfile Path | `./backend/Dockerfile` |
| Docker Context | `./backend` |
| Health Check Path | `/health` |
| Variables | `DATABASE_URL=sqlite:////tmp/esp32_monitoring.db`, `CORS_ORIGINS=https://jose-i-rm.github.io`, `ADMIN_API_KEY`, `TUYA_ACCESS_ID`, `TUYA_ACCESS_SECRET`, `TUYA_DEVICE_ID`, `TUYA_ENDPOINT=https://openapi.tuyaus.com`, `TUYA_POLL_INTERVAL_SECONDS=300`, `ENVIRONMENT=production` |
