# Dashboard (frontend)

Aplicación estática en **HTML5 + CSS3 + Vanilla JavaScript** con **Chart.js 4** (cargado por CDN). No requiere compilación ni frameworks.

## Estructura

```
frontend/
├── index.html          # Maquetación del dashboard
├── css/styles.css      # Tema oscuro, diseño responsive (CSS Grid)
├── js/config.js        # URL de la API e intervalos (regenerado en GitHub Pages)
├── js/api.js           # Cliente REST (fetch + timeout)
├── js/app.js           # Estado, renderizado y refresco periódico
└── assets/favicon.svg
```

## Funcionalidades

| Elemento | Fuente de datos | Detalle |
|----------|-----------------|---------|
| **Distancia actual** | Primer ítem de `GET /api/v1/measurements` | Valor en cm + barra proporcional al rango 0–400 cm. |
| **Última lectura** | `timestamp` de la medición más reciente | Fecha/hora local y tiempo relativo ("hace 12 s"). |
| **Estado del dispositivo** | Antigüedad de la última lectura | 🟢 En línea ≤ 45 s · 🟡 Retrasado ≤ 90 s · 🔴 Fuera de línea > 90 s. |
| **Estado de conexión** | `GET /health` | API conectada / degradada (BD caída) / sin conexión, con latencia. |
| **Estadísticas** | Lecturas cargadas | Mínimo, máximo, promedio y total de registros. |
| **Gráfico temporal** | Lecturas cargadas | Línea con Chart.js; 20, 50, 120 o 500 lecturas. |
| **Historial** | Lecturas cargadas | Tabla con exportación a CSV. |

Refresco automático cada 15 s (configurable). Los umbrales del estado del dispositivo se derivan de `DEVICE_INTERVAL_SECONDS` (30 s) y `DEVICE_OFFLINE_FACTOR` (3) en `js/config.js`.

## Configuración

`js/config.js`:

```js
window.APP_CONFIG = {
  API_BASE_URL: "http://localhost:8000",
  REFRESH_INTERVAL_SECONDS: 15,
  DEVICE_INTERVAL_SECONDS: 30,
  DEVICE_OFFLINE_FACTOR: 3,
  MAX_DISTANCE_CM: 400,
};
```

- En **GitHub Pages**, el workflow [`pages.yml`](../.github/workflows/pages.yml) reescribe `API_BASE_URL` con la variable de repositorio `API_BASE_URL`.
- Desde el botón **⚙ Configuración** el usuario puede cambiar la URL y el intervalo; se guarda en `localStorage` del navegador.

## Seguridad

- Todo el contenido dinámico se inserta con `textContent` (sin `innerHTML`), evitando XSS.
- El dashboard solo consume endpoints `GET` públicos; **nunca** debe contener la `DEVICE_API_KEY`.

## Compatibilidad

Chrome, Edge, Firefox y Safari en sus versiones actuales. Diseño adaptable desde 320 px de ancho.
