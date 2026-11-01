/* Cliente mínimo para la API REST del backend FastAPI. */
(function () {
  "use strict";

  const TIMEOUT_MS = 20000;

  async function request(baseUrl, path, params) {
    const url = new URL(path, baseUrl.endsWith("/") ? baseUrl : baseUrl + "/");
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
      const body = response.status === 204 ? null : await response.json().catch(() => null);
      return { ok: response.ok, status: response.status, body, latencyMs };
    } finally {
      clearTimeout(timer);
    }
  }

  window.ApiClient = {
    health: (baseUrl) => request(baseUrl, "health"),
    latest: (baseUrl) => request(baseUrl, "api/v1/measurements/latest"),
    list: (baseUrl, limit = 50, offset = 0) => request(baseUrl, "api/v1/measurements", { limit, offset }),
  };
})();
