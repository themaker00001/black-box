const THEMES = [
  { id: "mono", label: "Monochrome", color: "#e8e8ec" },
  { id: "violet", label: "Violet", color: "#a78bfa" },
  { id: "blue", label: "Blue", color: "#4f9dff" },
  { id: "green", label: "Green", color: "#34e0a1" },
  { id: "rose", label: "Rose", color: "#ff6f91" },
  { id: "amber", label: "Amber", color: "#ffb545" },
];
const THEME_STORAGE_KEY = "blackbox-theme";

function applyTheme(themeId) {
  if (themeId === "mono") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = themeId;
  }
}

function renderThemeSwitcher() {
  const container = document.getElementById("theme-switcher");
  if (!container) return;
  let current = "mono";
  try {
    current = localStorage.getItem(THEME_STORAGE_KEY) || "mono";
  } catch (err) {
    // localStorage unavailable (private browsing, etc.) — fall back to default silently.
  }

  container.innerHTML = THEMES.map(
    (t) =>
      `<button class="theme-swatch${t.id === current ? " active" : ""}" style="--swatch-color:${t.color}" data-theme-id="${t.id}" title="${t.label}"></button>`
  ).join("");

  container.querySelectorAll(".theme-swatch").forEach((btn) => {
    btn.addEventListener("click", () => {
      const themeId = btn.dataset.themeId;
      applyTheme(themeId);
      try {
        localStorage.setItem(THEME_STORAGE_KEY, themeId);
      } catch (err) {
        // Nothing to persist to; the choice still applies for this page view.
      }
      container.querySelectorAll(".theme-swatch").forEach((b) => b.classList.toggle("active", b === btn));
    });
  });
}

renderThemeSwitcher();
