# 1. Arquitectura general

Vista de alto nivel de los componentes del sistema y sus responsabilidades.

```mermaid
flowchart LR
    subgraph EDGE["🔌 Capa de borde (IoT)"]
        S["HC-SR04<br/>Sensor ultrasónico"]
        E["ESP32-S3 N16R8<br/>WiFi + NTP"]
        S -- "TRIG / ECHO<br/>GPIO12 / GPIO13" --> E
    end

    NTP[("Servidores NTP<br/>pool.ntp.org")]
    E -. "UDP 123<br/>sincronización horaria" .-> NTP

    subgraph CLOUD["☁️ Firebase (plan Spark)"]
        AUTH["Authentication<br/>cuenta del dispositivo"]
        DB[("Realtime Database<br/>/measurements · /stats")]
        RULES["Reglas de seguridad"]
        RULES -. "valida" .-> DB
    end

    subgraph WEB["🖥️ Frontend (GitHub Pages)"]
        UI["Dashboard HTML5<br/>Vanilla JS + Chart.js + SheetJS"]
    end

    E -- "HTTPS signInWithPassword" --> AUTH
    E -- "HTTPS PATCH cada 30 s<br/>?auth=idToken" --> DB
    UI -- "HTTPS GET<br/>lectura pública" --> DB
    U(["👤 Usuario"]) --> UI
    UI -- ".xlsx" --> X["📊 Excel"]
```

## Componentes

| Capa | Componente | Responsabilidad |
|------|------------|-----------------|
| Borde | HC-SR04 | Medición de distancia por tiempo de vuelo ultrasónico (2–400 cm). |
| Borde | ESP32-S3 N16R8 | Disparo del sensor, marca de tiempo NTP y envío HTTPS cada 30 s. |
| Nube | Firebase Authentication | Emite el token del dispositivo (1 h). |
| Nube | Firebase Realtime Database | Persistencia permanente; reglas que solo permiten escribir al dispositivo. |
| Frontend | Dashboard | Visualización en tiempo casi real, historial, estado y descarga en Excel. |
