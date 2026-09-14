/* PyWiki — client-side utilities */

"use strict";

// ── Dark mode toggle ───────────────────────────────────────────────────────

(function () {
  var root = document.documentElement;
  var btn  = document.getElementById("theme-toggle");
  if (!btn) return;

  function currentTheme() {
    var stored = localStorage.getItem("pywiki-theme");
    if (stored) return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
    btn.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  }

  applyTheme(currentTheme());

  btn.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    localStorage.setItem("pywiki-theme", next);
    applyTheme(next);
  });
})();

// ── Layout width toggle ────────────────────────────────────────────────────

(function () {
  var root = document.documentElement;
  var btn  = document.getElementById("width-toggle");
  if (!btn || !window.PyWiki) return;
  // Editor and other wide pages always use the full width; the toggle would do nothing
  if (document.body.matches(".editor-page, .wide-page")) return;

  // Resolves --limit-w (px, rem, % ...) to pixels
  var probe = document.createElement("div");
  probe.style.cssText = "position:absolute;visibility:hidden;height:0;width:var(--limit-w)";
  document.body.appendChild(probe);

  function update() {
    // Recalculate: the window may have moved to a screen of a different size
    root.style.setProperty("--limit-w", window.PyWiki.limitWidth());
    var full = root.getAttribute("data-width") === "full";
    // Only offer the toggle when the window is wider than the limited layout
    btn.hidden = root.clientWidth <= probe.offsetWidth;
    btn.title = full ? "Use limited width" : "Use full width";
    btn.setAttribute("aria-pressed", String(full));
  }

  btn.addEventListener("click", function () {
    var next = root.getAttribute("data-width") === "full" ? "limited" : "full";
    try { localStorage.setItem("pywiki-width", next); } catch (e) { /* storage blocked */ }
    root.setAttribute("data-width", next);
    update();
  });

  var pending = false;
  window.addEventListener("resize", function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; update(); });
  });

  update();
})();

// ── Confirm dangerous actions ──────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // Auto-dismiss alerts after 6 seconds
  document.querySelectorAll(".alert").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.5s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 500);
    }, 6000);
  });

  // Highlight current nav link
  var path = window.location.pathname;
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    if (a.getAttribute("href") === path) {
      a.style.fontWeight = "bold";
      a.style.color = "#fff";
    }
  });

  // Format badge tooltip
  document.querySelectorAll(".badge-markdown").forEach(function (el) {
    el.title = "Content written in Markdown";
  });
  document.querySelectorAll(".badge-rst").forEach(function (el) {
    el.title = "Content written in reStructuredText (RST)";
  });
});
