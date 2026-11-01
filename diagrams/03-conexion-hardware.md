# 3. Conexión de hardware

## Diagrama de cableado

```mermaid
flowchart LR
    subgraph HC["HC-SR04"]
        H_VCC["VCC"]
        H_TRIG["TRIG"]
        H_ECHO["ECHO"]
        H_GND["GND"]
    end

    subgraph CAM["ESP32-CAM AI Thinker"]
        C_5V["5V"]
        C_13["GPIO13"]
        C_14["GPIO14"]
        C_GND["GND"]
    end

    subgraph MB["ESP32-CAM-MB"]
        USB["Micro-USB<br/>CH340 + regulador"]
    end

    PC["💻 PC<br/>Arduino IDE / PlatformIO"]

    H_VCC -- "🔴 Rojo" --- C_5V
    H_GND -- "⚫ Negro" --- C_GND
    H_TRIG -- "🟡 Amarillo" --- C_13
    H_ECHO -- "🟢 Verde" --- C_14

    CAM === MB
    MB -- "Cable de datos" --- PC

    linkStyle 0 stroke:#ef4444,stroke-width:3px
    linkStyle 1 stroke:#111827,stroke-width:3px
    linkStyle 2 stroke:#eab308,stroke-width:3px
    linkStyle 3 stroke:#22c55e,stroke-width:3px
```

## Tabla de conexiones

| HC-SR04 | ESP32-CAM | Color del cable | Función |
|---------|-----------|-----------------|---------|
| VCC | 5V | 🔴 Rojo | Alimentación del sensor |
| GND | GND | ⚫ Negro | Referencia común |
| TRIG | GPIO13 | 🟡 Amarillo | Pulso de disparo (salida ESP32) |
| ECHO | GPIO14 | 🟢 Verde | Pulso de eco (entrada ESP32) |

## Diagrama de señales

```mermaid
sequenceDiagram
    participant ESP as ESP32-CAM
    participant HC as HC-SR04
    ESP->>HC: TRIG = HIGH durante 10 µs (GPIO13)
    HC-->>HC: Emite ráfaga de 8 pulsos a 40 kHz
    HC->>ESP: ECHO = HIGH mientras viaja el sonido (GPIO14)
    ESP-->>ESP: pulseIn() mide t (µs)
    ESP-->>ESP: distancia = t × 0.0343 / 2
```

> ⚠️ **Nivel lógico de ECHO:** el HC-SR04 alimentado a 5 V entrega 5 V en ECHO, mientras que los GPIO del ESP32 trabajan a 3.3 V. Ver la recomendación del divisor resistivo en [docs/hardware.md](../docs/hardware.md#4-consideraciones-eléctricas).
