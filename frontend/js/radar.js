/*
 * Radar del HC-SR04 sobre servo SG90. Dibuja el entorno a partir del barrido real (/stats/sweep):
 * área de espacio libre, contorno de los objetos y barridos anteriores atenuados. El último
 * acercamiento (/stats/last_alert) se marca en rojo en su ángulo.
 * Eventos de app.js: "radar:sweep" ({ sweep, alert }) y "measurements:updated" (lecturas).
 */
(() => {
  "use strict";

  const cfg = window.APP_CONFIG || {};
  const MAX_CM = cfg.MAX_DISTANCE_CM || 400;
  const MIRROR = Boolean(cfg.RADAR_MIRROR);
  const HISTORY = cfg.RADAR_HISTORY || 3;
  const TRAIL = cfg.RADAR_TRAIL || 10;
  const ALERT_VISIBLE_S = cfg.RADAR_ALERT_SECONDS || 60;
  // Velocidad aproximada del servo en el firmware (5° cada ~0,3 s).
  const BEAM_DEG_PER_S = cfg.RADAR_BEAM_DEG_PER_S || 16;
  const GREEN = "34, 197, 94";
  const RED = "239, 68, 68";

  const $ = (id) => document.getElementById(id);
  let sweeps = [];
  let alert = null;
  let readings = [];
  let beam = 90;
  let beamDir = 1;
  let lastFrame = 0;
  let canvas;
  let ctx;

  function parseSweep(sweep) {
    if (!sweep || !sweep.d) return null;
    const values = Array.isArray(sweep.d) ? sweep.d : Object.values(sweep.d);
    const start = Number(sweep.start ?? 0);
    const step = Number(sweep.step ?? 5);
    return {
      epoch: Number(sweep.epoch),
      angle: Number(sweep.angle ?? 90),
      points: values.map((d, i) => ({ angle: start + i * step, d: Number(d) })),
    };
  }

  function resize() {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = Math.round(width * 0.58);
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function geometry() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const r = Math.min(w / 2 - 12, h - 30);
    return { w, h, cx: w / 2, cy: h - 18, r, scale: r / MAX_CM };
  }

  function polar(g, cm, deg) {
    const a = ((MIRROR ? 180 - deg : deg) * Math.PI) / 180;
    const radius = Math.min(cm, MAX_CM) * g.scale;
    return [g.cx - radius * Math.cos(a), g.cy - radius * Math.sin(a)];
  }

  function drawGrid(g) {
    ctx.fillStyle = "rgba(2, 12, 6, 0.95)";
    ctx.beginPath();
    ctx.arc(g.cx, g.cy, g.r, Math.PI, 0);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = `rgba(${GREEN}, 0.25)`;
    ctx.fillStyle = `rgba(${GREEN}, 0.7)`;
    ctx.lineWidth = 1;
    ctx.font = "11px Segoe UI, sans-serif";
    const labelStep = 100 * g.scale < 40 ? 200 : 100;
    for (let cm = 100; cm <= MAX_CM; cm += 100) {
      ctx.beginPath();
      ctx.arc(g.cx, g.cy, cm * g.scale, Math.PI, 0);
      ctx.stroke();
      if (cm % labelStep === 0) ctx.fillText(`${cm}`, g.cx + 3, g.cy - cm * g.scale + 12);
    }
    for (let deg = 0; deg <= 180; deg += 30) {
      const [x, y] = polar(g, MAX_CM, deg);
      ctx.beginPath();
      ctx.moveTo(g.cx, g.cy);
      ctx.lineTo(x, y);
      ctx.stroke();
      const [lx, ly] = polar(g, MAX_CM * 1.0, deg);
      ctx.fillText(`${deg}°`, lx + (lx < g.cx ? -2 : -22) + (deg === 90 ? 10 : 0), deg === 0 || deg === 180 ? ly + 13 : ly - 4);
    }
    ctx.fillText("cm", g.cx + 3, g.cy + 13);
  }

  // Espacio libre (sin eco = libre hasta el alcance) y contorno de los objetos detectados.
  function drawSweep(g, sweep, alpha, filled) {
    if (filled) {
      ctx.fillStyle = `rgba(${GREEN}, ${0.16 * alpha})`;
      ctx.beginPath();
      ctx.moveTo(g.cx, g.cy);
      sweep.points.forEach((p) => {
        const [x, y] = polar(g, p.d > 0 ? p.d : MAX_CM, p.angle);
        ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.fill();
    }
    ctx.strokeStyle = `rgba(${GREEN}, ${0.9 * alpha})`;
    ctx.lineWidth = filled ? 2 : 1.2;
    ctx.beginPath();
    let open = false;
    sweep.points.forEach((p) => {
      if (!(p.d > 0) || p.d > MAX_CM) { open = false; return; }
      const [x, y] = polar(g, p.d, p.angle);
      if (open) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      open = true;
    });
    ctx.stroke();
    if (filled) {
      ctx.fillStyle = `rgba(${GREEN}, ${alpha})`;
      sweep.points.forEach((p) => {
        if (!(p.d > 0) || p.d > MAX_CM) return;
        const [x, y] = polar(g, p.d, p.angle);
        ctx.beginPath();
        ctx.arc(x, y, 2.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  }

  function drawBeam(g, dt) {
    beam += beamDir * BEAM_DEG_PER_S * dt;
    if (beam >= 180) { beam = 180; beamDir = -1; }
    if (beam <= 0) { beam = 0; beamDir = 1; }
    for (let i = 0; i < 18; i += 1) {
      const deg = beam - beamDir * i * 1.5;
      if (deg < 0 || deg > 180) continue;
      const [x, y] = polar(g, MAX_CM, deg);
      ctx.strokeStyle = `rgba(${GREEN}, ${0.7 * (1 - i / 18)})`;
      ctx.lineWidth = i === 0 ? 2.5 : 2;
      ctx.beginPath();
      ctx.moveTo(g.cx, g.cy);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
  }

  function recentAlert() {
    if (!alert || !Number.isFinite(alert.angle_deg)) return null;
    const age = Date.now() / 1000 - Number(alert.epoch);
    return age >= 0 && age <= ALERT_VISIBLE_S && alert.type === "acercamiento" ? { ...alert, age } : null;
  }

  function drawAlert(g, now) {
    const a = recentAlert();
    if (!a) return;
    const [x, y] = polar(g, a.distance_cm, a.angle_deg);
    const pulse = (now / 600) % 1;
    ctx.strokeStyle = `rgba(${RED}, 0.5)`;
    ctx.setLineDash([4, 5]);
    ctx.beginPath();
    ctx.moveTo(g.cx, g.cy);
    ctx.lineTo(...polar(g, MAX_CM, a.angle_deg));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = `rgba(${RED}, 0.95)`;
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = `rgba(${RED}, ${0.8 * (1 - pulse)})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, 8 + 16 * pulse, 0, Math.PI * 2);
    ctx.stroke();
    ctx.font = "bold 12px Segoe UI, sans-serif";
    ctx.fillText(`${Number(a.distance_cm).toFixed(0)} cm · ${a.angle_deg}°`, x + 12, y - 8);
  }

  function draw(now) {
    const dt = lastFrame ? Math.min(0.1, (now - lastFrame) / 1000) : 0;
    lastFrame = now;
    const g = geometry();
    ctx.clearRect(0, 0, g.w, g.h);
    drawGrid(g);
    sweeps.slice(1).reverse().forEach((s, i, list) => drawSweep(g, s, 0.15 + 0.25 * (i / Math.max(1, list.length)), false));
    if (sweeps[0]) drawSweep(g, sweeps[0], 1, true);
    drawBeam(g, dt);
    drawAlert(g, now);
    requestAnimationFrame(draw);
  }

  function renderInfo() {
    const status = $("radar-status");
    const a = recentAlert();
    let cls = "status-unknown";
    let text = "Esperando barrido";
    if (a) {
      cls = "status-error";
      text = `Acercamiento a ${a.angle_deg}° (${Number(a.distance_cm).toFixed(0)} cm)`;
    } else if (sweeps[0]) {
      cls = "status-ok";
      text = "Sin acercamientos";
    }
    status.className = `status ${cls}`;
    status.querySelector(".label").textContent = text;

    const s = sweeps[0];
    let detail = "Sin datos";
    if (s) {
      const valid = s.points.filter((p) => p.d > 0);
      const nearest = valid.reduce((m, p) => (!m || p.d < m.d ? p : m), null);
      const age = Math.max(0, Math.round(Date.now() / 1000 - s.epoch));
      detail = `${valid.length}/${s.points.length} ángulos con eco · ` +
        (nearest ? `más cercano ${nearest.d.toFixed(1)} cm a ${nearest.angle}° · ` : "") + `barrido hace ${age} s`;
    }
    $("radar-detail").textContent = detail;
  }

  function renderTable() {
    const body = $("radar-body");
    body.replaceChildren();
    readings.slice(0, TRAIL).forEach((m, i) => {
      const prev = readings[i + 1];
      const delta = prev ? m.distance_cm - prev.distance_cm : null;
      const row = body.insertRow();
      row.insertCell().textContent = m.timestamp ? m.timestamp.slice(11, 19) : "";
      row.insertCell().textContent = Number.isFinite(m.angle_deg) ? `${m.angle_deg}°` : "—";
      row.insertCell().textContent = m.distance_cm.toFixed(2);
      row.insertCell().textContent = delta === null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
      const cell = row.insertCell();
      if (delta === null || Math.abs(delta) < 2) cell.textContent = "• estable";
      else if (delta < 0) { cell.textContent = "▼ más cerca"; row.classList.add("tag-near"); }
      else cell.textContent = "▲ más lejos";
    });
    if (!readings.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = 5;
      cell.className = "empty";
      cell.textContent = "Sin datos";
    }
  }

  document.addEventListener("radar:sweep", (event) => {
    const { sweep, alert: last } = event.detail || {};
    alert = last || alert;
    const parsed = parseSweep(sweep);
    if (parsed && parsed.epoch !== sweeps[0]?.epoch) {
      sweeps = [parsed, ...sweeps].slice(0, HISTORY + 1);
      beam = parsed.angle;
    }
    renderInfo();
  });

  document.addEventListener("measurements:updated", (event) => {
    readings = (event.detail || []).filter((m) => Number.isFinite(m.distance_cm));
    renderTable();
  });

  document.addEventListener("DOMContentLoaded", () => {
    canvas = $("radar-canvas");
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    resize();
    window.addEventListener("resize", resize);
    renderInfo();
    renderTable();
    setInterval(renderInfo, 1000);
    requestAnimationFrame(draw);
  });
})();
