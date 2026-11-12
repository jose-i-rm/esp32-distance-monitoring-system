/*
 * Panel de la cámara PTZ Tuya. Consume el backend FastAPI (/api/camera/*).
 * Independiente de app.js (Firebase). La clave de administración solo vive en sessionStorage.
 */
(() => {
  "use strict";

  const STORAGE_URL = "camera.apiUrl";
  const STORAGE_KEY = "camera.apiKey";
  const EVENT_LABELS = {
    humanoid_detection: "🧍 Detección humanoide",
    abnormal_sound: "🔊 Sonido anormal",
    motion_detection: "🏃 Movimiento",
    face_detection: "🙂 Rostro",
    alarm: "🚨 Alarma",
    disalarm: "✅ Alarma desactivada",
    online: "🟢 En línea",
    offline: "🔴 Fuera de línea",
    dp_report: "⚙ Cambio de parámetro",
  };

  const $ = (id) => document.getElementById(id);
  const cfg = window.APP_CONFIG || {};
  let timer = null;
  let snapshotUrl = null;

  const state = {
    url: localStorage.getItem(STORAGE_URL) || cfg.CAMERA_API_URL || "",
    key: sessionStorage.getItem(STORAGE_KEY) || "",
  };

  function setStatus(kind, text) {
    const el = $("camera-status");
    el.className = `status status-${kind}`;
    el.querySelector(".label").textContent = text;
  }

  async function api(path, options = {}) {
    if (!state.url || !state.key) throw new Error("Configure la URL del backend y la clave.");
    const response = await fetch(`${state.url.replace(/\/$/, "")}${path}`, {
      ...options,
      headers: { "X-API-Key": state.key, ...(options.body ? { "Content-Type": "application/json" } : {}) },
      cache: "no-store",
    });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { detail = (await response.json()).detail || detail; } catch { /* respuesta no JSON */ }
      const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      error.status = response.status;
      throw error;
    }
    return response;
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "medium" });
  }

  function renderEvents(items) {
    const body = $("camera-events-body");
    body.replaceChildren();
    if (!items.length) {
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 4;
      cell.className = "empty";
      cell.textContent = "Sin eventos";
      return;
    }
    for (const ev of items) {
      const row = body.insertRow();
      row.insertCell().textContent = formatDate(ev.event_time);
      const label = EVENT_LABELS[ev.event_type] || ev.event_type;
      row.insertCell().textContent = ev.event_type === "dp_report" ? `${label}: ${ev.code}` : label;
      row.insertCell().textContent = ev.tuya_cmd || ev.code;
      row.insertCell().textContent = ev.has_image ? "Sí" : "—";
      if (ev.event_type === "humanoid_detection") row.classList.add("tag-near");
    }
  }

  async function refresh() {
    try {
      const [status, events] = await Promise.all([
        api("/api/camera/status").then((r) => r.json()),
        api("/api/camera/events?limit=50").then((r) => r.json()),
      ]);
      setStatus(status.online ? "ok" : "error", status.online ? `${status.name} · en línea` : `${status.name} · fuera de línea`);
      renderEvents(events.items.filter((e) => e.event_type !== "dp_report").slice(0, 25));
    } catch (error) {
      setStatus(error.status === 401 ? "warn" : "error", error.status === 401 ? "Clave inválida" : "Error");
      notify(error.message, true);
    }
  }

  function notify(message, isError = false) {
    const toast = $("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle("error", isError);
    toast.hidden = false;
    clearTimeout(notify.t);
    notify.t = setTimeout(() => { toast.hidden = true; }, 5000);
  }

  async function ptz(direction) {
    try {
      const body = direction === "stop" ? { direction } : { direction, duration_ms: 600 };
      await api("/api/camera/ptz", { method: "POST", body: JSON.stringify(body) });
    } catch (error) {
      notify(`PTZ: ${error.message}`, true);
    }
  }

  async function snapshot() {
    const msg = $("camera-snapshot-msg");
    msg.textContent = "Solicitando imagen…";
    try {
      const response = await api("/api/camera/snapshot");
      const blob = await response.blob();
      if (snapshotUrl) URL.revokeObjectURL(snapshotUrl);
      snapshotUrl = URL.createObjectURL(blob);
      const img = $("camera-snapshot");
      img.src = snapshotUrl;
      img.hidden = false;
      const source = response.headers.get("X-Snapshot-Source") || "";
      const at = response.headers.get("X-Captured-At");
      msg.textContent = `Origen: ${source}${at ? ` · ${formatDate(at)}` : ""}`;
    } catch (error) {
      msg.textContent = error.message;
    }
  }

  async function sync() {
    try {
      const result = await (await api("/api/camera/events/sync", { method: "POST" })).json();
      notify(`Eventos nuevos: ${result.inserted}`);
      refresh();
    } catch (error) {
      notify(`Sincronización: ${error.message}`, true);
    }
  }

  function start() {
    clearInterval(timer);
    if (!state.url || !state.key) return;
    refresh();
    timer = setInterval(refresh, Math.max(15, cfg.CAMERA_REFRESH_SECONDS || 30) * 1000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("camera-api-url").value = state.url;
    $("camera-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const url = $("camera-api-url").value.trim();
      if (!/^https:\/\//.test(url) && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?/.test(url)) {
        notify("Use HTTPS (o localhost en desarrollo).", true);
        return;
      }
      state.url = url;
      state.key = $("camera-api-key").value;
      localStorage.setItem(STORAGE_URL, state.url);
      sessionStorage.setItem(STORAGE_KEY, state.key);
      $("camera-api-key").value = "";
      start();
    });
    $("camera-forget").addEventListener("click", () => {
      sessionStorage.removeItem(STORAGE_KEY);
      state.key = "";
      clearInterval(timer);
      setStatus("unknown", "Sin conectar");
    });
    document.querySelectorAll("[data-ptz]").forEach((btn) => btn.addEventListener("click", () => ptz(btn.dataset.ptz)));
    $("camera-snapshot-btn").addEventListener("click", snapshot);
    $("camera-sync-btn").addEventListener("click", sync);
    start();
  });
})();
