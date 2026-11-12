# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [SemVer](https://semver.org/lang/es/).

## [4.2.0] - 2026-11-12

### Añadido

- **Radar del HC-SR04** en el dashboard (`frontend/js/radar.js`): barrido clásico, eco sobre el rumbo fijo del sensor y rastro de las últimas 10 lecturas con tendencia (se acerca / se aleja / estable), cambio y velocidad.
- **Cámara PTZ en el dashboard:** vídeo en vivo (HLS con hls.js), **Tomar foto** desde el vídeo con descarga, y pad PTZ. Detecta la pantalla de «conectando» de Tuya para no guardar fotos vacías.
- Firmware: **watchdog** de 120 s y límites de handshake TLS (15 s) y conexión HTTP (10 s). Evitan bloqueos como el observado (sin envíos entre 09:47 y 10:02).

### Cambiado

- Backend desplegable en **Render como Docker** con `ffmpeg` y SQLite (`render.yaml`). Las PostgreSQL gratuitas de Render expiran a los 30 días.
- `CAMERA_API_URL` apunta a `https://esp32-distance-api.onrender.com`.
- Rama `main` protegida contra force-push y borrado.

### Nota

- El radar y la PTZ funcionan de forma independiente; la orientación automática de la cámara hacia el sensor llegará con el servo SG90.

## [4.1.0] - 2026-11-12

### Cambiado

- **Origen de datos migrado de la ESP32-CAM AI Thinker a la ESP32-S3 N16R8.** HC-SR04 en TRIG GPIO12 / ECHO GPIO13, alimentado a 3V3 (sin divisor).
- El firmware reutiliza **sin cambios** el endpoint (`PATCH` multiruta a Firebase Realtime Database), la autenticación (Firebase Auth, cuenta `esp32-cam-01@esp32-distance.iot`) y el JSON. Sin cambios en Firebase, reglas ni contratos de API.
- `DEVICE_ID` (campo `device`) pasa a `esp32-s3-01`; las lecturas históricas conservan `esp32-cam-01`.
- Integrada la rama `feature/tuya-ptz-hybrid-surveillance` (PTZ Tuya, eventos humanoid detection, panel del dashboard).

### Añadido

- [docs/migracion-esp32-s3.md](docs/migracion-esp32-s3.md): endpoint real, JSON capturado, campos obligatorios, pruebas en hardware y compatibilidad con el HC-SR04.

## [4.0.0] - 2026-11-11

### Añadido

- **Integración con la cámara PTZ Tuya** (`backend/app/integrations/tuya`): cliente `TuyaClient` reutilizable (firma HMAC-SHA256, token con caché y renovación, errores tipados) y `CameraService` (eventos, PTZ, vídeo, snapshot).
- Endpoints `/api/camera/status`, `/events`, `/events/sync`, `/latest`, `/ptz`, `/snapshot` y `/stream`, protegidos con `ADMIN_API_KEY` (*fail-closed*).
- Tabla `camera_events` (migración Alembic `0002`) con deduplicación; normalización de *humanoid detection* (`ipc_human`), *abnormal sound* (`ipc_bang`), alarm/disalarm y online/offline.
- Sondeo periódico opcional de eventos (`TUYA_POLL_INTERVAL_SECONDS`).
- Script `backend/scripts/tuya_probe.py` para diagnosticar las APIs disponibles sin exponer secretos.
- Panel **Cámara PTZ Tuya** en el dashboard (estado, eventos, pad PTZ, snapshot).
- Documentación: arquitectura híbrida, informe de APIs Tuya, guía de integración, reconocimiento facial futuro, seguridad, radar con servo SG90 y roadmap IA.
- Cabeceras de seguridad HTTP en el backend.

### Cambiado

- `httpx` y `cryptography` pasan a ser dependencias de ejecución del backend.
- `render.yaml` y `docker-compose.yml` declaran las variables de Tuya sin valores (secretos fuera del repo).

## [3.0.0] - 2026-11-05

### Añadido

- **Alertas por cambio de distancia:** el firmware compara cada lectura con la anterior y, si el cambio es ≥ 10 cm, registra la alerta en `/alerts/<epoch>`, `stats/last_alert` y `stats/alert_count` dentro de la misma escritura atómica.
- Reglas de Firebase para `/alerts` (solo escritura del dispositivo, sin sobrescritura, validación de tipos y rangos) y para los nuevos campos de `/stats`.
- Dashboard: actualización en tiempo real por *streaming* REST de Firebase (Server-Sent Events), banner de alerta con mensaje, sonido generado con Web Audio (botón *Activar sonido*), tabla y contador de alertas, y lecturas con alerta resaltadas en el gráfico.
- Pipeline de procesamiento `processing/pipeline.py`: preprocesamiento (tipos, zona horaria, duplicados, rango, huecos, sesiones, latencia), filtro de Hampel, detección de cambios, estados, episodios, normalización y agregación cada 5 min; exporta Excel, CSV, figuras y resumen, y contrasta las alertas del borde con las recalculadas.
- Pruebas del pipeline (pytest) y workflow `Processing CI`.

### Cambiado

- El dashboard ya no depende solo del refresco periódico: el refresco de 15 s queda como respaldo del streaming.

## [2.0.0] - 2026-11-01

### Añadido

- Backend en **Firebase Realtime Database** (plan Spark, permanente) con reglas de seguridad versionadas (`firebase/database.rules.json`).
- Autenticación del dispositivo con Firebase Authentication (correo/contraseña).
- Firmware `firmware/esp32_distance_firebase`: envío HTTPS cada 30 s, renovación automática del token y credenciales en `secrets.h`.
- Descarga de lecturas en **Excel (.xlsx)** desde el dashboard, con filtro por fechas y hoja de resumen.
- Enlace al dashboard en vivo en el README.

### Cambiado

- El dashboard lee los datos directamente de Firebase (sin backend propio).
- El backend FastAPI + PostgreSQL pasa a ser una alternativa opcional.

### Eliminado

- Exportación a CSV (reemplazada por Excel).

## [1.0.0] - 2026-11-01

### Añadido

- API REST FastAPI: `POST/GET /api/v1/measurements`, `GET /api/v1/measurements/latest`, `GET /health`.
- Modelo `Measurement` en PostgreSQL con migración Alembic inicial.
- Autenticación del dispositivo mediante cabecera `X-API-Key`.
- Dashboard HTML5 con Chart.js: distancia actual, última lectura, historial, gráfico, estado del dispositivo y de la conexión.
- Simulador de dispositivo y exportación de OpenAPI.
- Despliegue: Render (Blueprint), Railway, Fly.io, Docker Compose y GitHub Pages.
- CI con pruebas unitarias, migraciones y prueba de humo sobre PostgreSQL.
- Documentación técnica y diagramas Mermaid.
