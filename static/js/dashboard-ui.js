(function () {
  "use strict";
  const body = document.body;
  const toggle = document.querySelector(".sidebar-toggle");
  const sidebar = document.querySelector(".sidebar");
  if (!toggle || !sidebar) return;
  toggle.addEventListener("click", () => {
    const open = body.classList.toggle("sidebar-open");
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close dashboard navigation" : "Open dashboard navigation");
  });
  sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
    body.classList.remove("sidebar-open");
    toggle.setAttribute("aria-expanded", "false");
  }));

  document.querySelectorAll("[data-dashboard-logout]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      ["access_token", "refresh_token", "user", "lastActivePage"].forEach((key) => localStorage.removeItem(key));
      window.location.replace("/");
    });
  });

  document.getElementById("top-create-article")?.addEventListener("click", (event) => {
    event.preventDefault();
    document.getElementById("create-article-link")?.click();
  });
  document.getElementById("top-editor-home")?.addEventListener("click", (event) => {
    event.preventDefault();
    document.getElementById("home-btn")?.click();
  });
})();
