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
})();
