# Firmware (ESP32-CAM)

> El firmware de la ESP32-CAM **ya está implementado** por fuera de este alcance (WiFi + NTP + HC-SR04, lectura cada 30 s). Esta carpeta documenta el **contrato de integración** que debe cumplir para enviar datos al backend. Puede versionar aquí el código fuente existente (Arduino IDE y/o PlatformIO).

## Estructura sugerida

```
firmware/
├── README.md                      # Este documento (contrato de integración)
├── arduino/<nombre_sketch>/       # Sketch actual (.ino)
└── platformio/                    # Proyecto PlatformIO (opcional)
```

> No suba credenciales WiFi ni la API Key: los archivos `config.h` y `secrets.h` están excluidos en `.gitignore`.

## Contrato con el backend

| Elemento | Valor |
|----------|-------|
| Método | `POST` |
| URL local | `http://<IP_DEL_PC>:8000/api/v1/measurements` |
| URL producción | `https://<servicio>.onrender.com/api/v1/measurements` |
| Cabeceras | `Content-Type: application/json` · `X-API-Key: <DEVICE_API_KEY>` |
| Respuesta exitosa | `201 Created` |

### Cuerpo JSON

```json
{ "timestamp": "2026-11-01T11:08:55-05:00", "distance_cm": 214.05 }
```

| Campo | Tipo | Reglas |
|-------|------|--------|
| `timestamp` | string ISO 8601 | Con zona horaria (`Z` o `-05:00`). Si se omite la zona, el backend asume **UTC**. |
| `distance_cm` | número | Entre 0 y 1000. Se almacena con 2 decimales. |

### Equivalencia con la salida serie actual

| Monitor serie | JSON a enviar |
|---------------|---------------|
| `2026-11-01 11:08:55 \| Distancia: 214.05 cm` | `{"timestamp":"2026-11-01T11:08:55-05:00","distance_cm":214.05}` |
| `2026-11-01 11:09:25 \| Distancia: 4.92 cm` | `{"timestamp":"2026-11-01T11:09:25-05:00","distance_cm":4.92}` |

## Fragmento de referencia para el envío HTTP

Si el firmware actual solo imprime en el monitor serie, este fragmento muestra cómo publicar la lectura usando las librerías estándar del core ESP32 (`HTTPClient`, `WiFiClientSecure`):

```cpp
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

const char* API_URL = "https://<servicio>.onrender.com/api/v1/measurements";
const char* DEVICE_API_KEY = "<DEVICE_API_KEY>";

// timestamp: "2026-11-01T11:08:55-05:00" (strftime "%Y-%m-%dT%H:%M:%S-05:00" o UTC con "Z")
bool enviarMedicion(const char* timestamp, float distanciaCm) {
  WiFiClientSecure client;
  client.setInsecure();               // Para validar TLS use client.setCACert(ROOT_CA)
  HTTPClient http;
  http.begin(client, API_URL);        // Para HTTP local use un WiFiClient normal
  http.setTimeout(20000);             // Render gratuito puede tardar ~50 s en despertar
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", DEVICE_API_KEY);

  char body[96];
  snprintf(body, sizeof(body), "{\"timestamp\":\"%s\",\"distance_cm\":%.2f}", timestamp, distanciaCm);
  int code = http.POST(body);
  http.end();
  return code == 201;
}
```

## Prueba sin hardware

Puede simular el dispositivo con `curl` (ver [../api/examples/curl.md](../api/examples/curl.md)) o con el simulador incluido:

```bash
cd backend
python scripts/simulate_device.py --url http://localhost:8000 --api-key <DEVICE_API_KEY>
```
