function escapeHtmlShared(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

async function refreshSidebar() {
  try {
    const [statusRes, incidentsRes] = await Promise.all([fetch("/api/status"), fetch("/api/incidents")]);
    const status = await statusRes.json();
    const incidents = await incidentsRes.json();

    const dot = document.getElementById("sidebar-status-dot");
    const text = document.getElementById("sidebar-status-text");
    if (dot && text) {
      dot.className = "status-dot " + (status.ok ? "ok" : "bad");
      text.textContent = status.ok ? "All systems normal" : "Needs attention";
    }

    const container = document.getElementById("sidebar-incidents");
    if (container) {
      container.innerHTML = "";
      const currentId = typeof INCIDENT_ID !== "undefined" ? INCIDENT_ID : null;
      for (const incident of incidents.slice(0, 8)) {
        const a = document.createElement("a");
        a.href = `/incidents/${incident.incident_id}`;
        a.className = "sidebar-incident" + (incident.incident_id === currentId ? " active" : "");
        const dotColor = incident.analysis_succeeded ? "#3ddc84" : "#f3c14b";
        a.innerHTML = `<span class="dot" style="background:${dotColor}"></span>${escapeHtmlShared(incident.trigger_reason)}`;
        container.appendChild(a);
      }
      if (incidents.length === 0) {
        container.innerHTML = '<div class="hint" style="padding:6px 8px;">None yet</div>';
      }
    }
  } catch (err) {
    // Dashboard/incident page still works without the sidebar refreshing.
  }
}

refreshSidebar();
setInterval(refreshSidebar, 5000);
