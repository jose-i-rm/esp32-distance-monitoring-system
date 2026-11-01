# 1. Arquitectura general

Vista de alto nivel de los componentes del sistema y sus responsabilidades.

```mermaid
flowchart LR
    subgraph EDGE["🔌 Capa de borde (IoT)"]
        S["HC-SR04<br/>Sensor ultrasónico"]
        E["ESP32-CAM<br/>AI Thinker<br/>WiFi + NTP"]
        S -- "TRIG / ECHO<br/>GPIO13 / GPIO14" --> E
    end

    NTP[("Servidores NTP<br/>pool.ntp.org")]
    E -. "UDP 123<br/>sincronización horaria" .-> NTP

    subgraph CLOUD["☁️ Backend (Render / Railway / Fly.io)"]
        API["FastAPI<br/>Uvicorn"]
        ORM["SQLAlchemy 2.0<br/>Pydantic v2"]
        MIG["Alembic<br/>migraciones"]
        DB[("PostgreSQL<br/>tabla measurements")]
        API --> ORM --> DB
        MIG -. "esquema" .-> DB
    end

    subgraph WEB["🖥️ Frontend (GitHub Pages)"]
        UI["Dashboard HTML5<br/>Vanilla JS + Chart.js"]
    end

    E -- "HTTPS POST<br/>/api/v1/measurements<br/>X-API-Key" --> API
    UI -- "HTTPS GET<br/>/api/v1/measurements<br/>/health" --> API
    U(["👤 Usuario"]) --> UI
```

## Componentes

| Capa | Componente | Responsabilidad |
|------|------------|-----------------|
| Borde | HC-SR04 | Medición de distancia por tiempo de vuelo ultrasónico (2–400 cm). |
| Borde | ESP32-CAM | Disparo del sensor, marca de tiempo NTP y envío HTTP cada 30 s. |
| Backend | FastAPI | Validación (Pydantic), autenticación por API Key y exposición REST. |
| Backend | PostgreSQL | Persistencia histórica de mediciones. |
| Frontend | Dashboard | Visualización en tiempo casi real, historial y estado del dispositivo. |
