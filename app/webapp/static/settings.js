document.getElementById("icon-privacy").innerHTML = ICONS.shield;

const TOGGLE_META = {
  screenshots: { icon: "camera", title: "Screenshots" },
  terminal: { icon: "terminal", title: "Terminal commands" },
};

function renderToggleRow(key, state) {
  const meta = TOGGLE_META[key] || { icon: "sliders", title: key };
  const row = document.createElement("div");
  row.className = "settings-row";
  row.innerHTML = `
    <div class="settings-row-icon">${ICONS[meta.icon] || ICONS.sliders}</div>
    <div class="settings-row-main">
      <div class="settings-row-title">${escapeHtml(meta.title)}</div>
      <div class="settings-row-desc">${escapeHtml(state.description)}</div>
      <div class="settings-row-status" data-status></div>
    </div>
    <button class="toggle-switch${state.enabled ? " on" : ""}" data-key="${key}" role="switch" aria-checked="${state.enabled}"></button>
  `;
  updateStatusLine(row, state.enabled);
  return row;
}

function updateStatusLine(row, enabled) {
  row.querySelector("[data-status]").textContent = enabled ? "Currently on" : "Currently off";
}

async function loadSettings() {
  const res = await fetch("/api/settings");
  const settings = await res.json();
  const list = document.getElementById("settings-list");
  list.innerHTML = "";

  const keys = Object.keys(settings);
  if (keys.length === 0) {
    list.innerHTML = '<p class="hint">Nothing toggleable here yet.</p>';
    return;
  }

  for (const key of keys) {
    list.appendChild(renderToggleRow(key, settings[key]));
  }

  list.querySelectorAll(".toggle-switch").forEach((btn) => {
    btn.addEventListener("click", () => toggleSetting(btn));
  });
}

async function toggleSetting(btn) {
  const key = btn.dataset.key;
  const nextValue = !btn.classList.contains("on");
  btn.classList.add("disabled");

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [key]: nextValue }),
    });
    const updated = await res.json();
    const actualValue = key in updated ? updated[key] : nextValue;
    btn.classList.toggle("on", actualValue);
    btn.setAttribute("aria-checked", String(actualValue));
    updateStatusLine(btn.closest(".settings-row"), actualValue);
  } finally {
    btn.classList.remove("disabled");
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

loadSettings();
