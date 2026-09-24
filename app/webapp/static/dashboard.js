document.getElementById("icon-grid").innerHTML = ICONS.grid;
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

function renderGauge(label, value, tooltip) {
  const pct = value ?? 0;
  const offset = CIRCUMFERENCE * (1 - Math.min(pct, 100) / 100);
  const color = gaugeColor(value);
  const displayValue = value === null || value === undefined ? "–" : `${value.toFixed(1)}%`;
  return `
    <div class="radial-gauge" title="${tooltip}">
      <svg width="64" height="64" viewBox="0 0 64 64">
        <circle class="track" cx="32" cy="32" r="${RADIUS}"></circle>
        <circle class="fill" cx="32" cy="32" r="${RADIUS}"
          stroke="${color}"
          stroke-dasharray="${CIRCUMFERENCE}"
          stroke-dashoffset="${offset}"></circle>
      </svg>
      <div class="radial-gauge-text">
        <span class="radial-gauge-value">${displayValue}</span>
        <span class="radial-gauge-label">${label}</span>
      </div>
    </div>`;
}

function renderStatTiles(status, incidentCount) {
  const tiles = [
    {
      icon: "check",
      cls: status.ok ? "green" : "",
      value: status.ok ? "All good" : "Needs attention",
      label: "System status",
      tooltip: "Whether your Mac looks like it's behaving normally right now.",
    },
    {
      icon: "layers",
      cls: "blue",
      value: status.buffered_events ?? 0,
      label: "Remembered events",
      tooltip: "Activity from the last ~5 minutes, kept ready as evidence if something breaks.",
    },
    {
      icon: "activity",
      cls: "peach",
      value: incidentCount,
      label: "Problems investigated",
      tooltip: "How many times Black Box has caught a problem and explained it.",
    },
    {
      icon: "cube",
      cls: "",
      value: (status.top_processes || []).length,
      label: "Apps being watched",
      tooltip: "Processes currently showing up in the resource-usage snapshot.",
    },
  ];
  document.getElementById("stat-grid").innerHTML = tiles
    .map(
      (t) => `
      <div class="stat-tile" title="${t.tooltip}">
        <div class="stat-icon ${t.cls}">${ICONS[t.icon]}</div>
        <div>
          <div class="stat-value">${t.value}</div>
          <div class="stat-label">${t.label}</div>
        </div>
      </div>`
    )
    .join("");
}

function renderSparkline() {
  const svg = document.getElementById("sparkline");
  if (cpuHistory.length < 2) {
    svg.innerHTML = "";
    return;
  }
  const max = Math.max(100, ...cpuHistory);
  const stepX = 300 / (HISTORY_LEN - 1);
  const points = cpuHistory
    .map((v, i) => {
      const x = i * stepX;
      const y = 38 - (v / max) * 36;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const last = cpuHistory[cpuHistory.length - 1];
  svg.innerHTML = `
    <polyline points="${points}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    <circle cx="${(cpuHistory.length - 1) * stepX}" cy="${(38 - (last / max) * 36).toFixed(1)}" r="3" fill="var(--accent)" />
  `;
}

async function refreshStatus() {
  const res = await fetch("/api/status");
  const status = await res.json();

  const pill = document.getElementById("status-pill");
  pill.textContent = status.ok ? "Everything OK" : "Needs attention";
  pill.className = "pill " + (status.ok ? "pill-ok" : "pill-bad");

  document.getElementById("gauges").innerHTML =
    renderGauge("CPU", status.cpu_percent, "How hard your processors are working right now.") +
    renderGauge("Memory", status.memory_percent, "How much of your RAM is currently in use.");

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
