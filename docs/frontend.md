# Dashboard (frontend)

Aplicación estática en **HTML5 + CSS3 + Vanilla JavaScript**, con **Chart.js 4** para el gráfico y **SheetJS** para generar Excel (ambos cargados por CDN). No requiere compilación. Lee los datos directamente de **Firebase Realtime Database** por su API REST (lectura pública).

🔴 En vivo: https://jose-i-rm.github.io/esp32-distance-monitoring-system/

## Estructura

```
frontend/
├── index.html          # Maquetación del dashboard
├── css/styles.css      # Tema oscuro, diseño responsive (CSS Grid)
├── js/config.js        # URL de Firebase e intervalos
├── js/api.js           # Cliente REST de Firebase (fetch + timeout)
├── js/app.js           # Estado, renderizado, refresco periódico y exportación a Excel
└── assets/favicon.svg
```

## Funcionalidades

| Elemento | Fuente de datos | Detalle |
|----------|-----------------|---------|
| **Distancia actual** | `/stats/latest` | Valor en cm + barra proporcional al rango 0–400 cm. |
| **Última lectura** | `ts` de la última medición | Fecha/hora y tiempo relativo ("hace 12 s"). |
| **Estado del dispositivo** | Antigüedad de la última lectura | 🟢 En línea ≤ 45 s · 🟡 Retrasado ≤ 90 s · 🔴 Fuera de línea > 90 s. |
| **Estado de conexión** | `GET /stats.json` | Firebase conectado / con errores / sin conexión, con latencia. |
| **Estadísticas** | Lecturas cargadas + `/stats/count` | Mínimo, máximo, promedio y total de registros. |
| **Gráfico temporal** | `/measurements` (`limitToLast`) | Línea con Chart.js; 20, 50, 120 o 500 lecturas. |
| **Historial** | Lecturas cargadas | Tabla con hora de lectura y hora de recepción en Firebase. |
| **Descargar Excel** | `/measurements` (rango por `startAt`/`endAt`) | `.xlsx` con hojas *Lecturas* y *Resumen*. |

Refresco automático cada 15 s (configurable). Los umbrales del estado del dispositivo se derivan de `DEVICE_INTERVAL_SECONDS` (30 s) y `DEVICE_OFFLINE_FACTOR` (3) en `js/config.js`.

## Exportación a Excel

- Campos **Desde/Hasta** opcionales (día completo, hora local del navegador). Vacíos = histórico completo.
- Hoja **Lecturas**: N°, fecha y hora de la lectura, distancia (cm, numérica), hora de recepción en Firebase, dispositivo y epoch UTC. Incluye autofiltro.
- Hoja **Resumen**: rango, cantidad de registros, mínimo, máximo y promedio.
- Nombre del archivo: `lecturas_distancia_<desde>_a_<hasta>.xlsx` o `lecturas_distancia_completo.xlsx`.

## Configuración

`js/config.js`:

```js
window.APP_CONFIG = {
  FIREBASE_DB_URL: "https://esp32-distance-jirm-450f1-default-rtdb.firebaseio.com",
  REFRESH_INTERVAL_SECONDS: 15,
  DEVICE_INTERVAL_SECONDS: 30,
  DEVICE_OFFLINE_FACTOR: 3,
  MAX_DISTANCE_CM: 400,
};
```

- En **GitHub Pages**, el workflow [`pages.yml`](../.github/workflows/pages.yml) puede reemplazar `FIREBASE_DB_URL` con la variable de repositorio opcional `FIREBASE_DB_URL`.
- Desde **⚙ Configuración** el usuario puede cambiar la URL y el intervalo; se guarda en `localStorage`.

## Seguridad

- Todo el contenido dinámico se inserta con `textContent` (sin `innerHTML`), evitando XSS.
- El dashboard solo **lee**; las reglas de Firebase impiden que el navegador escriba o borre datos. Nunca incluya la contraseña del dispositivo en el frontend.

## Compatibilidad

Chrome, Edge, Firefox y Safari en sus versiones actuales. Diseño adaptable desde 320 px de ancho.
