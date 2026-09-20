function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// root_cause/subject read the live theme accent so switching themes recolors
// the two most important nodes; the rest carry fixed semantic colors that
// stay meaningful (danger, info, etc.) no matter which accent is active.
function kindColor(kind) {
  if (kind === "root_cause") return cssVar("--accent");
  if (kind === "subject") return cssVar("--accent-2") || cssVar("--accent");
  return (
    { trigger: "#ff5c72", correlation: "#f3c14b", screenshot: "#4fd8c4", event: "#5b9dff" }[kind] || "#5b9dff"
  );
}
const KIND_BASE_SIZE = {
  trigger: 42,
  root_cause: 42,
  subject: 46,
  correlation: 24,
  screenshot: 24,
  event: 18,
};

let cy = null;

function wireIcons() {
  document.getElementById("icon-grid").innerHTML = ICONS.grid;
  document.getElementById("icon-chevron").innerHTML = ICONS.chevronRight;
  document.getElementById("icon-zoom-in").innerHTML = ICONS.zoomIn;
  document.getElementById("icon-zoom-out").innerHTML = ICONS.zoomOut;
  document.getElementById("icon-maximize").innerHTML = ICONS.maximize;
  document.getElementById("icon-node").innerHTML = ICONS.cube;
  document.getElementById("icon-cause").innerHTML = ICONS.lightbulb;
  document.getElementById("icon-evidence").innerHTML = ICONS.list;
  document.getElementById("icon-steps").innerHTML = ICONS.checkSquare;
  document.getElementById("icon-link").innerHTML = ICONS.link;
  document.getElementById("icon-image").innerHTML = ICONS.image;
}

async function loadIncident() {
  const res = await fetch(`/api/incidents/${INCIDENT_ID}`);
  if (!res.ok) {
    document.getElementById("meta-title").textContent = "Incident not found";
    return;
  }
  const incident = await res.json();
  renderMeta(incident);
  renderExplanation(incident);
  renderScreenshot(incident);
  renderGraph(incident.graph);
}

function renderMeta(incident) {
  document.getElementById("graph-title-text").textContent = incident.trigger_reason;
  document.getElementById("meta-title").textContent = incident.trigger_reason;
  document.getElementById("meta-sub").textContent =
    `${new Date(incident.created_at).toLocaleString()} · ${incident.trigger_name} · ` +
    `${incident.event_count} events · ${incident.model_used || "n/a"}`;
}

function renderExplanation(incident) {
  const sections = incident.analysis_sections || {};

  const rootCause = document.getElementById("root-cause-card");
  const rootCauseText = sections.most_likely_cause || "No AI analysis available.";
  rootCause.innerHTML = `<span class="icon">${ICONS.lightbulb}</span><span>${escapeHtml(rootCauseText)}</span>`;
  if (!sections.most_likely_cause) rootCause.classList.add("empty");

  const evidence = document.getElementById("evidence-card");
  if (sections.supporting_evidence && sections.supporting_evidence.length) {
    evidence.innerHTML = `<ul>${sections.supporting_evidence.map((e) => `<li>${escapeHtml(e)}</li>`).join("")}</ul>`;
  } else {
    evidence.textContent = "No specific evidence cited.";
    evidence.classList.add("empty");
  }

  const nextSteps = document.getElementById("next-steps-card");
  if (sections.next_steps && sections.next_steps.length) {
    nextSteps.innerHTML = `<ul>${sections.next_steps
      .map((s) => `<li><span class="icon">${ICONS.checkSquare}</span>${escapeHtml(s)}</li>`)
      .join("")}</ul>`;
  } else {
    nextSteps.textContent = "No next steps suggested.";
    nextSteps.classList.add("empty");
  }

  const chipRow = document.getElementById("correlation-chips");
  const correlations = incident.correlations || [];
  if (correlations.length) {
    chipRow.innerHTML = correlations
      .map((c) => `<span class="chip" title="${escapeHtml(c.description)}"><span class="dot"></span>${escapeHtml(c.kind.replace(/_/g, " "))}</span>`)
      .join("");
  } else {
    document.getElementById("correlations-section").style.display = "none";
  }
}

