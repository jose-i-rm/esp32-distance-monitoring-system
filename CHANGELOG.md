# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [SemVer](https://semver.org/lang/es/).

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
