<div align="center">

# 📡 ESP32 Distance Monitoring System

**Sistema IoT de monitoreo de distancias basado en ESP32-CAM y HC-SR04 con sincronización NTP, transmisión WiFi y almacenamiento en Firebase.**

### 🔴 [Ver el proyecto en vivo → jose-i-rm.github.io/esp32-distance-monitoring-system](https://jose-i-rm.github.io/esp32-distance-monitoring-system/)

![ESP32](https://img.shields.io/badge/ESP32--CAM-AI%20Thinker-E7352C?logo=espressif&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Realtime%20Database-FFCA28?logo=firebase&logoColor=black)
![Chart.js](https://img.shields.io/badge/Chart.js-4-FF6384?logo=chartdotjs&logoColor=white)
![Excel](https://img.shields.io/badge/Exportar-Excel%20.xlsx-217346?logo=microsoftexcel&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Dashboard-222?logo=github)
![License](https://img.shields.io/badge/Licencia-MIT-green)

[Demo en vivo](https://jose-i-rm.github.io/esp32-distance-monitoring-system/) · [Arquitectura](#-arquitectura) · [Hardware](#-hardware-utilizado) · [Firmware](firmware/README.md) · [Firebase](docs/firebase.md) · [Roadmap](#-roadmap)

</div>

---

## 📖 Introducción

**ESP32 Distance Monitoring System** es una solución IoT de extremo a extremo. Un sensor ultrasónico **HC-SR04**, conectado a una **ESP32-CAM AI Thinker**, mide la distancia **cada 30 segundos**. La ESP32 marca cada lectura con la hora real (**NTP**) y la envía por **WiFi/HTTPS** a **Firebase Realtime Database**. Un **dashboard web** público muestra los datos y permite **descargarlos en Excel**.

**Novedad v3:** cuando la distancia cambia **10 cm o más** entre dos lecturas consecutivas, la ESP32 registra una **alerta** y el dashboard la recibe **en tiempo real** con **sonido y mensaje**.

```
2026-11-01 11:08:55 | Distancia: 214.05 cm
  -> Guardado en Firebase
2026-11-01 11:09:25 | Distancia: 4.92 cm
  -> Guardado en Firebase
```

**¿Por qué Firebase?** El plan gratuito **Spark** no expira, no se suspende por inactividad y no requiere tarjeta. Ofrece 1 GB de almacenamiento y 10 GB de descarga al mes, suficiente para años de lecturas (≈ 2 880 lecturas/día ≈ 9 MB/mes).

## 🌐 Dashboard en vivo

👉 **https://jose-i-rm.github.io/esp32-distance-monitoring-system/**

| Funcionalidad | Detalle |
|---------------|---------|
| Distancia actual | Última lectura con barra proporcional (0–400 cm). |
| Estado del dispositivo | 🟢 En línea · 🟡 Retrasado · 🔴 Fuera de línea (según la antigüedad de la última lectura). |
| Estado de conexión | Conexión y latencia con Firebase. |
| Estadísticas | Mínimo, máximo, promedio y total de registros. |
| Gráfico temporal | Últimas 20 / 50 / 120 / 500 lecturas (Chart.js). |
| Historial | Tabla con hora de lectura y hora de recepción en Firebase. |
| **Descarga en Excel** | Archivo `.xlsx` con hojas **Lecturas** y **Resumen**. Puede filtrarse por rango de fechas o incluir el histórico completo. |
| **Alertas en tiempo real** | Banner con mensaje y **sonido** (botón *Activar sonido*, requisito del navegador) cuando la distancia cambia ≥ 10 cm. |
| **Historial de alertas** | Tabla con hora, distancia anterior, actual, cambio y tipo (acercamiento/alejamiento); las lecturas con alerta se marcan en rojo en el gráfico. |

Actualización inmediata por **streaming** de Firebase (Server-Sent Events) y refresco de respaldo cada 15 s.

## 🎯 Objetivos

**General:** implementar un sistema IoT funcional para la adquisición, almacenamiento y visualización de mediciones de distancia en tiempo casi real.

**Específicos:**

1. Adquirir mediciones del HC-SR04 con la ESP32-CAM y marcarlas con hora real sincronizada por NTP.
2. Transmitir las mediciones cada 30 s por HTTPS a Firebase con autenticación del dispositivo.
3. Persistir el histórico de forma permanente en Firebase Realtime Database.
4. Visualizar distancia actual, histórico, gráfico temporal y estado del dispositivo en un dashboard responsive.
5. Permitir la descarga de las lecturas en formato Excel.
6. Desplegar la solución en servicios gratuitos permanentes (Firebase Spark + GitHub Pages).

## 🏗 Arquitectura

```mermaid
flowchart TD
    HC["HC-SR04<br/>Sensor ultrasónico"] -->|TRIG GPIO13 / ECHO GPIO14| ESP["ESP32-CAM<br/>WiFi + NTP"]
    ESP -->|"1. signInWithPassword (cada ~55 min)"| AUTH["Firebase Authentication<br/>cuenta del dispositivo"]
    ESP -->|"2. HTTPS PATCH cada 30 s<br/>?auth=idToken"| DB[("Firebase Realtime Database<br/>/measurements · /alerts · /stats")]
    DB -->|"HTTPS GET + streaming SSE de /stats"| UI["Dashboard · GitHub Pages<br/>HTML5 · JS · Chart.js · SheetJS"]
    UI -->|.xlsx| XLS["📊 Excel"]
    UI -->|"🔔 sonido + mensaje"| USR["Usuario"]
```

| Capa | Tecnología | Hosting |
|------|-----------|---------|
| Borde | ESP32-CAM AI Thinker + HC-SR04 (Arduino, `WiFiClientSecure` + `HTTPClient`) | Red WiFi doméstica |
| Autenticación | Firebase Authentication (correo/contraseña del dispositivo) | Firebase (Spark, gratis) |
| Datos | Firebase Realtime Database + reglas de seguridad | Firebase (Spark, gratis) |
| Frontend | HTML5, CSS3, Vanilla JavaScript, Chart.js, SheetJS | GitHub Pages |
| Documentación | Markdown + Mermaid.js | GitHub |

**Seguridad:** la lectura de los datos es pública (dashboard). Solo la cuenta de la ESP32 puede escribir. Las reglas validan el formato, el rango (0–1000 cm) y la hora del servidor, e impiden sobrescribir o borrar lecturas. Ver [firebase/database.rules.json](firebase/database.rules.json) y [docs/firebase.md](docs/firebase.md).

📐 Más diagramas: [arquitectura general](diagrams/01-arquitectura-general.md) · [hardware](diagrams/03-conexion-hardware.md) · [pipeline IA](diagrams/05-pipeline-ia.md)

## 🗄 Modelo de datos (Firebase)

```json
{
  "measurements": {
    "1793553552": {
      "epoch": 1793553552,
      "ts": "2026-11-01T11:08:55-05:00",
      "distance_cm": 214.05,
      "received_at": 1793553553502,
      "device": "esp32-cam-01"
    }
  },
  "alerts": {
    "1793553582": {
      "epoch": 1793553582,
      "ts": "2026-11-01T11:09:25-05:00",
      "previous_cm": 214.05,
      "distance_cm": 4.92,
      "delta_cm": -209.13,
      "type": "acercamiento",
      "threshold_cm": 10.0,
      "received_at": 1793553583410,
      "device": "esp32-cam-01"
    }
  },
  "stats": {
    "count": 2,
    "latest": { "...": "copia de la última lectura" },
    "alert_count": 1,
    "last_alert": { "...": "copia de la última alerta" }
  }
}
```

| Campo | Descripción |
|-------|-------------|
| clave / `epoch` | Segundos UTC de la lectura (NTP). Ordena las lecturas cronológicamente. |
| `ts` | Fecha y hora local del dispositivo (ISO 8601, UTC-5). |
| `distance_cm` | Distancia medida, 2 decimales. |
| `received_at` | Hora del servidor de Firebase al recibir la lectura (ms). |
| `device` | Identificador del dispositivo. |
| `previous_cm` / `delta_cm` | (Alertas) Lectura anterior y cambio `actual − anterior`; negativo = acercamiento. |
| `type` / `threshold_cm` | (Alertas) `acercamiento` o `alejamiento` y umbral aplicado (10 cm). |

## 🔧 Hardware utilizado

| Componente | Función |
|-----------|---------|
| **ESP32-CAM AI Thinker** | Microcontrolador con WiFi, cámara OV2640 y PSRAM. |
| **ESP32-CAM-MB** | Programador USB-serie (CH340) y alimentación. |
| **HC-SR04** | Sensor ultrasónico de distancia (2–400 cm). |
| **Cable Micro-USB de datos** | Programación y alimentación. |
| **Red WiFi 2.4 GHz** | Conectividad a Internet. |

Detalle técnico: [docs/hardware.md](docs/hardware.md).

## 🔌 Esquema de conexiones

| HC-SR04 | ESP32-CAM | Cable |
|---------|-----------|-------|
| VCC | 5V | 🔴 Rojo |
| GND | GND | ⚫ Negro |
| TRIG | GPIO13 | 🟡 Amarillo |
| ECHO | GPIO14 | 🟢 Verde |

```mermaid
flowchart LR
    subgraph HC["HC-SR04"]
        VCC
        TRIG
        ECHO
        GND
    end
    subgraph CAM["ESP32-CAM"]
        V5["5V"]
        G13["GPIO13"]
        G14["GPIO14"]
        G["GND"]
    end
    VCC -- Rojo --- V5
    GND -- Negro --- G
    TRIG -- Amarillo --- G13
    ECHO -- Verde --- G14
    linkStyle 0 stroke:#ef4444,stroke-width:3px
    linkStyle 1 stroke:#111827,stroke-width:3px
    linkStyle 2 stroke:#eab308,stroke-width:3px
    linkStyle 3 stroke:#22c55e,stroke-width:3px
```

> ⚠️ ECHO entrega 5 V y los GPIO del ESP32 son de 3.3 V. Se recomienda un divisor resistivo 1 kΩ / 2 kΩ — ver [consideraciones eléctricas](docs/hardware.md#4-consideraciones-eléctricas).

## 📁 Estructura del repositorio

```
/
├── README.md                 # Este documento
├── firebase.json             # Configuración de Firebase CLI (reglas de la BD)
├── .firebaserc               # Proyecto Firebase por defecto
├── firebase/                 # Reglas de seguridad de Realtime Database
├── firmware/                 # Sketch Arduino de la ESP32-CAM (Firebase)
├── frontend/                 # Dashboard HTML5 + JS + Chart.js + SheetJS (GitHub Pages)
├── processing/               # Pipeline ETL en Python: preprocesamiento, filtrado y transformación
├── .github/workflows/        # Despliegue en GitHub Pages y CI del backend alternativo
├── docs/                     # Documentación técnica
├── diagrams/                 # Diagramas Mermaid
├── backend/ · api/ · deployment/ · render.yaml
│                             # Backend alternativo FastAPI + PostgreSQL (opcional, no usado en producción)
└── LICENSE
```

## ⚙ Puesta en marcha

### 1. Firmware (ESP32-CAM)

1. Abra [`firmware/esp32_distance_firebase/esp32_distance_firebase.ino`](firmware/esp32_distance_firebase/esp32_distance_firebase.ino) en Arduino IDE.
2. Copie `secrets.example.h` como `secrets.h` en la misma carpeta y complete el WiFi, la API key web de Firebase y la clave del dispositivo.
3. Placa **AI Thinker ESP32-CAM** (core ESP32 de Espressif 3.x) → **Subir**.
4. Monitor serie a 115200 baudios: cada 30 s debe verse `-> Guardado en Firebase`.

Detalle: [firmware/README.md](firmware/README.md).

### 2. Firebase

El proyecto `esp32-distance-jirm-450f1` ya está creado y configurado. Para redesplegar las reglas:

```bash
npm install -g firebase-tools
firebase login
firebase deploy --only database
```

Guía completa (crear desde cero, cuenta del dispositivo, límites): [docs/firebase.md](docs/firebase.md).

### 3. Dashboard

Se publica automáticamente en GitHub Pages con cada push a `main` que modifique `frontend/`. Para probarlo localmente:

```bash
cd frontend && python -m http.server 5500
# http://localhost:5500
```

### 4. Procesamiento de datos

```bash
pip install -r processing/requirements.txt
python processing/pipeline.py      # descarga de Firebase → processing/output/ (Excel, CSV, figuras)
```

Detalle de las operaciones: [processing/README.md](processing/README.md).

## 🗺 Roadmap

| Fase | Alcance | Estado |
|------|---------|--------|
| 1 | Firmware: WiFi + NTP + HC-SR04 cada 30 s | ✅ Completado |
| 2 | Envío autenticado a Firebase Realtime Database | ✅ Completado |
| 3 | Dashboard en GitHub Pages + descarga en Excel | ✅ Completado |
| 4 | Alertas por cambio de distancia (≥ 10 cm) con sonido y mensaje en tiempo real | ✅ Completado |
| 5 | Procesamiento de datos (preprocesamiento, filtrado y transformación) | ✅ Completado |
| 6 | Servo SG90: barrido angular tipo radar | 📋 Siguiente iteración |
| 7 | MQTT (broker, LWT, comandos bidireccionales) | 📋 Planificado |
| 8 | Captura de imágenes con ESP32-CAM | 📋 Planificado |
| 9 | Visión artificial con Hugging Face | 📋 Planificado |

## 🔮 Futuras mejoras

- Búfer local en la ESP32 para reenviar lecturas cuando se pierde el WiFi.
- Notificaciones externas de las alertas (Telegram/correo).
- **MQTT**, **servo SG90**, **cámara** e **IA con Hugging Face** — ver [docs/futuras-integraciones.md](docs/futuras-integraciones.md).

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/firebase.md](docs/firebase.md) | Proyecto Firebase, reglas, cuenta del dispositivo y límites del plan gratuito |
| [firmware/README.md](firmware/README.md) | Firmware, configuración y contrato de datos |
| [docs/frontend.md](docs/frontend.md) | Dashboard, alertas con sonido y exportación a Excel |
| [processing/README.md](processing/README.md) | Pipeline de preprocesamiento, filtrado y transformación |
| [docs/hardware.md](docs/hardware.md) | Componentes, conexiones y consideraciones eléctricas |
| [docs/credenciales-pendientes.md](docs/credenciales-pendientes.md) | Estado de cuentas y credenciales |
| [docs/solucion-de-problemas.md](docs/solucion-de-problemas.md) | Errores frecuentes |
| [docs/arquitectura.md](docs/arquitectura.md) · [docs/instalacion.md](docs/instalacion.md) · [docs/base-de-datos.md](docs/base-de-datos.md) | Backend alternativo FastAPI + PostgreSQL |

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Consulte [LICENSE](LICENSE).
