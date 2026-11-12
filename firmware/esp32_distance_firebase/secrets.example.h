// Copie este archivo como "secrets.h" en la misma carpeta del sketch y complete los valores.
// secrets.h está excluido de Git (.gitignore).
#pragma once

#define WIFI_SSID        "<SSID_WIFI_2.4GHz>"
#define WIFI_PASSWORD    "<CLAVE_WIFI>"

// Firebase: Configuración del proyecto -> General -> "Clave de API web"
#define FIREBASE_API_KEY "<FIREBASE_WEB_API_KEY>"
#define FIREBASE_DB_URL  "https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com"

// Cuenta del dispositivo en Firebase Authentication (correo/contraseña).
// Se reutiliza la cuenta existente: las reglas solo autorizan su UID (jz0Com63Fkam7s5IuOkolcWOdAL2).
#define DEVICE_EMAIL     "esp32-cam-01@esp32-distance.iot"
#define DEVICE_PASSWORD  "<CLAVE_DEL_DISPOSITIVO>"
// Valor del campo "device" de cada registro (texto <= 40 caracteres según las reglas).
#define DEVICE_ID        "esp32-s3-01"
