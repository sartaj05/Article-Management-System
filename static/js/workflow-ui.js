(function (window) {
  "use strict";

  const labels = { draft: "Draft", submitted: "Submitted", approved: "Approved", rejected: "Rejected", published: "Published" };

  function escapeHtml(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function statusBadge(status) {
    const key = String(status || "draft").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    return `<span class="status-badge status-badge--${key}">${escapeHtml(labels[key] || status || "Draft")}</span>`;
  }

  function timeline(steps) {
    if (!Array.isArray(steps) || !steps.length) return "";
    return `<ol class="workflow-timeline" aria-label="Article workflow">${steps.map((step) => {
      const state = step.current ? "is-current" : (step.complete ? "is-complete" : "");
      return `<li class="workflow-timeline__item ${state}"><span class="workflow-timeline__dot" aria-hidden="true"></span><span>${escapeHtml(step.label || step.status)}</span></li>`;
    }).join("")}</ol>`;
  }

  function actionButtons(actions, articleId) {
    if (!Array.isArray(actions) || !actions.length) return "";
    return `<div class="workflow-actions" aria-label="Available workflow actions">${actions.map((action) => {
      const name = typeof action === "string" ? action : action.name || action.action;
      const label = typeof action === "string" ? action : action.label || name;
      return `<button type="button" class="table-action workflow-action" data-action="${escapeHtml(name)}" data-id="${articleId}">${escapeHtml(label)}</button>`;
    }).join("")}</div>`;
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".workflow-action");
    if (!button) return;
    const action = button.dataset.action;
    if (action === "schedule" || action === "review") {
      button.title = action === "schedule" ? "Use the scheduling form to choose a publication time." : "Use the review controls for this article.";
      return;
    }
    const token = window.localStorage.getItem("access_token");
    button.disabled = true;
    try {
      const response = await fetch(`/articles/api/v2/articles/${button.dataset.id}/${action}/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) throw new Error("Workflow action failed.");
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      button.setAttribute("aria-label", error.message);
    }
  });

  window.WorkflowUI = { escapeHtml, statusBadge, timeline, actionButtons };
})(window);
