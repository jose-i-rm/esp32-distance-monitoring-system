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

    subgraph S3["ESP32-S3 N16R8 (placa de expansión)"]
        C_33["3V3"]
        C_12["GPIO12"]
        C_13["GPIO13"]
        C_GND["GND"]
        COM["USB-C COM<br/>CH343"]
    end

    PC["💻 PC<br/>Arduino IDE / arduino-cli"]

    H_VCC -- "🟡 Amarillo" --- C_33
    H_GND -- "🟤 Marrón" --- C_GND
    H_TRIG -- "🟠 Naranja" --- C_12
    H_ECHO -- "🔴 Rojo" --- C_13

    COM -- "Cable USB-C de datos" --- PC

    linkStyle 0 stroke:#eab308,stroke-width:3px
    linkStyle 1 stroke:#78350f,stroke-width:3px
    linkStyle 2 stroke:#f97316,stroke-width:3px
    linkStyle 3 stroke:#ef4444,stroke-width:3px
```

## Tabla de conexiones

| HC-SR04 | ESP32-S3 N16R8 | Color del cable | Función |
|---------|----------------|-----------------|---------|
| VCC | 3V3 | 🟡 Amarillo | Alimentación del sensor |
| GND | GND | 🟤 Marrón | Referencia común |
| TRIG | GPIO12 | 🟠 Naranja | Pulso de disparo (salida ESP32) |
| ECHO | GPIO13 | 🔴 Rojo | Pulso de eco (entrada ESP32) |

## Diagrama de señales

```mermaid
sequenceDiagram
    participant ESP as ESP32-S3
    participant HC as HC-SR04
    ESP->>HC: TRIG = HIGH durante 10 µs (GPIO12)
    HC-->>HC: Emite ráfaga de 8 pulsos a 40 kHz
    HC->>ESP: ECHO = HIGH mientras viaja el sonido (GPIO13)
    ESP-->>ESP: pulseIn() mide t (µs)
    ESP-->>ESP: distancia = t × 0.0343 / 2
```

> ✅ **Nivel lógico de ECHO:** con el HC-SR04 alimentado a 3V3, ECHO entrega ≤ 3.3 V y se conecta directamente. Si se alimenta a 5 V, use el divisor resistivo de [docs/hardware.md](../docs/hardware.md#4-consideraciones-eléctricas).
