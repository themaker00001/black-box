async function refreshStatus() {
  const res = await fetch("/api/status");
  const status = await res.json();

  const pill = document.getElementById("status-pill");
  pill.textContent = status.ok ? "Everything OK" : "Needs attention";
  pill.className = "pill " + (status.ok ? "pill-ok" : "pill-bad");

  setBar("cpu", status.cpu_percent);
  setBar("mem", status.memory_percent);

  const rows = document.getElementById("proc-rows");
  rows.innerHTML = "";
  for (const proc of status.top_processes || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(proc.name)}</td><td>${proc.cpu_percent.toFixed(1)}</td><td>${proc.memory_percent.toFixed(1)}</td>`;
    rows.appendChild(tr);
  }
}

function setBar(prefix, value) {
  const bar = document.getElementById(`${prefix}-bar`);
  const label = document.getElementById(`${prefix}-value`);
  if (value === null || value === undefined) {
    bar.style.width = "0%";
    label.textContent = "–";
    return;
  }
  bar.style.width = `${Math.min(value, 100)}%`;
  bar.style.background = value >= 90 ? "var(--red)" : value >= 70 ? "var(--peach)" : "linear-gradient(90deg, var(--blue), var(--accent))";
  label.textContent = `${value.toFixed(1)}%`;
}

async function refreshIncidents() {
  const res = await fetch("/api/incidents");
  const incidents = await res.json();
  const list = document.getElementById("incident-list");
  list.innerHTML = "";

  if (incidents.length === 0) {
    list.innerHTML = '<li class="incident-empty">No incidents recorded yet.</li>';
    return;
  }

  for (const incident of incidents) {
    const li = document.createElement("li");
    const badge = incident.analysis_succeeded ? "" : '<span class="badge">AI unavailable</span>';
    li.innerHTML = `<a href="/incidents/${incident.incident_id}">${escapeHtml(incident.trigger_reason)}</a>
      ${badge}
      <span class="hint">${new Date(incident.created_at).toLocaleString()}</span>`;
    list.appendChild(li);
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

refreshStatus();
refreshIncidents();
setInterval(refreshStatus, 3000);
setInterval(refreshIncidents, 5000);
