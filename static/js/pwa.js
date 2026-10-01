(function () {
  "use strict";
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/js/service-worker.js").catch(() => {});
  });

  let installPrompt;
  const installButton = document.querySelector("[data-install-app]");
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    installButton?.removeAttribute("hidden");
  });

  installButton?.addEventListener("click", async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    installButton.setAttribute("hidden", "hidden");
  });
})();
