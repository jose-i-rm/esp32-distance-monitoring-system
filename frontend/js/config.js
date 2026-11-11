/*
 * Configuración del dashboard.
 * Los datos se leen de Firebase Realtime Database (lectura pública, escritura solo del ESP32).
 * El usuario puede cambiar la URL desde el panel "Configuración" (se guarda en localStorage).
 */
window.APP_CONFIG = {
  FIREBASE_DB_URL: "https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com",
  REFRESH_INTERVAL_SECONDS: 15,
  // Intervalo de envío del firmware (30 s). Si no llegan datos en 3 intervalos el dispositivo se marca offline.
  DEVICE_INTERVAL_SECONDS: 30,
  DEVICE_OFFLINE_FACTOR: 3,
  MAX_DISTANCE_CM: 400,
  // Debe coincidir con UMBRAL_CAMBIO_CM del firmware (solo se usa para mostrar la regla).
  ALERT_THRESHOLD_CM: 10,
  ALERTS_LIMIT: 20,
  // Backend FastAPI para la cámara PTZ Tuya (vacío = el usuario lo indica en el panel).
  // La clave de administración NUNCA se configura aquí: se introduce en el panel.
  CAMERA_API_URL: "",
  CAMERA_REFRESH_SECONDS: 30,
};
