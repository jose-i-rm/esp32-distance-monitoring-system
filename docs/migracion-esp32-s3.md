# Migración del origen de datos: ESP32-CAM → ESP32-S3 N16R8

Este documento registra el análisis del repositorio para localizar el **contrato real** que usaba la ESP32-CAM y su reutilización **sin cambios** en la ESP32-S3 N16R8. No se crearon endpoints, no se modificó Firebase (reglas, cuentas ni estructura) y no se alteró ningún contrato de API.

## 1. Endpoint genérico descartado

El firmware de referencia apuntaba a `https://api.midominio.com/api/distance` con un `POST` de `{"device":"esp32-s3","distance_cm":...}`. **Ese endpoint no existe en el proyecto** y el JSON no cumple las reglas de Firebase (faltan `epoch`, `ts`, `received_at`, autenticación y la clave de ruta). Se reemplazó por la implementación real descrita abajo.

## 2. Hallazgos

| # | Elemento | Valor real | Evidencia |
|---|----------|-----------|-----------|
| 1 | **Endpoint de escritura** | `PATCH https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com/.json?auth=<idToken>` (Firebase Realtime Database REST, escritura multiruta atómica) | [`esp32_distance_firebase.ino`](../firmware/esp32_distance_firebase/esp32_distance_firebase.ino) (`enviarMedicion`), [`secrets.example.h`](../firmware/esp32_distance_firebase/secrets.example.h) (`FIREBASE_DB_URL`) |
| 1b | **Endpoint de autenticación** | `POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<FIREBASE_API_KEY>` | `iniciarSesionFirebase()` en el sketch |
| 2 | **Formato JSON** | Objeto multiruta: `measurements/<epoch>`, `stats/latest`, `stats/count` (+ `alerts/<epoch>`, `stats/last_alert`, `stats/alert_count` si hay alerta) | Sketch, [`firebase/database.rules.json`](../firebase/database.rules.json) |
| 3 | **Autenticación** | Firebase Authentication correo/contraseña de la cuenta del dispositivo → `idToken` (1 h, renovado 5 min antes o ante `401`) enviado como parámetro `?auth=` | Sketch, [`firebase.md`](firebase.md) |
| 4 | **Identificador de dispositivo** | **Autorización:** UID `jz0Com63Fkam7s5IuOkolcWOdAL2` (cuenta `esp32-cam-01@esp32-distance.iot`); es el único UID con permiso de escritura en las reglas. **Etiqueta de datos:** campo `device` (texto ≤ 40), antes `esp32-cam-01` | `database.rules.json` (`auth.uid === ...`), `docs/firebase.md` |
| 5 | **Campos obligatorios** | `measurements/<epoch>`: `epoch` (número), `ts` (texto ≤ 40), `distance_cm` (0–1000), `received_at` (`{".sv":"timestamp"}`, debe ser igual a `now`); clave = 10 dígitos; `device` opcional; **no se admiten campos extra**. `alerts/<epoch>`: además `previous_cm`, `delta_cm`, `type` (`acercamiento`/`alejamiento`); `threshold_cm` y `device` opcionales | `database.rules.json` |

> **Backend FastAPI (`POST /api/v1/measurements`, `X-API-Key`):** existe en `backend/` como backend alternativo y en la arquitectura híbrida está documentado como canal **previsto** para el radar, pero **ningún firmware lo usa**. El dashboard y el pipeline de procesamiento leen de Firebase, por lo que el origen de datos real es Firebase.

## 3. Decisiones de la migración

| Aspecto | ESP32-CAM (antes) | ESP32-S3 N16R8 (ahora) |
|---------|-------------------|------------------------|
| TRIG / ECHO | GPIO13 / GPIO14 | **GPIO12 / GPIO13** |
| Alimentación HC-SR04 | 5V (divisor en ECHO) | **3V3** (sin divisor) |
| Endpoint, auth, JSON | Firebase RTDB `PATCH` multiruta | **Idénticos** |
| Cuenta Firebase (`DEVICE_EMAIL`) | `esp32-cam-01@esp32-distance.iot` | **La misma** (las reglas solo autorizan su UID; crear otra exigiría modificar Firebase) |
| Campo `device` (`DEVICE_ID`) | `esp32-cam-01` | `esp32-s3-01` — valor permitido por las reglas (texto ≤ 40); identifica el nuevo origen en el dashboard y en el Excel. Puede volver a `esp32-cam-01` en `secrets.h` si se prefiere conservar la etiqueta. |
| Intervalo | 30 s (`millis()`) | 30 s (`millis()`) |
| Alertas en el borde | ≥ 10 cm | ≥ 10 cm |

## 4. Captura del JSON real

### 4.1 Datos reales almacenados en Firebase (leídos el 2026-11-12)

`GET /stats.json`:

```json
{"count":372,"latest":{"device":"esp32-cam-01","distance_cm":214.38,"epoch":1793569831,"received_at":1793569832196,"ts":"2026-11-01T16:50:31-05:00"}}
```

`GET /measurements.json?orderBy="$key"&limitToLast=2`:

```json
{
  "1793569801": {"device":"esp32-cam-01","distance_cm":214.05,"epoch":1793569801,"received_at":1793569802527,"ts":"2026-11-01T16:50:01-05:00"},
  "1793569831": {"device":"esp32-cam-01","distance_cm":214.38,"epoch":1793569831,"received_at":1793569832196,"ts":"2026-11-01T16:50:31-05:00"}
}
```

### 4.2 Cuerpo que envía la ESP32-S3 (mismo contrato)

`PATCH {FIREBASE_DB_URL}/.json?auth=<idToken>` · `Content-Type: application/json`:

