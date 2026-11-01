# 4. Flujo HTTP

## Registro de una medición (dispositivo → API)

```mermaid
sequenceDiagram
    autonumber
    participant ESP as ESP32-CAM
    participant API as FastAPI
    participant SEC as verify_device_api_key
    participant VAL as Pydantic
    participant DB as PostgreSQL

    ESP->>API: POST /api/v1/measurements<br/>X-API-Key: ****<br/>{"timestamp","distance_cm"}
    API->>SEC: Validar cabecera X-API-Key
    alt API Key inválida
        SEC-->>ESP: 401 Unauthorized
    else API Key válida
        API->>VAL: Validar esquema MeasurementCreate
        alt Datos inválidos
            VAL-->>ESP: 422 Unprocessable Entity
        else Datos válidos
            API->>DB: INSERT INTO measurements
            DB-->>API: id, created_at
            API-->>ESP: 201 Created + MeasurementRead
        end
    end
```

## Consulta desde el dashboard (navegador → API)

```mermaid
sequenceDiagram
    autonumber
    participant UI as Dashboard (GitHub Pages)
    participant API as FastAPI
    participant DB as PostgreSQL

    loop Cada 15 s (configurable)
        UI->>API: GET /health
        API->>DB: SELECT 1
        API-->>UI: 200 {"status":"ok","database":"ok"}
        UI->>API: GET /api/v1/measurements?limit=50
        API->>DB: SELECT ... ORDER BY timestamp DESC LIMIT 50
        API-->>UI: 200 {"items":[...],"total":N}
        UI-->>UI: Actualiza tarjetas, gráfico e historial
    end
```

## Códigos de respuesta

| Código | Significado | Endpoint |
|--------|-------------|----------|
| 200 | Consulta exitosa | `GET` |
| 201 | Medición creada | `POST /api/v1/measurements` |
| 401 | API Key ausente o inválida | `POST /api/v1/measurements` |
| 404 | No existen mediciones | `GET /api/v1/measurements/latest` |
| 422 | Error de validación | Todos |
| 503 | Base de datos no disponible | `GET /health` |
