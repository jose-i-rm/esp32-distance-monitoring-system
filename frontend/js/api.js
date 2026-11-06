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

  // Alertas de cambio de distancia, de la más reciente a la más antigua.
  async function alerts(dbUrl, limit = 20) {
    const res = await get(dbUrl, "alerts", { orderBy: '"$key"', limitToLast: limit });
    const items = Object.entries((res.ok && res.body) || {})
      .map(([key, value]) => ({ ...value, epoch: Number(value.epoch ?? key) }))
      .sort((a, b) => b.epoch - a.epoch);
    return { ...res, items };
  }

  /*
   * Escucha una ruta en tiempo real con la API REST de streaming de Firebase (Server-Sent Events).
   * onChange recibe el valor completo y actualizado de la ruta.
   */
  function listen(dbUrl, path, onChange, onStatus) {
    const source = new EventSource(`${dbUrl.replace(/\/+$/, "")}/${path}.json`);
    let value = null;

    const setAt = (target, keys, data) => {
      if (!keys.length) return data;
      const root = target && typeof target === "object" ? { ...target } : {};
      let node = root;
      keys.slice(0, -1).forEach((k) => {
        node[k] = node[k] && typeof node[k] === "object" ? { ...node[k] } : {};
        node = node[k];
      });
      const last = keys[keys.length - 1];
      if (data === null) delete node[last]; else node[last] = data;
      return root;
    };

    const handle = (kind) => (event) => {
      const { path: p, data } = JSON.parse(event.data);
      const keys = p.split("/").filter(Boolean);
      if (kind === "put") {
        value = setAt(value, keys, data);
      } else {
        Object.entries(data || {}).forEach(([k, v]) => {
          value = setAt(value, [...keys, ...k.split("/").filter(Boolean)], v);
        });
      }
      onChange(value);
    };

    source.addEventListener("put", handle("put"));
    source.addEventListener("patch", handle("patch"));
    source.addEventListener("open", () => onStatus && onStatus(true));
    source.addEventListener("error", () => onStatus && onStatus(false));
    source.addEventListener("cancel", () => source.close());
    return source;
  }

  window.FirebaseClient = {
    normalize,
    stats: (dbUrl) => get(dbUrl, "stats"),
    recent: (dbUrl, limit = 50) => measurements(dbUrl, { limitToLast: limit }),
    alerts,
    listen,
    // Rango por epoch (segundos UTC). Sin límites devuelve todo el histórico.
    range: (dbUrl, startEpoch, endEpoch) => measurements(dbUrl, {
      startAt: startEpoch != null ? `"${startEpoch}"` : undefined,
      endAt: endEpoch != null ? `"${endEpoch}"` : undefined,
    }),
  };
})();
