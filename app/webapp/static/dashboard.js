document.getElementById("icon-cpu").innerHTML = ICONS.cpu;
document.getElementById("icon-activity").innerHTML = ICONS.activity;
document.getElementById("icon-help").innerHTML = ICONS.helpCircle;
document.getElementById("icon-how-it-works-close").innerHTML = ICONS.x;

const HOW_IT_WORKS_KEY = "blackbox-hide-howitworks";

function renderHowItWorks() {
  const banner = document.getElementById("how-it-works");
  let hidden = false;
  try {
    hidden = localStorage.getItem(HOW_IT_WORKS_KEY) === "1";
  } catch (err) {
    // No persistence available — just show it every time, harmless.
  }
  if (hidden) {
    banner.style.display = "none";
    return;
  }
  document.getElementById("steps-row").innerHTML = HOW_IT_WORKS_STEPS.map(
    (step, i) => `
      ${i > 0 ? `<span class="icon step-chevron">${ICONS.chevronRight}</span>` : ""}
      <div class="step">
        <div class="step-icon-circle">${ICONS[step.icon]}</div>
        <div class="step-title">${step.title}</div>
        <div class="step-detail">${step.detail}</div>
      </div>`
  ).join("");
}

document.getElementById("how-it-works-close").addEventListener("click", () => {
  document.getElementById("how-it-works").style.display = "none";
  try {
    localStorage.setItem(HOW_IT_WORKS_KEY, "1");
  } catch (err) {
    // Nothing to persist to; it'll just reappear next visit, which is fine.
  }
});

renderHowItWorks();

const RADIUS = 26;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const cpuHistory = [];
const HISTORY_LEN = 40;

function gaugeColor(value) {
  if (value === null || value === undefined) return "var(--text-faint)";
  return value >= 90 ? "var(--red)" : value >= 70 ? "var(--peach)" : "var(--accent)";
}

function gaugeColorEnd(value) {
  if (value === null || value === undefined) return "var(--text-faint)";
  return value >= 90 ? "var(--peach)" : value >= 70 ? "var(--yellow)" : "var(--accent-2)";
}

function renderGauge(label, value, tooltip) {
  const pct = value ?? 0;
  const offset = CIRCUMFERENCE * (1 - Math.min(pct, 100) / 100);
  const displayValue = value === null || value === undefined ? "–" : `${value.toFixed(1)}%`;
  // Unique ids per gauge so the two gradients/filters don't collide in the DOM.
  const gid = `g-${label.toLowerCase()}`;
  return `
    <div class="radial-gauge" title="${tooltip}">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <defs>
          <linearGradient id="${gid}-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="${gaugeColor(value)}" />
            <stop offset="100%" stop-color="${gaugeColorEnd(value)}" />
          </linearGradient>
          <filter id="${gid}-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <circle class="track" cx="34" cy="34" r="${RADIUS}"></circle>
        <circle class="fill" cx="34" cy="34" r="${RADIUS}"
          stroke="url(#${gid}-grad)"
          filter="url(#${gid}-glow)"
          stroke-dasharray="${CIRCUMFERENCE}"
          stroke-dashoffset="${offset}"></circle>
      </svg>
      <div class="radial-gauge-text">
        <span class="radial-gauge-value">${displayValue}</span>
        <span class="radial-gauge-label">${label}</span>
      </div>
    </div>`;
}

const STAT_TILES = [
  {
    key: "status",
    icon: "check",
    label: "System status",
    tooltip: "Whether your Mac looks like it's behaving normally right now.",
  },
  {
    key: "buffered",
    icon: "layers",
    cls: "blue",
    label: "Remembered events",
    tooltip: "Activity from the last ~5 minutes, kept ready as evidence if something breaks.",
  },
  {
    key: "incidents",
    icon: "activity",
    cls: "peach",
    label: "Problems investigated",
    tooltip: "How many times Black Box has caught a problem and explained it.",
  },
  {
    key: "processes",
    icon: "cube",
    label: "Apps being watched",
    tooltip: "Processes currently showing up in the resource-usage snapshot.",
  },
];

