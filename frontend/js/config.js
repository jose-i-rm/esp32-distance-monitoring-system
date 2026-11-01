/*
 * Configuración del dashboard.
 * En GitHub Pages este archivo se regenera en el workflow usando la variable
 * de repositorio API_BASE_URL (Settings > Secrets and variables > Actions > Variables).
 * El usuario también puede cambiar la URL desde el panel "Configuración" (se guarda en localStorage).
 */
window.APP_CONFIG = {
  API_BASE_URL: "http://localhost:8000",
  REFRESH_INTERVAL_SECONDS: 15,
  // Intervalo de envío del firmware (30 s). Si no llegan datos en 3 intervalos el dispositivo se marca offline.
  DEVICE_INTERVAL_SECONDS: 30,
  DEVICE_OFFLINE_FACTOR: 3,
  MAX_DISTANCE_CM: 400,
};
