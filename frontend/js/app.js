/* Lógica del dashboard: estado, renderizado y actualización periódica. */
(function () {
  "use strict";

  const STORAGE_KEYS = { dbUrl: "esp32dms.dbUrl", refresh: "esp32dms.refresh", limit: "esp32dms.limit", sound: "esp32dms.sound" };
  const defaults = window.APP_CONFIG;

  const state = {
    dbUrl: localStorage.getItem(STORAGE_KEYS.dbUrl) || defaults.FIREBASE_DB_URL,
    refreshSeconds: Number(localStorage.getItem(STORAGE_KEYS.refresh)) || defaults.REFRESH_INTERVAL_SECONDS,
    limit: Number(localStorage.getItem(STORAGE_KEYS.limit)) || 50,
    measurements: [],
    latest: null,
    stats: null,
    total: 0,
    exporting: false,
    timer: null,
    chart: null,
    loading: false,
    alerts: [],
    lastAlertEpoch: null,   // última alerta ya conocida (las anteriores a la carga no suenan)
    lastLatestEpoch: null,
    soundEnabled: false,
    audioCtx: null,
    stream: null,
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
    exportForm: $("export-form"),
    exportBtn: $("export-btn"),
    exportFrom: $("export-from"),
    exportTo: $("export-to"),
    settingsToggle: $("settings-toggle"),
    settingsPanel: $("settings-panel"),
    settingsForm: $("settings-form"),
    settingsReset: $("settings-reset"),
    dbUrlInput: $("db-url-input"),
    refreshInput: $("refresh-input"),
    toast: $("toast"),
    soundToggle: $("sound-toggle"),
    alertBanner: $("alert-banner"),
    alertTitle: $("alert-title"),
    alertMessage: $("alert-message"),
    alertDismiss: $("alert-dismiss"),
    alertsBody: $("alerts-body"),
    alertRule: $("alert-rule"),
    statAlerts: $("stat-alerts"),
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

  /* ---------- Alertas ---------- */

  const alertTypeLabel = (type) => (type === "acercamiento" ? "Acercamiento" : "Alejamiento");
  const signed = (value) => `${value > 0 ? "+" : ""}${formatCm(value)}`;

  function renderAlerts() {
    const body = el.alertsBody;
    body.replaceChildren();
    el.statAlerts.textContent = state.stats?.alert_count ?? state.alerts.length;
    if (!state.alerts.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = 5;
      cell.className = "empty";
      cell.textContent = "Sin alertas";
      return;
    }
    const fragment = document.createDocumentFragment();
    state.alerts.forEach((a) => {
      const row = document.createElement("tr");
      [formatDate(a.ts), formatCm(a.previous_cm), formatCm(a.distance_cm), signed(a.delta_cm), alertTypeLabel(a.type)]
        .forEach((value, i) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          if (i === 4) cell.className = a.type === "acercamiento" ? "tag-near" : "tag-far";
          row.appendChild(cell);
        });
      fragment.appendChild(row);
    });
    body.appendChild(fragment);
  }

  // Tres pitidos alternos generados con Web Audio (no requiere archivos de sonido).
  function playAlarm() {
    if (!state.soundEnabled || !state.audioCtx) return;
    const ctx = state.audioCtx;
    const start = ctx.currentTime + 0.05;
    [880, 660, 880].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.value = freq;
      const t = start + i * 0.25;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.22);
    });
  }

  function triggerAlert(alert) {
    const hora = timeFmt.format(new Date(alert.ts));
    el.alertTitle.textContent = `${alertTypeLabel(alert.type)} detectado · ${hora}`;
    el.alertMessage.textContent =
      `La distancia cambió de ${formatCm(alert.previous_cm)} cm a ${formatCm(alert.distance_cm)} cm ` +
      `(${signed(alert.delta_cm)} cm; umbral ${alert.threshold_cm ?? defaults.ALERT_THRESHOLD_CM} cm).`;
    el.alertBanner.classList.toggle("alert-near", alert.type === "acercamiento");
    el.alertBanner.hidden = false;
    document.title = `⚠ ${alertTypeLabel(alert.type)} · ESP32 Distance Monitoring`;
    playAlarm();
    showToast(`Alerta: ${formatCm(alert.previous_cm)} → ${formatCm(alert.distance_cm)} cm`);
  }

  // Procesa /stats (desde la consulta periódica o desde el stream) y dispara la alerta si es nueva.
  function onStats(stats) {
    state.stats = stats;
    const last = stats?.last_alert;
    const epoch = last ? Number(last.epoch) : 0;
    if (state.lastAlertEpoch === null) {
      state.lastAlertEpoch = epoch;
    } else if (epoch > state.lastAlertEpoch) {
      state.lastAlertEpoch = epoch;
      state.alerts = [last, ...state.alerts.filter((a) => a.epoch !== epoch)].slice(0, defaults.ALERTS_LIMIT);
      renderAlerts();
      triggerAlert(last);
    }
    el.statAlerts.textContent = stats?.alert_count ?? state.alerts.length;
  }

  async function loadAlerts() {
    const res = await FirebaseClient.alerts(state.dbUrl, defaults.ALERTS_LIMIT);
    if (res.ok) {
      state.alerts = res.items;
      renderAlerts();
    }
  }

  // Tiempo real: Firebase empuja cada cambio de /stats (nueva lectura o alerta) sin esperar al refresco.
  function startStream() {
    if (state.stream) state.stream.close();
    if (typeof EventSource === "undefined") return;
    state.stream = FirebaseClient.listen(state.dbUrl, "stats", (stats) => {
      onStats(stats);
      const latestEpoch = Number(stats?.latest?.epoch) || null;
      if (latestEpoch && latestEpoch !== state.lastLatestEpoch) {
        state.lastLatestEpoch = latestEpoch;
        refresh();
      }
    }, (open) => {
      el.apiDetail.dataset.stream = open ? "en vivo" : "reconectando";
    });
  }

  function setSound(enabled) {
    state.soundEnabled = enabled;
    if (enabled) {
      state.audioCtx = state.audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      state.audioCtx.resume();
    }
    el.soundToggle.textContent = enabled ? "🔔 Sonido activado" : "🔕 Activar sonido";
    el.soundToggle.setAttribute("aria-pressed", String(enabled));
    localStorage.setItem(STORAGE_KEYS.sound, enabled ? "1" : "0");
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
    const top = Math.max(state.total, state.measurements.length);
    state.measurements.forEach((m, index) => {
      const row = document.createElement("tr");
      const received = m.created_at ? formatDate(m.created_at) : "--";
      [top - index, formatDate(m.timestamp), formatCm(m.distance_cm), received].forEach((value) => {
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
    // Las lecturas que generaron alerta se resaltan en rojo y con mayor tamaño.
    const alertEpochs = new Set(state.alerts.map((a) => a.epoch));
    const pointColors = ordered.map((m) => (alertEpochs.has(m.epoch) ? "#f87171" : "#38bdf8"));
    const pointSizes = ordered.map((m) => (alertEpochs.has(m.epoch) ? 6 : 2));

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
            pointRadius: pointSizes,
            pointBackgroundColor: pointColors,
            pointBorderColor: pointColors,
            pointHoverRadius: 7,
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
    state.chart.data.datasets[0].pointRadius = pointSizes;
    state.chart.data.datasets[0].pointBackgroundColor = pointColors;
    state.chart.data.datasets[0].pointBorderColor = pointColors;
    state.chart.update();
  }

  /* ---------- Datos ---------- */

  async function checkHealth() {
    try {
      const res = await FirebaseClient.stats(state.dbUrl);
      if (res.ok) {
        onStats(res.body);
        setIndicator(el.apiStatus, "ok", "Firebase conectado");
        setIndicator(el.connectionBadge, "ok", "Conectado");
        const live = el.apiDetail.dataset.stream ? ` · ${el.apiDetail.dataset.stream}` : "";
        el.apiDetail.textContent = `Realtime Database · latencia ${res.latencyMs} ms${live}`;
      } else {
        setIndicator(el.apiStatus, "warn", "Firebase con errores");
        setIndicator(el.connectionBadge, "warn", "Degradado");
        el.apiDetail.textContent = `${res.body?.error ?? "Error"} (HTTP ${res.status})`;
      }
      return res.ok;
    } catch (error) {
      setIndicator(el.apiStatus, "error", "Sin conexión");
      setIndicator(el.connectionBadge, "error", "Desconectado");
      el.apiDetail.textContent = error.name === "AbortError"
        ? "Tiempo de espera agotado"
        : "No fue posible contactar Firebase";
      return false;
    }
  }

  async function loadMeasurements() {
    const res = await FirebaseClient.recent(state.dbUrl, state.limit);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.measurements = res.items;
    document.dispatchEvent(new CustomEvent("measurements:updated", { detail: res.items }));
    const latest = state.stats?.latest;
    state.latest = latest ? FirebaseClient.normalize(String(latest.epoch), latest) : res.items[0] || null;
    state.total = Math.max(Number(state.stats?.count) || 0, res.items.length);
    return state.total;
  }

  async function refresh() {
    if (state.loading) return;
    state.loading = true;
    el.refreshBtn.disabled = true;
    try {
      const healthy = await checkHealth();
      if (healthy) {
        const total = await loadMeasurements();
        await loadAlerts();
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

  // "2026-11-01T11:08:55-05:00" -> "2026-11-01 11:08:55" (hora local del dispositivo).
  const deviceTime = (iso) => (iso ? iso.slice(0, 19).replace("T", " ") : "");

  const toEpoch = (dateStr, endOfDay) =>
    dateStr ? Math.floor(new Date(`${dateStr}T${endOfDay ? "23:59:59" : "00:00:00"}`).getTime() / 1000) : null;

  async function exportExcel(event) {
    event.preventDefault();
    if (state.exporting) return;
    if (typeof XLSX === "undefined") {
      showToast("No se pudo cargar la librería de Excel. Revise su conexión.", true);
      return;
    }

    const from = el.exportFrom.value;
    const to = el.exportTo.value;
    if (from && to && from > to) {
      showToast("La fecha inicial debe ser anterior a la final", true);
      return;
    }

    state.exporting = true;
    el.exportBtn.disabled = true;
    el.exportBtn.textContent = "Generando…";
    try {
      const res = await FirebaseClient.range(state.dbUrl, toEpoch(from, false), toEpoch(to, true));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.items.length) {
        showToast("No hay lecturas en el rango seleccionado");
        return;
      }

      const items = [...res.items].reverse();
      const rows = items.map((m, i) => ({
        "N°": i + 1,
        "Fecha y hora (lectura)": deviceTime(m.timestamp),
        "Distancia (cm)": Number(m.distance_cm.toFixed(2)),
        "Recibido en Firebase": m.created_at ? formatDate(m.created_at) : "",
        "Dispositivo": m.device,
        "Epoch (UTC)": m.epoch,
      }));
      const values = items.map((m) => m.distance_cm);
      const sum = values.reduce((a, b) => a + b, 0);
      const summary = [
        ["Resumen de lecturas", ""],
        ["Desde", deviceTime(items[0].timestamp)],
        ["Hasta", deviceTime(items[items.length - 1].timestamp)],
        ["Registros", items.length],
        ["Mínimo (cm)", Number(Math.min(...values).toFixed(2))],
        ["Máximo (cm)", Number(Math.max(...values).toFixed(2))],
        ["Promedio (cm)", Number((sum / values.length).toFixed(2))],
        ["Generado", formatDate(new Date().toISOString())],
      ];

      const wb = XLSX.utils.book_new();
      const wsData = XLSX.utils.json_to_sheet(rows);
      wsData["!cols"] = [{ wch: 8 }, { wch: 22 }, { wch: 15 }, { wch: 22 }, { wch: 15 }, { wch: 13 }];
      wsData["!autofilter"] = { ref: wsData["!ref"] };
      const wsSummary = XLSX.utils.aoa_to_sheet(summary);
      wsSummary["!cols"] = [{ wch: 18 }, { wch: 22 }];
      XLSX.utils.book_append_sheet(wb, wsData, "Lecturas");
      XLSX.utils.book_append_sheet(wb, wsSummary, "Resumen");

      const suffix = from || to ? `${from || "inicio"}_a_${to || "hoy"}` : "completo";
      XLSX.writeFile(wb, `lecturas_distancia_${suffix}.xlsx`);
      showToast(`Excel generado con ${items.length} lecturas`);
    } catch (error) {
      showToast(`Error al exportar: ${error.message}`, true);
    } finally {
      state.exporting = false;
      el.exportBtn.disabled = false;
      el.exportBtn.textContent = "⬇ Descargar Excel";
    }
  }

  function bindEvents() {
    el.limitSelect.value = String(state.limit);
    el.limitSelect.addEventListener("change", () => {
      state.limit = Number(el.limitSelect.value);
      localStorage.setItem(STORAGE_KEYS.limit, state.limit);
      refresh();
    });
    el.refreshBtn.addEventListener("click", refresh);
    el.exportForm.addEventListener("submit", exportExcel);

    el.alertRule.textContent = `Se alerta cuando dos lecturas consecutivas difieren ≥ ${defaults.ALERT_THRESHOLD_CM} cm`;
    // El navegador solo permite reproducir audio después de una interacción del usuario.
    setSound(false);
    el.soundToggle.addEventListener("click", () => {
      setSound(!state.soundEnabled);
      if (state.soundEnabled) playAlarm();
    });
    el.alertDismiss.addEventListener("click", () => {
      el.alertBanner.hidden = true;
      document.title = "ESP32 Distance Monitoring System";
    });

    el.settingsToggle.addEventListener("click", () => {
      const open = el.settingsPanel.hidden;
      el.settingsPanel.hidden = !open;
      el.settingsToggle.setAttribute("aria-expanded", String(open));
      el.dbUrlInput.value = state.dbUrl;
      el.refreshInput.value = state.refreshSeconds;
    });

    el.settingsForm.addEventListener("submit", (event) => {
      event.preventDefault();
      state.dbUrl = el.dbUrlInput.value.trim().replace(/\/+$/, "");
      state.refreshSeconds = Math.max(5, Number(el.refreshInput.value) || defaults.REFRESH_INTERVAL_SECONDS);
      localStorage.setItem(STORAGE_KEYS.dbUrl, state.dbUrl);
      localStorage.setItem(STORAGE_KEYS.refresh, state.refreshSeconds);
      showToast("Configuración guardada");
      schedule();
      startStream();
      refresh();
    });

    el.settingsReset.addEventListener("click", () => {
      Object.values(STORAGE_KEYS).forEach((k) => localStorage.removeItem(k));
      state.dbUrl = defaults.FIREBASE_DB_URL;
      state.refreshSeconds = defaults.REFRESH_INTERVAL_SECONDS;
      el.dbUrlInput.value = state.dbUrl;
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
    startStream();
  });
})();
