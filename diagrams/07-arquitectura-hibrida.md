# 7. Arquitectura híbrida: radar ESP32 + cámara PTZ Tuya

## Vista general

```mermaid
flowchart TD
    RadarESP32["ESP32 + HC-SR04 + SG90"]
    TuyaCam["Cámara PTZ Tuya"]
    FastAPI["FastAPI"]
    DB["PostgreSQL"]
    Dashboard["Dashboard"]

    RadarESP32 --> FastAPI
    TuyaCam --> FastAPI
    FastAPI --> DB
    DB --> Dashboard
```

## Detalle de flujos

```mermaid
flowchart LR
    subgraph Borde
        HC["HC-SR04"] --> ESP["ESP32<br/>NTP · WiFi"]
        SG["Servo SG90<br/>barrido 0–180°"] --- ESP
    end

    subgraph Tuya["Tuya IoT Cloud"]
        CAM["Cámara PTZ<br/>humanoid detection<br/>abnormal sound"] --> TC["IoT Core<br/>OpenAPI"]
        CAM -.-> LS["IoT Video Live Stream<br/>(pendiente de autorizar)"]
    end

    subgraph Backend["Backend FastAPI"]
        M["/api/v1/measurements"]
        C["/api/camera/*"]
        S["TuyaClient + CameraService<br/>firma HMAC · token · PTZ"]
        P["Sondeo de eventos<br/>(TUYA_POLL_INTERVAL_SECONDS)"]
        AI["Futuro: reconocimiento facial"]
    end

    ESP -->|"HTTPS POST cada 30 s<br/>X-API-Key"| M
    TC <-->|"HTTPS firmado"| S
    LS -.->|"RTSP/HLS"| S
    C --> S
    P --> S
    S -.-> AI
    M --> DB[("PostgreSQL<br/>measurements · camera_events")]
    S --> DB
    DB --> UI["Dashboard HTML5 + Chart.js<br/>panel Cámara PTZ"]
    UI -->|"X-API-Key admin"| C
```

## Secuencia: detección humanoide → evento guardado

```mermaid
sequenceDiagram
    participant Cam as Cámara PTZ
    participant Tuya as Tuya Cloud
    participant API as FastAPI
    participant DB as PostgreSQL
    participant UI as Dashboard

    Cam->>Tuya: alarm_message (cmd=ipc_human, imagen cifrada)
    loop cada TUYA_POLL_INTERVAL_SECONDS o POST /events/sync
        API->>Tuya: GET /v1.0/devices/{id}/logs (firmado)
        Tuya-->>API: logs paginados
        API->>API: normaliza (humanoid_detection, abnormal_sound…)
        API->>DB: INSERT sin duplicados
    end
    UI->>API: GET /api/camera/events (X-API-Key)
    API->>DB: SELECT
    API-->>UI: eventos (sin claves de imagen)
    UI->>API: POST /api/camera/ptz {"direction":"left"}
    API->>Tuya: ptz_control=6 → espera → ptz_stop
```

## Correlación radar ↔ cámara (siguiente iteración)

Cuando el radar detecte un cambio ≥ 10 cm en el ángulo θ del servo, el backend podrá:

1. Buscar eventos `humanoid_detection` en una ventana de ±30 s.
2. Si no hay, orientar la cámara (`ptz_control`/`ipc_preset_action` según θ) y solicitar snapshot.
3. Registrar un **incidente** con la medición y el evento asociados (ver [reconocimiento facial](../docs/reconocimiento-facial.md)).
