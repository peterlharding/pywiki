/* PyWiki — client-side utilities */

"use strict";

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
