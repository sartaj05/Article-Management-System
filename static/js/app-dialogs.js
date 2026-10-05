(function () {
  "use strict";

  let activeResolve = null;

  function ensureDialog() {
    let dialog = document.querySelector("[data-app-dialog]");
    if (dialog) return dialog;
    if (!document.body) return null;

    dialog = document.createElement("div");
    dialog.className = "app-dialog";
    dialog.dataset.appDialog = "";
    dialog.dataset.dialogKind = "info";
    dialog.hidden = true;
    dialog.setAttribute("role", "alertdialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.innerHTML = `
      <section class="app-dialog__card" role="document">
        <header class="app-dialog__header">
          <span class="app-dialog__icon" data-dialog-icon aria-hidden="true">i</span>
          <div>
            <p class="app-dialog__eyebrow" data-dialog-eyebrow>Article Studio</p>
            <h2 class="app-dialog__title" data-dialog-title>Notice</h2>
          </div>
          <button type="button" class="app-dialog__close" data-dialog-close aria-label="Close dialog">&times;</button>
        </header>
        <div class="app-dialog__body">
          <p class="app-dialog__message" data-dialog-message></p>
          <div class="app-dialog__actions">
            <button type="button" class="app-dialog__button app-dialog__button--cancel" data-dialog-cancel>Cancel</button>
            <button type="button" class="app-dialog__button app-dialog__button--confirm" data-dialog-confirm>Okay</button>
          </div>
        </div>
      </section>`;
    document.body.appendChild(dialog);

    dialog.querySelector("[data-dialog-close]").addEventListener("click", function () {
      finish(false);
    });
    dialog.querySelector("[data-dialog-cancel]").addEventListener("click", function () {
      finish(false);
    });
    dialog.querySelector("[data-dialog-confirm]").addEventListener("click", function () {
      finish(true);
    });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) finish(false);
    });
    return dialog;
  }

  function finish(result) {
    const dialog = document.querySelector("[data-app-dialog]");
    if (dialog) dialog.hidden = true;
    if (activeResolve) {
      const resolve = activeResolve;
      activeResolve = null;
      resolve(result);
    }
  }

  function openDialog(message, options) {
    const dialog = ensureDialog();
    if (!dialog) return Promise.resolve(options && options.confirm ? false : undefined);

    if (activeResolve) finish(false);
    const confirmMode = Boolean(options && options.confirm);
    const kind = options && options.kind ? options.kind : "info";
    dialog.dataset.dialogKind = kind;
    dialog.querySelector("[data-dialog-icon]").textContent = kind === "error" ? "!" : kind === "success" ? "✓" : confirmMode ? "?" : "i";
    dialog.querySelector("[data-dialog-eyebrow]").textContent = confirmMode ? "Please confirm" : "Article Studio";
    dialog.querySelector("[data-dialog-title]").textContent = options && options.title ? options.title : confirmMode ? "Confirm action" : kind === "error" ? "Something went wrong" : "Notice";
    dialog.querySelector("[data-dialog-message]").textContent = String(message || "");
    dialog.querySelector("[data-dialog-cancel]").hidden = !confirmMode;
    dialog.querySelector("[data-dialog-confirm]").textContent = confirmMode ? "Continue" : "Okay";
    dialog.hidden = false;
    dialog.querySelector(confirmMode ? "[data-dialog-cancel]" : "[data-dialog-confirm]").focus();

    return new Promise(function (resolve) {
      activeResolve = resolve;
    });
  }

  window.appAlert = function (message, options) {
    openDialog(message, options || {});
  };
  window.appConfirm = function (message, options) {
    return openDialog(message, Object.assign({}, options || {}, { confirm: true }));
  };

  // Keep legacy call sites inside the application on the styled dialog.
  window.alert = window.appAlert;
  window.confirm = function (message) {
    window.appConfirm(message);
    return false;
  };
})();
