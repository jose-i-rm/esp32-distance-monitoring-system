# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [SemVer](https://semver.org/lang/es/).

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
