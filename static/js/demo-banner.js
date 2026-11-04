(function () {
  "use strict";
  const banner = document.querySelector("[data-demo-banner]");
  const close = banner?.querySelector("[data-demo-banner-close]");
  if (!banner || !close) return;
  if (window.localStorage.getItem("article-studio-demo-banner-dismissed") === "1") {
    banner.hidden = true;
    return;
  }
  close.addEventListener("click", () => {
    banner.hidden = true;
    window.localStorage.setItem("article-studio-demo-banner-dismissed", "1");
  });
})();
