(function () {
  "use strict";
  const init = () => {
    const banner = document.querySelector("[data-demo-banner]");
    const close = banner?.querySelector("[data-demo-banner-close]");
    if (!banner || !close || banner.dataset.initialized === "true") return;
    banner.dataset.initialized = "true";
    try {
      if (window.localStorage.getItem("article-studio-demo-banner-dismissed") === "1") {
        banner.hidden = true;
        return;
      }
    } catch (_) {}
    close.addEventListener("click", (event) => {
      event.preventDefault();
      banner.hidden = true;
      try { window.localStorage.setItem("article-studio-demo-banner-dismissed", "1"); } catch (_) {}
    });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
