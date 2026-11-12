# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [SemVer](https://semver.org/lang/es/).

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
