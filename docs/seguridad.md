# Seguridad del proyecto

Medidas aplicadas en la integración de la cámara PTZ Tuya y recomendaciones operativas.

## 1. Gestión de secretos

| Secreto | Dónde vive | Nunca en |
|---------|-----------|----------|
| `TUYA_ACCESS_SECRET`, `TUYA_ACCESS_ID` | `backend/.env` local (en `.gitignore`) o gestor de secretos del proveedor (Render `sync: false`, GitHub Actions *secrets*) | Código, README, commits, issues, capturas |
| `ADMIN_API_KEY` | Igual que el anterior; en el navegador solo en `sessionStorage` | `frontend/js/config.js`, URLs |
| `DEVICE_API_KEY` | `.env` del backend y `secrets.h` del firmware (ignorado) | Repositorio |
| `access_token` de Tuya | Solo en memoria del proceso | Logs, base de datos |
| Clave AES de imágenes de alarma | Columna `camera_events.image_key` | Respuestas de la API, logs |

* `.env.example` contiene **solo marcadores** (`<tu_access_secret>`), nunca valores reales.
* `Settings.tuya_access_secret` es `SecretStr`: no aparece en `repr()`, logs ni trazas.
* `TuyaClient.__repr__` enmascara el Access ID y nunca incluye el secreto; los errores solo contienen código y mensaje de Tuya.
* `scripts/tuya_probe.py` no imprime tokens, trunca las URLs de vídeo y omite los valores de `alarm_message`.

### Si un secreto se expone

1. **Rotarlo de inmediato**: *platform.tuya.com → Cloud → (proyecto) → Overview → Access Secret → Reset*.
2. Actualizar `backend/.env` y el gestor de secretos del despliegue.
3. Si llegó a un commit: rotar **y** purgar el historial (`git filter-repo`) — rotar es obligatorio porque el historial puede estar clonado.
4. Revisar *Cloud → Operation logs* por llamadas no reconocidas.

## 2. Controles en la API

| Control | Implementación |
|---------|----------------|
| Autenticación de cámara | `X-API-Key` = `ADMIN_API_KEY`, comparación en tiempo constante (`secrets.compare_digest`) |
| *Fail-closed* | Sin `ADMIN_API_KEY` los endpoints `/api/camera/*` responden 503 (no quedan abiertos por olvido) |
| Separación de privilegios | La clave del ESP32 (`DEVICE_API_KEY`) **no** sirve para la cámara |
| Validación | Pydantic: dirección PTZ en lista cerrada, `duration_ms ≤ 3000`, preset 1–6, `type` de stream por regex, límites de paginación |
| Seguridad física PTZ | Siempre se envía `ptz_stop` (bloque `finally`); límite de frecuencia (429 + `Retry-After`) |
| Minimización de datos | `/status` oculta `alarm_message`; los eventos no exponen `image_key` ni el payload original |
| Cabeceras HTTP | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` en `/api/camera/*` |
| CORS | Lista explícita de orígenes (`CORS_ORIGINS`), sin credenciales |
| Transporte | `TUYA_ENDPOINT` debe ser HTTPS (validado); el dashboard solo acepta backends HTTPS (o localhost) |
| URLs de vídeo | Temporales y firmadas por Tuya; no se guardan en BD |
| Cuota | Sondeo desactivado por defecto y con mínimo de 30 s para no agotar las 26 000 llamadas/mes |

## 3. Frontend

* La clave se pide en el panel y se guarda en `sessionStorage` (se borra al cerrar la pestaña); botón *Olvidar clave*.
* Todo el contenido proveniente de la API se inserta con `textContent` (sin `innerHTML`) → sin XSS.
* Las imágenes se cargan con `fetch` + `URL.createObjectURL` para no poner la clave en la URL.

## 4. Recomendaciones operativas

* Mantener el repositorio con *Secret scanning* y *Push protection* activados (GitHub → Settings → Code security).
* Activar **Dependabot** para `backend/requirements*.txt`.
* Usar un proyecto Tuya exclusivo para este backend y autorizar solo los servicios necesarios.
* Ejecutar el backend detrás de HTTPS (Render/Railway/Fly lo proveen) y no exponer `/docs` públicamente en producción si no es necesario.
* Revisar periódicamente el consumo de la cuota en *Cloud → Cloud Services → IoT Core*.
* La cámara graba espacios privados: limitar quién conoce `ADMIN_API_KEY` y rotarla si cambia el equipo.
