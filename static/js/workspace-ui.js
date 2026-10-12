(function () {
  "use strict";

  const STORAGE_KEYS = ["access_token", "refresh_token", "user", "lastActivePage"];
  let initialized = false;

  function clearWorkspaceSession() {
    STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key));
  }

  function init() {
    if (initialized) return;
    initialized = true;
    const body = document.body;
    const toggle = document.querySelector(".sidebar-toggle");
    const sidebar = document.querySelector(".sidebar");

    if (toggle && sidebar) {
      toggle.addEventListener("click", () => {
        const open = body.classList.toggle("sidebar-open");
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Close dashboard navigation" : "Open dashboard navigation");
      });
      sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
        body.classList.remove("sidebar-open");
        toggle.setAttribute("aria-expanded", "false");
      }));
    }

    document.querySelectorAll("[data-dashboard-logout]").forEach((link) => link.addEventListener("click", (event) => {
      event.preventDefault();
      clearWorkspaceSession();
      window.location.replace("/");
    }));

    document.getElementById("top-create-article")?.addEventListener("click", (event) => {
      event.preventDefault();
      document.getElementById("create-article-link")?.click();
    });
    document.getElementById("top-editor-home")?.addEventListener("click", (event) => {
      event.preventDefault();
      document.getElementById("home-btn")?.click();
    });
  }

  window.WorkspaceUI = Object.freeze({ clearWorkspaceSession, init });
  document.addEventListener("DOMContentLoaded", init);
})();
