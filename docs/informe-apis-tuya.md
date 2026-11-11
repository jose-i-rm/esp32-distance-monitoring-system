# Informe de APIs Tuya Cloud — Cámara PTZ "Security Camera"

> Fecha de las pruebas: **2026-11-11** · Data center: **Western America** (`https://openapi.tuyaus.com`)
> Dispositivo: `Security Camera` · categoría **`sp`** (Smart Camera) · zona horaria `-05:00`
> Proyecto Tuya: *Custom Development* (cuenta gratuita / **Trial Edition**)
>
> Todas las filas marcadas como *verificado* se obtuvieron ejecutando
> [`backend/scripts/tuya_probe.py`](../backend/scripts/tuya_probe.py) contra la cuenta real.
> El script no imprime secretos ni tokens y se puede volver a ejecutar en cualquier momento
> para ver si cambió el estado de las suscripciones.

## 1. Resumen ejecutivo

| Capacidad | ¿Utilizable hoy? | API | Requisito para habilitarla |
|-----------|------------------|-----|----------------------------|
| Autenticación (token) | ✅ Sí | `GET /v1.0/token?grant_type=1` | — |
| Estado del dispositivo | ✅ Sí | `GET /v1.0/devices/{id}` · `/status` · `/specifications` · `/functions` | IoT Core |
| Historial de eventos | ✅ Sí (7 días) | `GET /v1.0/devices/{id}/logs` · `GET /v2.0/cloud/thing/{id}/report-logs` | IoT Core |
| **PTZ** (mover / detener / presets) | ✅ **Sí** | `POST /v1.0/devices/{id}/commands` (`ptz_control`, `ptz_stop`, `ipc_preset_action`) | IoT Core |
| Configuración (detección, visión nocturna, privacidad…) | ✅ Sí | `POST /v1.0/devices/{id}/commands` | IoT Core |
| **Vídeo en vivo** HLS/RTSP/FLV/RTMP | ❌ No (`28841105`) | `POST /v1.0/devices/{id}/stream/actions/allocate` | Autorizar *IoT Video Live Stream* **en el proyecto** |
| Vídeo en vivo WebRTC | ❌ No (`28841106`) | `GET /v1.0/devices/{id}/webrtc-configs` | Suscribir/autorizar la API WebRTC |
| **Snapshot bajo demanda** | ❌ No (`28841101`) | `POST /v1.0/cameras/{id}/actions/capture` | Servicio *Camera Open Capabilities* (orientado a cámaras profesionales) |
| Imagen de alarma (detección humanoide/sonido) | ⚠️ Referencia sí, descarga no (`28841106`) | `GET /v1.0/devices/{id}/movement-configs` | Suscribir la API de imágenes de alarma |
| Grabaciones en la nube | ❌ No | APIs de *Video Cloud Storage* | Plan de almacenamiento en la nube **de pago** activo en la cámara |

**Conclusión:** con la cuenta gratuita actual el backend puede **leer estado, leer y guardar eventos
(incluida la detección humanoide y el sonido anormal) y controlar el PTZ**. El vídeo en vivo y las
imágenes requieren autorizar servicios adicionales; el código ya está preparado y empezará a
funcionar sin cambios en cuanto Tuya devuelva `success: true`.

## 2. Autenticación y firma (verificado)

