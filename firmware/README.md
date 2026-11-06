# Firmware (ESP32-CAM)

Sketch Arduino para la **ESP32-CAM AI Thinker** con sensor **HC-SR04**. Funciones:

- Mide la distancia cada **30 s** (TRIG GPIO13, ECHO GPIO14).
- Sincroniza la hora con **NTP** (UTC-5).
- Envía cada lectura por **HTTPS** a **Firebase Realtime Database**, autenticado con la cuenta del dispositivo en Firebase Authentication.
- **v3:** detecta en el borde los cambios de distancia ≥ **10 cm** (`UMBRAL_CAMBIO_CM`) frente a la lectura anterior y registra la alerta en Firebase.

No requiere librerías externas: usa `WiFi`, `WiFiClientSecure` y `HTTPClient` del core ESP32 de Espressif (probado con **3.3.12**).

## Estructura

```
firmware/
└── esp32_distance_firebase/
    ├── esp32_distance_firebase.ino   # Sketch
    ├── secrets.example.h             # Plantilla de credenciales
    └── secrets.h                     # Credenciales reales (NO se versiona)
```

## Cargar en la placa

1. Copie `secrets.example.h` como `secrets.h` y complete:

   | Constante | Valor |
   |-----------|-------|
   | `WIFI_SSID` / `WIFI_PASSWORD` | Red WiFi 2.4 GHz |
   | `FIREBASE_API_KEY` | Consola Firebase → Configuración del proyecto → General → *Clave de API web* |
   | `FIREBASE_DB_URL` | `https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com` |
   | `DEVICE_EMAIL` / `DEVICE_PASSWORD` | Cuenta del dispositivo en Firebase Authentication |
   | `DEVICE_ID` | `esp32-cam-01` |

2. Arduino IDE → Placa **AI Thinker ESP32-CAM** → **Subir** (con el ESP32-CAM-MB).
3. Monitor serie a **115200** baudios.

Compilación por línea de comandos (opcional):

```bash
arduino-cli compile --fqbn esp32:esp32:esp32cam firmware/esp32_distance_firebase
```

## Salida esperada en el monitor serie

```
WiFi conectado
IP: 192.168.1.50
Esperando sincronizacion NTP...
Hora sincronizada
Firebase Auth: sesion iniciada
2026-11-01 11:08:55 | Distancia: 214.05 cm
  -> Guardado en Firebase
2026-11-01 11:09:25 | Distancia: 4.92 cm
  ** ALERTA: cambio de -209.13 cm (214.05 -> 4.92 cm)
  -> Guardado en Firebase (con alerta)
```

## Comportamiento

| Situación | Acción del firmware |
|-----------|---------------------|
| Sin eco del sensor (fuera de rango > ~5 m o desconectado) | Imprime aviso y **no envía** la lectura. |
| Cambio ≥ `UMBRAL_CAMBIO_CM` (10 cm) frente a la lectura anterior | Registra una **alerta** en `/alerts/<epoch>` y `stats/last_alert` en la misma escritura. La primera lectura tras reiniciar no genera alerta (no hay lectura previa). |
| WiFi caído | Reintenta conectar antes de cada envío; la lectura de ese ciclo se pierde si no hay conexión. |
| Token expirado (1 h) | Se renueva automáticamente 5 min antes; ante un `401` inicia sesión de nuevo y reintenta una vez. |
| Temporización | Basada en `millis()`: una lectura cada 30 s aunque el envío HTTPS tarde 1–3 s. |

## Contrato de datos

Una sola petición `PATCH {FIREBASE_DB_URL}/.json?auth=<idToken>` (escritura atómica multiruta):

```json
{
  "measurements/1793553552": {
    "epoch": 1793553552,
    "ts": "2026-11-01T11:08:55-05:00",
    "distance_cm": 214.05,
    "received_at": { ".sv": "timestamp" },
    "device": "esp32-cam-01"
  },
  "stats/latest": { "...": "mismo objeto" },
  "stats/count": { ".sv": { "increment": 1 } }
}
```

Si hay alerta, el mismo `PATCH` agrega:

```json
{
  "alerts/1793553582": {
    "epoch": 1793553582, "ts": "2026-11-01T11:09:25-05:00",
    "previous_cm": 214.05, "distance_cm": 4.92, "delta_cm": -209.13,
    "type": "acercamiento", "threshold_cm": 10.0,
    "received_at": { ".sv": "timestamp" }, "device": "esp32-cam-01"
  },
  "stats/last_alert": { "...": "mismo objeto" },
  "stats/alert_count": { ".sv": { "increment": 1 } }
}
```

Las reglas de Firebase rechazan escrituras de otros usuarios, valores fuera de rango y sobrescrituras. Ver [../docs/firebase.md](../docs/firebase.md).

> **TLS:** el sketch usa `client.setInsecure()` (cifra el tráfico pero no valida el certificado), suficiente para uso académico. Para producción, cargue el certificado raíz de Google con `client.setCACert(...)`.