function renderScreenshot(incident) {
  if (!incident.screenshot_url) return;
  document.getElementById("screenshot-section").style.display = "";
  document.getElementById("screenshot-wrap").innerHTML =
    `<a href="${incident.screenshot_url}" target="_blank" rel="noopener"><img src="${incident.screenshot_url}" alt="screenshot" /></a>`;
}

function renderGraph(graph) {
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [...graph.nodes, ...graph.edges],
    minZoom: 0.2,
    maxZoom: 3,
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-wrap": "wrap",
          "text-max-width": "90px",
          "font-size": "10px",
          color: cssVar("--text") || "#f2f2f4",
          "text-valign": "bottom",
          "text-margin-y": 6,
          "text-opacity": 0.9,
          width: (n) => sizeFor(n),
          height: (n) => sizeFor(n),
          "background-color": (n) => kindColor(n.data("kind")),
          "border-width": 0,
          "overlay-color": (n) => kindColor(n.data("kind")),
          "overlay-opacity": 0.28,
          "overlay-padding": 9,
          "overlay-shape": "ellipse",
          "transition-property": "opacity",
          "transition-duration": "150ms",
        },
      },
      {
        selector: "edge",
        style: {
          width: 1,
          "line-color": cssVar("--border") || "#232326",
          "target-arrow-color": cssVar("--border") || "#232326",
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.7,
          "curve-style": "bezier",
          opacity: 0.6,
          "transition-property": "opacity",
          "transition-duration": "150ms",
        },
      },
      { selector: ".faded", style: { opacity: 0.1 } },
      { selector: ".highlighted", style: { opacity: 1 } },
      {
        selector: "node.highlighted",
        style: { "border-width": 2, "border-color": "#fff", "border-opacity": 0.7 },
      },
    ],
    layout: {
      name: "cose",
      animate: false,
      nodeRepulsion: 22000,
      nodeOverlap: 40,
      idealEdgeLength: 150,
      edgeElasticity: 80,
      gravity: 30,
      numIter: 2000,
      fit: true,
      padding: 50,
    },
  });

  const degree = {};
  cy.nodes().forEach((n) => (degree[n.id()] = n.degree()));
  cy.nodes().forEach((n) => n.data("_degree", degree[n.id()] || 0));
  cy.style().update();

  cy.on("mouseover", "node", (evt) => {
    const neighborhood = evt.target.closedNeighborhood();
    cy.elements().difference(neighborhood).addClass("faded");
    neighborhood.addClass("highlighted");
  });
  cy.on("mouseout", "node", () => {
    cy.elements().removeClass("faded").removeClass("highlighted");
  });

  cy.on("tap", "node", (evt) => {
    const data = evt.target.data();
    document.getElementById("node-detail").textContent = data.detail || "(no detail)";
  });

  pulseNode(cy.getElementById("trigger"));
}

function pulseNode(node) {
  if (!node || node.empty()) return;
  const grow = () => node.animate({ style: { "overlay-padding": 16, "overlay-opacity": 0.45 } }, { duration: 900, easing: "ease-in-out", complete: shrink });
  const shrink = () => node.animate({ style: { "overlay-padding": 8, "overlay-opacity": 0.24 } }, { duration: 900, easing: "ease-in-out", complete: grow });
  grow();
}

function sizeFor(node) {
  const base = KIND_BASE_SIZE[node.data("kind")] || 20;
  const degree = node.data("_degree") || 0;
  return base + Math.min(degree * 3, 18);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

document.getElementById("toggle-panel").addEventListener("click", () => {
  const shell = document.getElementById("incident-shell");
  shell.classList.toggle("panel-collapsed");
  document.getElementById("toggle-panel").classList.toggle("flipped", shell.classList.contains("panel-collapsed"));
  setTimeout(() => {
    if (cy) {
      cy.resize();
      cy.fit(undefined, 40);
    }
  }, 260);
});

document.getElementById("zoom-in").addEventListener("click", () => cy && cy.zoom(cy.zoom() * 1.25));
document.getElementById("zoom-out").addEventListener("click", () => cy && cy.zoom(cy.zoom() / 1.25));
document.getElementById("zoom-fit").addEventListener("click", () => cy && cy.fit(undefined, 40));

wireIcons();
loadIncident();
