# Despliegue del frontend en GitHub Pages

El workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) publica la carpeta `frontend/` en cada push a `main` que modifique el frontend (o manualmente).

🔴 URL en vivo: **https://jose-i-rm.github.io/esp32-distance-monitoring-system/**

## Configuración (una sola vez)

1. **Settings → Pages → Build and deployment → Source:** `GitHub Actions`.
2. (Opcional) **Settings → Secrets and variables → Actions → Variables → New repository variable:**
   - Nombre: `FIREBASE_DB_URL`
   - Valor: URL de Realtime Database (sin `/` final). Si no existe, se usa la de `frontend/js/config.js`.
3. **Actions → Deploy Frontend to GitHub Pages → Run workflow**.

## Origen de los datos

El dashboard lee directamente de Firebase Realtime Database por HTTPS. Firebase permite peticiones CORS desde cualquier origen y las reglas solo permiten **lectura** pública, por lo que no hace falta configurar CORS ni backend adicional. Ver [../docs/firebase.md](../docs/firebase.md).
