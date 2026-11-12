/*
 * Radar clásico del HC-SR04. Recibe las lecturas de app.js (evento "measurements:updated").
 * Sin servo el sensor apunta a un rumbo fijo (90°): el eco se dibuja sobre esa línea y el rastro
 * de lecturas anteriores muestra si el objeto se acerca o se aleja.
 */
(() => {
  "use strict";

  const cfg = window.APP_CONFIG || {};
  const MAX_CM = cfg.MAX_DISTANCE_CM || 400;
  const BEARING_DEG = cfg.RADAR_BEARING_DEG ?? 90;
  const TRAIL = cfg.RADAR_TRAIL || 10;
  // Cambio mínimo por lectura para considerar que el objeto se mueve (el ruido del sensor es < 1 cm).
  const TREND_CM = cfg.RADAR_TREND_CM || 2;
  const SWEEP_DEG_PER_S = 60;
  const GREEN = "34, 197, 94";
  const RED = "239, 68, 68";

  const $ = (id) => document.getElementById(id);
  let readings = [];
  let sweep = 0;
  let direction = 1;
  let lastFrame = 0;
  let canvas;
  let ctx;

  function trend(items) {
    if (items.length < 2) return { kind: "unknown", delta: 0, speed: 0 };
    const [last, prev] = items;
    const delta = last.distance_cm - prev.distance_cm;
    const seconds = Math.max(1, last.epoch - prev.epoch);
    const kind = delta <= -TREND_CM ? "approaching" : delta >= TREND_CM ? "receding" : "steady";
    return { kind, delta, speed: delta / seconds };
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

  function polar(cx, cy, radius, deg) {
    const rad = (deg * Math.PI) / 180;
    return [cx + radius * Math.cos(Math.PI - rad), cy - radius * Math.sin(Math.PI - rad)];
  }

  function draw(now) {
    const dt = lastFrame ? (now - lastFrame) / 1000 : 0;
    lastFrame = now;
    sweep += direction * SWEEP_DEG_PER_S * dt;
    if (sweep >= 180) { sweep = 180; direction = -1; }
    if (sweep <= 0) { sweep = 0; direction = 1; }

    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const cx = w / 2;
    const cy = h - 18;
    const r = Math.min(w / 2 - 12, h - 30);
    const scale = r / MAX_CM;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "rgba(2, 12, 6, 0.9)";
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI, 0);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = `rgba(${GREEN}, 0.35)`;
    ctx.fillStyle = `rgba(${GREEN}, 0.75)`;
    ctx.lineWidth = 1;
    ctx.font = "11px Segoe UI, sans-serif";
    // Etiquetas solo si caben (en pantallas estrechas se muestra una de cada dos).
    const labelStep = 100 * scale < 40 ? 200 : 100;
    for (let cm = 100; cm <= MAX_CM; cm += 100) {
      ctx.beginPath();
      ctx.arc(cx, cy, cm * scale, Math.PI, 0);
      ctx.stroke();
      if (cm % labelStep === 0) ctx.fillText(`${cm}`, cx - cm * scale + 3, cy - 4);
    }
    ctx.fillText("cm", cx - r + 3, cy + 13);
    for (let deg = 0; deg <= 180; deg += 30) {
      const [x, y] = polar(cx, cy, r, deg);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(x, y);
      ctx.stroke();
    }

    // Línea de visión del sensor (rumbo fijo sin servo).
    const [bx, by] = polar(cx, cy, r, BEARING_DEG);
    ctx.setLineDash([4, 6]);
    ctx.strokeStyle = `rgba(${GREEN}, 0.6)`;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(bx, by);
    ctx.stroke();
    ctx.setLineDash([]);

    // Barrido con estela.
    for (let i = 0; i < 24; i += 1) {
      const deg = sweep - direction * i * 1.2;
      if (deg < 0 || deg > 180) continue;
      const [x, y] = polar(cx, cy, r, deg);
      ctx.strokeStyle = `rgba(${GREEN}, ${0.9 * (1 - i / 24)})`;
      ctx.lineWidth = i === 0 ? 2.5 : 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(x, y);
      ctx.stroke();
    }

    // Ecos: el más reciente se ilumina al paso del barrido; el rastro muestra la trayectoria.
    const t = trend(readings);
    const color = t.kind === "approaching" ? RED : GREEN;
    const glow = Math.max(0.35, 1 - Math.abs(sweep - BEARING_DEG) / 90);
    readings.slice(0, TRAIL).reverse().forEach((m, index, list) => {
      const isLast = index === list.length - 1;
      const [x, y] = polar(cx, cy, Math.min(m.distance_cm, MAX_CM) * scale, BEARING_DEG);
      const alpha = isLast ? glow : 0.3 + 0.5 * (index / list.length);
      ctx.fillStyle = `rgba(${isLast ? color : GREEN}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(x, y, isLast ? 7 + 3 * glow : 4.5, 0, Math.PI * 2);
      ctx.fill();
      if (isLast) {
        ctx.strokeStyle = `rgba(${color}, ${0.5 * glow})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 14 + 8 * (1 - glow), 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = `rgba(${color}, 0.95)`;
        ctx.font = "bold 12px Segoe UI, sans-serif";
        ctx.fillText(`${m.distance_cm.toFixed(1)} cm`, x + 14, y + 4);
      }
    });

    requestAnimationFrame(draw);
  }

  function renderInfo() {
    const t = trend(readings);
    const status = $("radar-status");
    const labels = {
      approaching: ["status-error", "Objeto acercándose"],
      receding: ["status-ok", "Objeto alejándose"],
      steady: ["status-ok", "Sin movimiento"],
      unknown: ["status-unknown", "Esperando lecturas"],
    };
    const [cls, text] = labels[t.kind];
    status.className = `status ${cls}`;
    status.querySelector(".label").textContent = text;
    $("radar-detail").textContent = readings.length
      ? `Última: ${readings[0].distance_cm.toFixed(2)} cm · cambio ${t.delta >= 0 ? "+" : ""}${t.delta.toFixed(2)} cm · ${Math.abs(t.speed).toFixed(2)} cm/s`
      : "Sin datos";

    const body = $("radar-body");
    body.replaceChildren();
    readings.slice(0, TRAIL).forEach((m, i) => {
      const prev = readings[i + 1];
      const delta = prev ? m.distance_cm - prev.distance_cm : null;
      const row = body.insertRow();
      row.insertCell().textContent = m.timestamp ? m.timestamp.slice(11, 19) : "";
      row.insertCell().textContent = m.distance_cm.toFixed(2);
      row.insertCell().textContent = delta === null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
      const cell = row.insertCell();
      if (delta === null || Math.abs(delta) < TREND_CM) cell.textContent = "• estable";
      else if (delta < 0) { cell.textContent = "▼ se acerca"; row.classList.add("tag-near"); }
      else cell.textContent = "▲ se aleja";
    });
    if (!readings.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = 4;
      cell.className = "empty";
      cell.textContent = "Sin datos";
    }
  }

  document.addEventListener("measurements:updated", (event) => {
    readings = (event.detail || []).filter((m) => Number.isFinite(m.distance_cm));
    renderInfo();
  });

  document.addEventListener("DOMContentLoaded", () => {
    canvas = $("radar-canvas");
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    resize();
    window.addEventListener("resize", resize);
    renderInfo();
    requestAnimationFrame(draw);
  });
})();
