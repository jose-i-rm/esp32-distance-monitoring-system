# Despliegue del frontend en GitHub Pages

El workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) publica la carpeta `frontend/` en cada push a `main` que modifique el frontend (o manualmente).

## Configuración (una sola vez)

1. **Settings → Pages → Build and deployment → Source:** `GitHub Actions`.
2. **Settings → Secrets and variables → Actions → Variables → New repository variable:**
   - Nombre: `API_BASE_URL`
   - Valor: `https://<servicio>.onrender.com` (sin `/` final)
3. **Actions → Deploy Frontend to GitHub Pages → Run workflow**.

URL resultante: **https://jose-i-rm.github.io/esp32-distance-monitoring-system/**

## ¿Cómo se inyecta la URL de la API?

Durante el workflow, si existe la variable `API_BASE_URL`, se reemplaza el valor por defecto de `frontend/js/config.js`:

```bash
sed -i "s|API_BASE_URL: \".*\"|API_BASE_URL: \"${API_BASE_URL}\"|" frontend/js/config.js
```

Así el repositorio conserva `http://localhost:8000` para desarrollo y la versión publicada apunta a producción.

## Requisitos de CORS

El backend debe incluir el origen de Pages en `CORS_ORIGINS`:

```
CORS_ORIGINS=https://jose-i-rm.github.io
```

> El origen no incluye la ruta del repositorio (`/esp32-distance-monitoring-system`).
