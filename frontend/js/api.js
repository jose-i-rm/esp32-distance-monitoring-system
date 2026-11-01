/* Cliente mínimo para la API REST de Firebase Realtime Database (solo lectura). */
(function () {
  "use strict";

  const TIMEOUT_MS = 20000;

  async function get(dbUrl, path, params) {
    const url = new URL(`${dbUrl.replace(/\/+$/, "")}/${path}.json`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) url.searchParams.set(key, value);
      });
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const started = performance.now();

    try {
      const response = await fetch(url, { signal: controller.signal, headers: { Accept: "application/json" } });
      const latencyMs = Math.round(performance.now() - started);
      const body = await response.json().catch(() => null);
      return { ok: response.ok, status: response.status, body, latencyMs };
    } finally {
      clearTimeout(timer);
    }
  }

  // Registro de Firebase -> formato usado por el dashboard.
  function normalize(key, value) {
    return {
      id: key,
      epoch: Number(value.epoch ?? key),
      timestamp: value.ts,
      distance_cm: Number(value.distance_cm),
      created_at: value.received_at ? new Date(value.received_at).toISOString() : null,
      device: value.device || "",
    };
  }

  // Lista ordenada de la más reciente a la más antigua.
  function toItems(body) {
    return Object.entries(body || {})
      .map(([key, value]) => normalize(key, value))
      .sort((a, b) => b.epoch - a.epoch);
  }

  async function measurements(dbUrl, params) {
    const res = await get(dbUrl, "measurements", { orderBy: '"$key"', ...params });
    return { ...res, items: res.ok ? toItems(res.body) : [] };
  }

  window.FirebaseClient = {
    normalize,
    stats: (dbUrl) => get(dbUrl, "stats"),
    recent: (dbUrl, limit = 50) => measurements(dbUrl, { limitToLast: limit }),
    // Rango por epoch (segundos UTC). Sin límites devuelve todo el histórico.
    range: (dbUrl, startEpoch, endEpoch) => measurements(dbUrl, {
      startAt: startEpoch != null ? `"${startEpoch}"` : undefined,
      endAt: endEpoch != null ? `"${endEpoch}"` : undefined,
    }),
  };
})();