* Token "modo simple": `GET /v1.0/token?grant_type=1` → `access_token`, `refresh_token`, `expire_time` (7200 s), `uid`.
* Renovación: `GET /v1.0/token/{refresh_token}` (el *refresh token* es de un solo uso).
* Firma **HMAC-SHA256** en mayúsculas ([doc oficial](https://developer.tuya.com/en/docs/iot/new-singnature?id=Kbw0q34cs2e5g)):

```text
stringToSign = METHOD + "\n" + SHA256(body) + "\n" + "" + "\n" + path?query_ordenada
token API    : sign = HMAC(client_id + t + nonce + stringToSign, secret)
negocio      : sign = HMAC(client_id + access_token + t + nonce + stringToSign, secret)
cabeceras    : client_id, sign, t (ms), nonce, sign_method=HMAC-SHA256, access_token
```

Implementado en [`backend/app/integrations/tuya/client.py`](../backend/app/integrations/tuya/client.py)
(caché del token en memoria, renovación 60 s antes de expirar y reintento automático ante los
códigos `1010/1011/1012`).

## 3. Estado y parámetros de la cámara (verificado)

`GET /v1.0/devices/{id}/functions` devolvió los DPs **escribibles**:

| Código | Tipo | Valores | Uso |
|--------|------|---------|-----|
| `ptz_control` | enum | `"0"`…`"7"` | 0↑ 1↗ 2→ 3↘ 4↓ 5↙ 6← 7↖ |
| `ptz_stop` | bool | — | Detener el giro |
| `ipc_preset_action` | enum | `"1"`…`"6"` | Ir a posición predefinida |
| `motion_switch` | bool | — | Detección de movimiento |
| `motion_sensitivity` | enum | 0 baja · 1 media · 2 alta | |
| `motion_interval` | enum | 1 · 3 · 5 (min) | Intervalo entre alarmas |
| `motion_tracking` | bool | — | Seguimiento automático |
| `motion_area_switch` / `motion_area` | bool / string(255) | JSON de región | Zona de detección |
| `humanoid_filter` | bool | — | Solo alarmas de personas |
| `motion_record` / `record_switch` / `record_mode` | bool / bool / enum(1 evento, 2 continuo) | | Grabación en SD |
| `decibel_switch` / `decibel_sensitivity` | bool / enum(0,1) | | Alarma de sonido anormal |
| `basic_nightvision` | enum | 0 auto · 1 off · 2 on | |
| `basic_private` | bool | — | Modo privacidad (lente oculto) |
| `basic_flip`, `basic_indicator`, `ipc_mute_record`, `device_restart`, `sd_format`, `record_switch1` | bool | | |

DPs **solo de lectura** adicionales: `sd_storge`, `sd_status`, `sd_format_state`,
`movement_detect_pic`, `alarm_message`, `decibel_upload`.

## 4. Eventos (verificado)

* `GET /v1.0/devices/{id}/logs?type=1,2,7&start_time&end_time&size&start_row_key` — paginado con `next_row_key`.
  * `event_id`: 1 online · 2 offline · 3 activación · 4 reset · 5 comando · 6 firmware · **7 reporte de DP** · 9 reinicio.
* `GET /v2.0/cloud/thing/{id}/report-logs?codes=…` — también disponible, pero el `alarm_message`
  llega **cifrado** (`keyId: default`), por lo que el backend usa `/v1.0/.../logs`, donde llega en claro.
* En 24 h de prueba se obtuvieron **254 eventos**: 89 de detección humanoide, 25 de sonido anormal,
  2 de conexión y el resto cambios de parámetros (incluidos los movimientos PTZ).

Formato del `alarm_message` (base64 → JSON) en `/v1.0/devices/{id}/logs`:

```jsonc
{
  "v": "5.0",
  "cmd": "ipc_human",                 // ipc_human = humanoid detection · ipc_bang = abnormal sound
  "type": "image",
  "with": "resources",
  "files": [["<bucket>", "/<ruta>/detect/<epoch>.jpeg", "<clave AES 16 car.>", "<expira epoch>"]]
}
```

| `cmd` | Evento observado en la App | `event_type` normalizado |
|-------|----------------------------|--------------------------|
| `ipc_human` | humanoid detection | `humanoid_detection` |
| `ipc_bang` | abnormal sound alarm | `abnormal_sound` |
| `ipc_motion` / `ipc_move` | motion | `motion_detection` |
| texto `alarm` / `disalarm` | alarm / disalarm | `alarm` / `disalarm` |
| otros (`ipc_face`, `ipc_baby_cry`, `ipc_car`, …) | | ver `ALARM_CMD_TYPES` |

La **clave AES** de la imagen se guarda en la columna `image_key` pero **nunca** se devuelve por la API.
Las imágenes expiran a los ~30 días (`image_expires_at`).

## 5. PTZ (verificado con la cámara real)

```http
POST /v1.0/devices/{id}/commands
{"commands":[{"code":"ptz_control","value":"2"}]}   → success: true (gira a la derecha)
{"commands":[{"code":"ptz_stop","value":true}]}     → success: true
```

* El movimiento es **continuo** hasta recibir `ptz_stop`; por eso el backend envía siempre
  `ptz_stop` después de `duration_ms` (máx. 3000 ms), incluso si ocurre un error.
* `ipc_preset_action` permite ir a 6 posiciones guardadas desde la App.
* `POST /v1.0/cameras/{id}/configs/ptz` (API de *Camera Open Capabilities*) **no** es necesaria.

## 6. Vídeo

| API | Resultado | Notas |
|-----|-----------|-------|
| `POST /v1.0/devices/{id}/stream/actions/allocate` `{"type":"hls"|"rtsp"|"flv"|"rtmp"}` | ❌ `28841105` *project is not authorized* | El servicio está suscrito en la cuenta pero **no autorizado para el proyecto**. |
| `POST /v1.0/users/{uid}/devices/{id}/stream/actions/allocate` | ❌ `28841105` | Variante por usuario. |
| `GET /v1.0/devices/{id}/webrtc-configs` | ❌ `28841106` *API is not subscribed* | Para reproducción WebRTC en navegador. |

Cuando se habilite: la URL devuelta es **temporal** (firmada, válida pocos minutos según reportes
de la comunidad; Tuya no publica un valor fijo) y no debe guardarse ni compartirse. HLS se puede
reproducir en el navegador con `hls.js`; RTSP sirve para OpenCV/ffmpeg (capturas e IA).
Documentación: <https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybxmi136f>

**Cómo habilitarlo:** *platform.tuya.com → Cloud → Development → (proyecto) → Service API →
Go to Authorize →* seleccionar **IoT Video Live Stream** (y *Smart Camera / IPC* si aparece) → OK.
Luego volver a ejecutar `python scripts/tuya_probe.py`.

## 7. Snapshot

No hay un "GET imagen actual" síncrono para cámaras de consumo (`sp`). Opciones evaluadas:

| Estrategia | Estado | Implementación |
|------------|--------|----------------|
| Fotograma del stream RTSP/HLS con **ffmpeg** | Bloqueada por §6 | `CameraService.snapshot()` paso 1 (requiere `ffmpeg` en el servidor) |
| Última **imagen de alarma** (`movement-configs` → descarga → AES-128-CBC) | Bloqueada (`28841106`) | `CameraService.snapshot()` paso 2 + `decrypt_alarm_image()` |
| `POST /v1.0/cameras/{id}/actions/capture` (asíncrona, llega por Message Service) | Bloqueada (`28841101`) | `TuyaClient.trigger_capture()` — línea profesional, no garantizada en `sp` |

`GET /api/camera/snapshot` prueba las estrategias en orden y, si ninguna está disponible, responde
**503 con el motivo exacto** de cada una.

Formato de la imagen cifrada (SDK oficial: AES/CBC/PKCS5Padding,
<https://developer.tuya.com/en/docs/app-development/encryptimage?id=Kceuhc84acev1>): 4 bytes de
versión + 16 bytes IV + 44 bytes reservados + datos cifrados; clave = cadena de 16 caracteres del mensaje.

## 8. Almacenamiento de vídeo en la nube (Video Cloud Storage)

Las APIs de listado/reproducción de grabaciones requieren que **la cámara tenga un plan de
almacenamiento en la nube de pago activo** (se compra desde la App Smart Life/Tuya). Sin plan no hay
grabaciones que consultar. La cámara tiene `sd_status = 5` (sin tarjeta SD), por lo que tampoco hay
grabación local. **No utilizable** con la cuenta actual.

## 9. Limitaciones de la cuenta gratuita (Trial Edition)

Fuente: <https://developer.tuya.com/en/docs/iot/membership-service?id=k9m8k45jwvg9j>

| Recurso | Trial Edition |
|---------|---------------|
| Llamadas API / mes | **26 000** |
| Mensajes (Message Service) / mes | 68 000 |
| Data centers | 1 |
| Dispositivos (solo monitoreo) | 50 |
| Dispositivos controlables | 10 |
| Retención de logs de dispositivo | **7 días** |
| Uso comercial | **Prohibido** (solo desarrollo personal / depuración) |
| Vigencia | Periodo de prueba renovable desde la consola (se debe extender periódicamente) |
| Live Stream / Cloud Storage | Servicios de valor añadido con facturación propia, no incluidos en la cuota anterior |

**Presupuesto de llamadas del backend** (26 000/mes ≈ 866/día):

| Uso | Llamadas/día aprox. |
|-----|---------------------|
| Sondeo de eventos cada 300 s (`TUYA_POLL_INTERVAL_SECONDS=300`, 1 página) | 288 |
| Sondeo de eventos cada 120 s | 720 (⚠️ sumado al dashboard supera la cuota) |
| Dashboard abierto 1 h con refresco de 30 s (`/status` = 2 llamadas) | 240 |

Por eso el sondeo está **desactivado por defecto** y su mínimo es 30 s. Para uso continuo se
recomienda 300 s o más (≈ 288/día), o migrar a **Message Service (Pulsar)** para recibir eventos por
*push* sin consumir llamadas.

## 10. SDK

| Paquete | Estado (GitHub) | Decisión |
|---------|-----------------|----------|
| [`tuya-iot-python-sdk`](https://github.com/tuya/tuya-iot-python-sdk) | No archivado pero **inactivo**: última versión 0.6.6 (2021), último push 2022 | Referencia del algoritmo de firma |
| [`tuya-connector-python`](https://github.com/tuya/tuya-connector-python) | Más reciente (push 2024), incluye cliente Pulsar | Opción para Message Service en el futuro |
| Cliente propio `httpx` (este repo) | — | **Usado**: misma firma, sin dependencias extra, sin registrar peticiones en DEBUG, probado con mocks |

## 11. Tabla de códigos de error observados

| Código | Mensaje | Significado |
|--------|---------|-------------|
| `28841105` | No permissions. This project is not authorized to call this API. | Servicio suscrito, falta autorizarlo en el proyecto |
| `28841106` / `28841101` | No permissions. This API is not subscribed. | Hay que suscribir el servicio/API |
| `1108` | uri path invalid | Ruta inexistente |
| `1010` | token invalid | Token expirado (el cliente lo renueva solo) |