```json
{
  "measurements/1793640000": {"epoch":1793640000,"ts":"2026-11-02T12:20:00-05:00","distance_cm":214.05,"received_at":{".sv":"timestamp"},"device":"esp32-s3-01"},
  "stats/latest":            {"epoch":1793640000,"ts":"2026-11-02T12:20:00-05:00","distance_cm":214.05,"received_at":{".sv":"timestamp"},"device":"esp32-s3-01"},
  "stats/count": {".sv":{"increment":1}}
}
```

Con alerta (|Δ| ≥ 10 cm) el mismo `PATCH` añade:

```json
{
  "alerts/1793640030": {"epoch":1793640030,"ts":"2026-11-02T12:20:30-05:00","previous_cm":214.05,"distance_cm":4.92,"delta_cm":-209.13,"type":"acercamiento","threshold_cm":10.0,"received_at":{".sv":"timestamp"},"device":"esp32-s3-01"},
  "stats/last_alert": {"...": "mismo objeto"},
  "stats/alert_count": {".sv":{"increment":1}}
}
```

## 5. Compatibilidad con el HC-SR04

| Punto | Resultado |
|-------|-----------|
| Pines | GPIO12 y GPIO13 son GPIO de uso general en la ESP32-S3 N16R8: no son *strapping* (0, 3, 45, 46), ni flash (26–32), ni PSRAM octal (35–37), ni USB (19/20). ✅ |
| Nivel lógico ECHO | Con VCC = 3V3 el pulso ECHO es ≤ 3.3 V: conexión directa a GPIO13 **sin divisor**. ✅ (los GPIO del S3 **no** toleran 5 V) |
| Nivel lógico TRIG | 3.3 V es un alto válido para el HC-SR04. Pulso de 10 µs. ✅ |
| Medición | `pulseIn(..., 30000)` → hasta ~5 m; sin eco devuelve `-1` y la lectura no se envía. ✅ |
| Alimentación a 3V3 | ⚠️ El HC-SR04 clásico está especificado a **5 V**. Las variantes **HC-SR04P / RCWL-9610** (3–5.5 V) funcionan correctamente a 3V3; algunos módulos clásicos dan alcance reducido o ningún eco a 3V3. |

**Si el monitor serie muestra repetidamente `Sin eco del sensor`** con el cableado correcto, el módulo es de 5 V: alimente VCC desde el pin **5V/VIN** de la placa y coloque un divisor **1 kΩ / 2 kΩ** en ECHO → GPIO13 (ver [hardware.md](hardware.md#4-consideraciones-eléctricas)). El firmware no cambia.

**Prueba real (2026-11-12):** con el HC-SR04 alimentado a **3V3**, un sketch de diagnóstico midió pulsos estables de ~9 715 µs (**166.6 cm**) con TRIG=GPIO12 / ECHO=GPIO13. El módulo usado es compatible con 3V3. ✅

> Durante la prueba se detectaron TRIG y ECHO invertidos en la placa de expansión (el firmware no recibía eco). En la placa de expansión de 3 columnas (negra = GND, roja = VCC, amarilla = señal), TRIG y ECHO van en la **columna amarilla** de IO12 e IO13.

## 6. Verificación en hardware real

**Compilación** (Arduino core ESP32 3.3.12): 1 026 559 bytes de flash (32 %) y 47 268 bytes de RAM (14 %).

```bash
arduino-cli compile --upload -p COM7 \
  --fqbn esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,CDCOnBoot=default,PartitionScheme=app3M_fat9M_16MB \
  firmware/esp32_distance_firebase
```

**Monitor serie (COM7, 115200):**

```
Conectando a WiFi...
WiFi conectado
Esperando sincronizacion NTP...
Hora sincronizada
Firebase Auth: sesion iniciada
2026-11-12 09:41:55 | Distancia: 166.13 cm
  -> Guardado en Firebase
2026-11-12 09:42:25 | Distancia: 166.63 cm
  -> Guardado en Firebase
2026-11-12 09:42:55 | Distancia: 166.63 cm
  -> Guardado en Firebase
2026-11-12 09:43:25 | Distancia: 166.49 cm
  -> Guardado en Firebase
```

**Datos recibidos en Firebase** (`GET /measurements.json?orderBy="$key"&limitToLast=4`); `stats/count` pasó de 373 a 377:

```json
{
  "1794494515": {"device":"esp32-s3-01","distance_cm":166.13,"epoch":1794494515,"received_at":1794494516293,"ts":"2026-11-12T09:41:55-05:00"},
  "1794494545": {"device":"esp32-s3-01","distance_cm":166.63,"epoch":1794494545,"received_at":1794494546165,"ts":"2026-11-12T09:42:25-05:00"},
  "1794494575": {"device":"esp32-s3-01","distance_cm":166.63,"epoch":1794494575,"received_at":1794494576169,"ts":"2026-11-12T09:42:55-05:00"},
  "1794494605": {"device":"esp32-s3-01","distance_cm":166.49,"epoch":1794494605,"received_at":1794494606166,"ts":"2026-11-12T09:43:25-05:00"}
}
```

Las reglas de Firebase aceptaron las escrituras sin cambios (UID autorizado, `received_at` = hora del servidor). El intervalo entre lecturas es exactamente de 30 s.

## 7. Notas de carga (placas ESP32-S3 con CH343)

- El puerto **COM** (chip CH343, VID `1A86:55D3`) usa UART0: compile con `CDCOnBoot=default` para ver el monitor serie por ese puerto. Con `CDCOnBoot=cdc` la salida va al conector USB nativo.
- Si la carga se queda en `Running stub flasher...`: desconecte y reconecte el USB, y cargue sin el *stub*:

```bash
esptool --chip esp32s3 --port COM7 --baud 115200 --no-stub write-flash -z 0x10000 build/esp32_distance_firebase.ino.bin
```
