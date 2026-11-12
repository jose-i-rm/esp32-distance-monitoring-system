# Credenciales y configuración

Estado de cuentas, secretos y variables del sistema. **Ningún secreto se versiona** en el repositorio.

## 1. Firebase (backend)

| # | Tarea | Estado |
|---|-------|--------|
| 1 | Proyecto `esp32-distance-jirm-450f1` (plan Spark gratuito) | ☑ Hecho |
| 2 | Realtime Database `esp32-distance-jirm-450f1-default-rtdb` (us-central1) | ☑ Hecho |
| 3 | Authentication: proveedor correo/contraseña habilitado, registro público deshabilitado | ☑ Hecho |
| 4 | Cuenta del dispositivo `esp32-cam-01@esp32-distance.iot` | ☑ Hecho |
| 5 | Reglas de seguridad desplegadas (`firebase deploy --only database`) | ☑ Hecho |
| 6 | App web registrada (API key web) | ☑ Hecho |

Detalle: [firebase.md](./firebase.md).

## 2. GitHub Pages (frontend)

| # | Tarea | Estado |
|---|-------|--------|
| 1 | GitHub Pages con origen **GitHub Actions** | ☑ Hecho |
| 2 | URL de Firebase en `frontend/js/config.js` (opcional: variable de repositorio `FIREBASE_DB_URL`) | ☑ Hecho |

Sitio: https://jose-i-rm.github.io/esp32-distance-monitoring-system/

## 3. Firmware (ESP32-S3 N16R8)

Los valores reales se guardan en `secrets.h` junto al sketch (excluido de Git):

| Constante | Origen |
|-----------|--------|
| `WIFI_SSID`, `WIFI_PASSWORD` | Red WiFi 2.4 GHz |
| `FIREBASE_API_KEY` | Consola Firebase → Configuración del proyecto → General |
| `FIREBASE_DB_URL` | `https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com` |
| `DEVICE_EMAIL`, `DEVICE_PASSWORD` | Cuenta del dispositivo (Authentication → Usuarios) |

Si se pierde la contraseña del dispositivo, restablézcala desde la consola (ver [firebase.md](./firebase.md#rotar-la-contraseña-del-dispositivo)).

## 4. Backend alternativo (opcional, no usado)

El backend FastAPI + PostgreSQL (`backend/`, `render.yaml`, `deployment/`) se conserva como alternativa. Si se quisiera usar: cuenta de Render, Blueprint `render.yaml`, `DEVICE_API_KEY` y `CORS_ORIGINS`. Ver [../deployment/README.md](../deployment/README.md).

## 5. Futuras integraciones

| Servicio | Credencial |
|----------|-----------|
| Hugging Face | `HF_API_TOKEN` (*Settings* → *Access Tokens*, rol *read*). |
| Broker MQTT | Host, puerto 8883, usuario y contraseña por dispositivo. |
| Almacenamiento de imágenes | Firebase Storage u otro bucket. |
