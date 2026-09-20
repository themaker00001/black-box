const KIND_STYLE = {
  trigger: { color: "#e0503a", shape: "diamond" },
  root_cause: { color: "#5b8cff", shape: "star" },
  correlation: { color: "#e0a72b", shape: "round-rectangle" },
  screenshot: { color: "#8b93a3", shape: "round-rectangle" },
  event: { color: "#2fbf71", shape: "ellipse" },
};

async function loadIncident() {
  const res = await fetch(`/api/incidents/${INCIDENT_ID}`);
  if (!res.ok) {
    document.getElementById("incident-meta").textContent = "Incident not found.";
    return;
  }
  const incident = await res.json();
  renderMeta(incident);
  renderAnalysis(incident);
  renderScreenshot(incident);
  renderGraph(incident.graph);
}

function renderMeta(incident) {
  document.getElementById("incident-meta").innerHTML = `
    <div><strong>${escapeHtml(incident.trigger_reason)}</strong></div>
    <div class="hint">${new Date(incident.created_at).toLocaleString()} · ${incident.trigger_name}</div>
    <div class="hint">${incident.event_count} events · model: ${escapeHtml(incident.model_used || "n/a")}</div>
  `;
}

function renderAnalysis(incident) {
  const el = document.getElementById("analysis");
  el.innerHTML = window.marked ? marked.parse(incident.analysis_text || "") : escapeHtml(incident.analysis_text || "");
}

function renderScreenshot(incident) {
  const wrap = document.getElementById("screenshot-wrap");
  if (incident.screenshot_url) {
    wrap.innerHTML = `<h3>Screen at incident time</h3><img src="${incident.screenshot_url}" alt="screenshot" />`;
  }
}

function renderGraph(graph) {
  const cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [...graph.nodes, ...graph.edges],
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-wrap": "wrap",
          "text-max-width": "90px",
          "font-size": "10px",
          color: "#e6e8ec",
          "text-valign": "bottom",
          "text-margin-y": 6,
          width: 34,
          height: 34,
          "background-color": (n) => (KIND_STYLE[n.data("kind")] || {}).color || "#5b8cff",
          shape: (n) => (KIND_STYLE[n.data("kind")] || {}).shape || "ellipse",
          "border-width": 2,
          "border-color": "#0f1115",
        },
      },
      {
        selector: "edge",
        style: {
          width: 1.5,
          "line-color": "#262c38",
          "target-arrow-color": "#262c38",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
        },
      },
      { selector: "node[kind='trigger']", style: { width: 46, height: 46 } },
      { selector: "node[kind='root_cause']", style: { width: 46, height: 46 } },
    ],
    layout: { name: "cose", animate: false, padding: 30 },
  });

  cy.on("tap", "node", (evt) => {
    const data = evt.target.data();
    document.getElementById("node-detail").textContent = data.detail || "(no detail)";
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

loadIncident();