let statTilesBuilt = false;

function buildStatTiles() {
  document.getElementById("stat-grid").innerHTML = STAT_TILES.map(
    (t) => `
      <div class="stat-tile" title="${t.tooltip}" data-tile="${t.key}">
        <div class="stat-icon ${t.cls || ""}" data-icon>${ICONS[t.icon]}</div>
        <div>
          <div class="stat-value" data-value>–</div>
          <div class="stat-label">${t.label}</div>
        </div>
      </div>`
  ).join("");
  statTilesBuilt = true;
}

/** Eases a tile's number to its new value instead of snapping. Counters that
 *  tick up feel alive; they also make it obvious the page is live, not stale.
 *
 *  The animation is strictly decorative: the value is written synchronously
 *  whenever it can't be animated. requestAnimationFrame is suspended while a
 *  tab is hidden, so relying on it to write the number left a backgrounded
 *  dashboard stuck on its "–" placeholder forever (the bookkeeping had already
 *  advanced, so the next poll saw no change and skipped). */
function countUp(el, to) {
  const from = Number(el.dataset.current);
  el.dataset.current = String(to);

  if (!Number.isFinite(from) || from === to || document.hidden) {
    el.textContent = String(to);
    return;
  }

  const start = performance.now();
  const DURATION = 550;

  function frame(now) {
    const t = Math.min((now - start) / DURATION, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = String(Math.round(from + (to - from) * eased));
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function renderStatTiles(status, incidentCount) {
  if (!statTilesBuilt) buildStatTiles();

  const statusTile = document.querySelector('[data-tile="status"]');
  statusTile.querySelector("[data-value]").textContent = status.ok ? "All good" : "Needs attention";
  statusTile.querySelector("[data-icon]").className = `stat-icon ${status.ok ? "green" : "red"}`;
  statusTile.querySelector("[data-icon]").innerHTML = status.ok ? ICONS.check : ICONS.alert;

  countUp(document.querySelector('[data-tile="buffered"] [data-value]'), status.buffered_events ?? 0);
  countUp(document.querySelector('[data-tile="incidents"] [data-value]'), incidentCount);
  countUp(document.querySelector('[data-tile="processes"] [data-value]'), (status.top_processes || []).length);
}

/** Catmull-Rom through the samples, emitted as cubic beziers — a plain
 *  polyline on noisy per-second CPU data reads as jagged static. */
function smoothPath(points) {
  if (points.length < 2) return "";
  let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

function renderSparkline() {
  const svg = document.getElementById("sparkline");
  if (cpuHistory.length < 2) {
    svg.innerHTML = "";
    return;
  }
  const max = Math.max(100, ...cpuHistory);
  // Span the full width regardless of how many samples we have yet. Indexing
  // by a fixed step left-aligns a short history into a stub in the corner,
  // which reads as a rendering glitch rather than "still filling up".
  const stepX = 300 / Math.max(cpuHistory.length - 1, 1);
  const points = cpuHistory.map((v, i) => ({ x: i * stepX, y: 38 - (v / max) * 34 }));
  const line = smoothPath(points);
  const last = points[points.length - 1];
  const area = `${line} L ${last.x.toFixed(1)} 40 L ${points[0].x.toFixed(1)} 40 Z`;

  svg.innerHTML = `
    <defs>
      <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.35" />
        <stop offset="100%" stop-color="var(--accent)" stop-opacity="0" />
      </linearGradient>
      <linearGradient id="spark-stroke" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="var(--accent-2)" />
        <stop offset="100%" stop-color="var(--accent)" />
      </linearGradient>
      <filter id="spark-glow" x="-20%" y="-60%" width="140%" height="240%">
        <feGaussianBlur stdDeviation="2.5" result="b" />
        <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>
    <path d="${area}" fill="url(#spark-fill)" stroke="none" />
    <path d="${line}" fill="none" stroke="url(#spark-stroke)" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round" filter="url(#spark-glow)" />
    <circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="3.5" fill="var(--accent)" filter="url(#spark-glow)" />
    <circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="3.5" fill="none"
            stroke="var(--accent)" stroke-opacity="0.5" class="spark-pulse" />
  `;
}

let gaugesBuilt = false;

/** Gauges are built once and then mutated in place. Re-rendering the SVG
 *  every poll (as this used to) replaces the <circle>, so the CSS
 *  stroke-dashoffset transition never had an old value to animate from and
 *  the arc just snapped. Updating the same node lets it sweep. */
function updateGauges(status) {
  const container = document.getElementById("gauges");
  if (!gaugesBuilt) {
    container.innerHTML =
      renderGauge("CPU", status.cpu_percent, "How hard your processors are working right now.") +
      renderGauge("Memory", status.memory_percent, "How much of your RAM is currently in use.");
    gaugesBuilt = true;
    return;
  }

  const gauges = container.querySelectorAll(".radial-gauge");
  const values = [status.cpu_percent, status.memory_percent];
  gauges.forEach((gauge, i) => {
    const value = values[i];
    const pct = value ?? 0;
    gauge.querySelector(".fill").setAttribute(
      "stroke-dashoffset",
      String(CIRCUMFERENCE * (1 - Math.min(pct, 100) / 100))
    );
    const stops = gauge.querySelectorAll("linearGradient stop");
    stops[0].setAttribute("stop-color", gaugeColor(value));
    stops[1].setAttribute("stop-color", gaugeColorEnd(value));
    gauge.querySelector(".radial-gauge-value").textContent =
      value === null || value === undefined ? "–" : `${value.toFixed(1)}%`;
  });
}

async function refreshStatus() {
  const res = await fetch("/api/status");
  const status = await res.json();

  const pill = document.getElementById("status-pill");
  pill.textContent = status.ok ? "Everything OK" : "Needs attention";
  pill.className = "pill " + (status.ok ? "pill-ok" : "pill-bad");

  updateGauges(status);

  cpuHistory.push(status.cpu_percent ?? 0);
  if (cpuHistory.length > HISTORY_LEN) cpuHistory.shift();
  renderSparkline();

  const rows = document.getElementById("proc-rows");
  rows.innerHTML = "";
  for (const proc of status.top_processes || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(proc.name)}</td>
      <td><div class="proc-bar-cell">${proc.cpu_percent.toFixed(1)}
        <div class="proc-bar-track"><div class="proc-bar-fill" style="width:${Math.min(proc.cpu_percent, 100)}%"></div></div>
      </div></td>
      <td>${proc.memory_percent.toFixed(1)}</td>`;
    rows.appendChild(tr);
  }

  return status;
}

async function refreshIncidents(status) {
  const res = await fetch("/api/incidents");
  const incidents = await res.json();
  const list = document.getElementById("incident-list");
  list.innerHTML = "";

  if (incidents.length === 0) {
    list.innerHTML = `<li class="incident-empty">${ICONS.activity} Nothing to report yet — Black Box is watching quietly in the background.</li>`;
  } else {
    for (const incident of incidents) {
      const li = document.createElement("li");
      const badge = incident.analysis_succeeded ? "" : `<span class="badge">${ICONS.alert} AI unavailable</span>`;
      li.innerHTML = `<div class="incident-row-icon">${ICONS.alert}</div>
        <div class="incident-row-main">
          <a class="incident-row-title" href="/incidents/${incident.incident_id}">${escapeHtml(incident.trigger_reason)}</a>
          <span class="incident-row-sub">${humanizeTrigger(incident.trigger_name)} · ${new Date(incident.created_at).toLocaleString()}</span>
        </div>
        ${badge}`;
      list.appendChild(li);
    }
  }

  if (status) renderStatTiles(status, incidents.length);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

async function tick() {
  const status = await refreshStatus();
  await refreshIncidents(status);
}

tick();
setInterval(tick, 3000);
