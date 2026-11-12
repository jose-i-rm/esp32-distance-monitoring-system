# 2. Flujo de datos

Recorrido de una medición desde el sensor hasta el dashboard.

```mermaid
flowchart TD
    A([ESP32-S3<br/>ciclo cada 30 s]) --> B[Lectura HC-SR04<br/>distancia en cm]
    B --> C[Timestamp NTP]
    C --> D[JSON<br/>timestamp + distance_cm]
    D --> E[HTTP POST /api/v1/measurements<br/>cabecera X-API-Key]

    subgraph BACKEND["Backend FastAPI"]
        E --> F{¿API Key válida?}
        F -- No --> F1[401 Unauthorized]
        F -- Sí --> G{¿Esquema válido?<br/>Pydantic}
        G -- No --> G1[422 Unprocessable Entity]
        G -- Sí --> H[Normalizar timestamp a UTC]
        H --> I[(PostgreSQL<br/>INSERT measurements)]
        I --> J[201 Created]
    end

    subgraph DASHBOARD["Dashboard (GitHub Pages)"]
        K[GET /health] --> L[GET /api/v1/measurements]
        L --> M[Tarjetas + Chart.js + Historial]
    end

    I -. consulta periódica .-> L
```

## Formato del mensaje

```json
{
  "timestamp": "2026-11-01T16:08:55Z",
  "distance_cm": 214.05
}
```

> La lectura `2026-11-01 11:08:55 | Distancia: 214.05 cm` (hora local Colombia, UTC-5) equivale a `2026-11-01T16:08:55Z` en UTC. El backend acepta ambos formatos (`...Z` o `...-05:00`) y almacena siempre en UTC; el dashboard la muestra en la hora local del navegador.
