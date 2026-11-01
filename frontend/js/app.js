/* Lógica del dashboard: estado, renderizado y actualización periódica. */
(function () {
  "use strict";

  const STORAGE_KEYS = { apiUrl: "esp32dms.apiUrl", refresh: "esp32dms.refresh", limit: "esp32dms.limit" };
  const defaults = window.APP_CONFIG;

  const state = {
    apiUrl: localStorage.getItem(STORAGE_KEYS.apiUrl) || defaults.API_BASE_URL,
    refreshSeconds: Number(localStorage.getItem(STORAGE_KEYS.refresh)) || defaults.REFRESH_INTERVAL_SECONDS,
    limit: Number(localStorage.getItem(STORAGE_KEYS.limit)) || 50,
    measurements: [],
    latest: null,
    timer: null,
    chart: null,
    loading: false,
  };

  const $ = (id) => document.getElementById(id);
  const el = {
    connectionBadge: $("connection-badge"),
    currentDistance: $("current-distance"),
    gauge: $("distance-gauge"),
    lastTime: $("last-reading-time"),
    lastRelative: $("last-reading-relative"),
    deviceStatus: $("device-status"),
    deviceDetail: $("device-status-detail"),
    apiStatus: $("api-status"),
    apiDetail: $("api-status-detail"),
    statMin: $("stat-min"),
    statMax: $("stat-max"),
    statAvg: $("stat-avg"),
    statTotal: $("stat-total"),
    historyBody: $("history-body"),
    limitSelect: $("limit-select"),
    refreshBtn: $("refresh-btn"),
    exportBtn: $("export-btn"),
    settingsToggle: $("settings-toggle"),
    settingsPanel: $("settings-panel"),
    settingsForm: $("settings-form"),
    settingsReset: $("settings-reset"),
    apiUrlInput: $("api-url-input"),
    refreshInput: $("refresh-input"),
    toast: $("toast"),
  };

  const dateFmt = new Intl.DateTimeFormat("es-CO", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
  const timeFmt = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

  const formatDate = (iso) => dateFmt.format(new Date(iso));
  const formatCm = (value) => Number(value).toFixed(2);

  function relativeTime(iso) {
    const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (seconds < 60) return `hace ${seconds} s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `hace ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `hace ${hours} h`;
    return `hace ${Math.floor(hours / 24)} d`;
  }

  function setIndicator(node, level, label) {
    node.classList.remove("status-ok", "status-warn", "status-error", "status-unknown",
      "badge-ok", "badge-warn", "badge-error", "badge-unknown");
    const prefix = node.classList.contains("badge") ? "badge" : "status";
    node.classList.add(`${prefix}-${level}`);
    node.querySelector(".label").textContent = label;
  }

  function showToast(message, isError = false) {
    el.toast.textContent = message;
    el.toast.classList.toggle("error", isError);
    el.toast.hidden = false;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => { el.toast.hidden = true; }, 4000);
  }

  /* ---------- Renderizado ---------- */

  function renderLatest() {
    const latest = state.latest;
    if (!latest) {
      el.currentDistance.textContent = "--";
      el.gauge.style.width = "0";
      el.lastTime.textContent = "--";
      el.lastRelative.textContent = "Sin datos";
      return;
    }
    el.currentDistance.textContent = formatCm(latest.distance_cm);
    const pct = Math.min(100, (latest.distance_cm / defaults.MAX_DISTANCE_CM) * 100);
    el.gauge.style.width = `${pct}%`;
    el.lastTime.textContent = formatDate(latest.timestamp);
    el.lastRelative.textContent = relativeTime(latest.timestamp);
  }

  function renderDeviceStatus() {
    if (!state.latest) {
      setIndicator(el.deviceStatus, "unknown", "Sin lecturas");
      el.deviceDetail.textContent = "Aún no se han recibido datos del dispositivo";
      return;
    }
    const ageSeconds = (Date.now() - new Date(state.latest.timestamp).getTime()) / 1000;
    const interval = defaults.DEVICE_INTERVAL_SECONDS;
    const offlineAfter = interval * defaults.DEVICE_OFFLINE_FACTOR;

    if (ageSeconds <= interval * 1.5) {
      setIndicator(el.deviceStatus, "ok", "En línea");
      el.deviceDetail.textContent = `Reportando cada ${interval} s`;
    } else if (ageSeconds <= offlineAfter) {
      setIndicator(el.deviceStatus, "warn", "Retrasado");
      el.deviceDetail.textContent = `Última lectura ${relativeTime(state.latest.timestamp)}`;
    } else {
      setIndicator(el.deviceStatus, "error", "Fuera de línea");
      el.deviceDetail.textContent = `Sin datos desde ${relativeTime(state.latest.timestamp)}`;
    }
  }

  function renderStats(total) {
    const values = state.measurements.map((m) => m.distance_cm);
    if (!values.length) {
      [el.statMin, el.statMax, el.statAvg].forEach((n) => { n.textContent = "--"; });
      el.statTotal.textContent = total ?? "--";
      return;
    }
    const sum = values.reduce((a, b) => a + b, 0);
    el.statMin.textContent = `${formatCm(Math.min(...values))} cm`;
    el.statMax.textContent = `${formatCm(Math.max(...values))} cm`;
    el.statAvg.textContent = `${formatCm(sum / values.length)} cm`;
    el.statTotal.textContent = total;
  }

  function renderHistory() {
    const body = el.historyBody;
    body.replaceChildren();
    if (!state.measurements.length) {
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 4;
      cell.className = "empty";
      cell.textContent = "Sin datos";
      return;
    }
    const fragment = document.createDocumentFragment();
    state.measurements.forEach((m) => {
      const row = document.createElement("tr");
      [m.id, formatDate(m.timestamp), formatCm(m.distance_cm), formatDate(m.created_at)].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      fragment.appendChild(row);
    });
    body.appendChild(fragment);
  }

  function renderChart() {
    if (typeof Chart === "undefined") return;
    const ordered = [...state.measurements].reverse();
    const labels = ordered.map((m) => timeFmt.format(new Date(m.timestamp)));
    const data = ordered.map((m) => m.distance_cm);

    if (!state.chart) {
      const ctx = $("distance-chart").getContext("2d");
      const gradient = ctx.createLinearGradient(0, 0, 0, 340);
      gradient.addColorStop(0, "rgba(56, 189, 248, 0.35)");
      gradient.addColorStop(1, "rgba(56, 189, 248, 0)");

      state.chart = new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [{
            label: "Distancia (cm)",
            data,
            borderColor: "#38bdf8",
            backgroundColor: gradient,
            fill: true,
            tension: 0.3,
            pointRadius: 2,
            pointHoverRadius: 5,
            borderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 400 },
          interaction: { mode: "index", intersect: false },
          scales: {
            x: { ticks: { color: "#8a9bb8", maxTicksLimit: 10 }, grid: { color: "rgba(35, 49, 79, 0.6)" } },
            y: {
              beginAtZero: true,
              title: { display: true, text: "cm", color: "#8a9bb8" },
              ticks: { color: "#8a9bb8" },
              grid: { color: "rgba(35, 49, 79, 0.6)" },
            },
          },
          plugins: {
            legend: { labels: { color: "#e5ecf6" } },
            tooltip: { callbacks: { label: (c) => ` ${formatCm(c.parsed.y)} cm` } },
          },
        },
      });
      return;
    }
    state.chart.data.labels = labels;
    state.chart.data.datasets[0].data = data;
    state.chart.update();
  }

  /* ---------- Datos ---------- */

  async function checkHealth() {
    try {
      const res = await ApiClient.health(state.apiUrl);
      if (res.ok && res.body?.status === "ok") {
        setIndicator(el.apiStatus, "ok", "API conectada");
        setIndicator(el.connectionBadge, "ok", "Conectado");
        el.apiDetail.textContent = `Latencia ${res.latencyMs} ms · v${res.body.version}`;
      } else {
        setIndicator(el.apiStatus, "warn", "API degradada");
        setIndicator(el.connectionBadge, "warn", "Degradado");
        el.apiDetail.textContent = `Base de datos: ${res.body?.database ?? "desconocida"} (HTTP ${res.status})`;
      }
      return res.ok;
    } catch (error) {
      setIndicator(el.apiStatus, "error", "Sin conexión");
      setIndicator(el.connectionBadge, "error", "Desconectado");
      el.apiDetail.textContent = error.name === "AbortError"
        ? "Tiempo de espera agotado (el servidor puede estar iniciando)"
        : "No fue posible contactar la API";
      return false;
    }
  }

  async function loadMeasurements() {
    const res = await ApiClient.list(state.apiUrl, state.limit);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.measurements = res.body.items;
    state.latest = res.body.items[0] || null;
    return res.body.total;
  }

  async function refresh() {
    if (state.loading) return;
    state.loading = true;
    el.refreshBtn.disabled = true;
    try {
      const healthy = await checkHealth();
      if (healthy) {
        const total = await loadMeasurements();
        renderStats(total);
        renderHistory();
        renderChart();
      }
    } catch (error) {
      showToast(`Error al cargar mediciones: ${error.message}`, true);
    } finally {
      renderLatest();
      renderDeviceStatus();
      state.loading = false;
      el.refreshBtn.disabled = false;
    }
  }

  function schedule() {
    clearInterval(state.timer);
    state.timer = setInterval(refresh, state.refreshSeconds * 1000);
  }

  /* ---------- Acciones ---------- */

  function exportCsv() {
    if (!state.measurements.length) {
      showToast("No hay datos para exportar");
      return;
    }
    const rows = [["id", "timestamp", "distance_cm", "created_at"],
      ...state.measurements.map((m) => [m.id, m.timestamp, m.distance_cm, m.created_at])];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `mediciones_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function bindEvents() {
    el.limitSelect.value = String(state.limit);
    el.limitSelect.addEventListener("change", () => {
      state.limit = Number(el.limitSelect.value);
      localStorage.setItem(STORAGE_KEYS.limit, state.limit);
      refresh();
    });
    el.refreshBtn.addEventListener("click", refresh);
    el.exportBtn.addEventListener("click", exportCsv);

    el.settingsToggle.addEventListener("click", () => {
      const open = el.settingsPanel.hidden;
      el.settingsPanel.hidden = !open;
      el.settingsToggle.setAttribute("aria-expanded", String(open));
      el.apiUrlInput.value = state.apiUrl;
      el.refreshInput.value = state.refreshSeconds;
    });

    el.settingsForm.addEventListener("submit", (event) => {
      event.preventDefault();
      state.apiUrl = el.apiUrlInput.value.trim().replace(/\/+$/, "");
      state.refreshSeconds = Math.max(5, Number(el.refreshInput.value) || defaults.REFRESH_INTERVAL_SECONDS);
      localStorage.setItem(STORAGE_KEYS.apiUrl, state.apiUrl);
      localStorage.setItem(STORAGE_KEYS.refresh, state.refreshSeconds);
      showToast("Configuración guardada");
      schedule();
      refresh();
    });

    el.settingsReset.addEventListener("click", () => {
      Object.values(STORAGE_KEYS).forEach((k) => localStorage.removeItem(k));
      state.apiUrl = defaults.API_BASE_URL;
      state.refreshSeconds = defaults.REFRESH_INTERVAL_SECONDS;
      el.apiUrlInput.value = state.apiUrl;
      el.refreshInput.value = state.refreshSeconds;
      showToast("Configuración restablecida");
      schedule();
      refresh();
    });

    // Actualiza los textos relativos ("hace X s") entre consultas.
    setInterval(() => { renderLatest(); renderDeviceStatus(); }, 5000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    refresh();
    schedule();
  });
})();
