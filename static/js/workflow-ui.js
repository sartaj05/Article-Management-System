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
      const state = step.state === 'current' || step.current ? "is-current" : (step.state === 'complete' || step.complete ? "is-complete" : "");
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
    button.disabled = true;
    try {
      const token = await WorkspaceUI.ensureAccess();
      const response = await fetch(`/articles/api/v2/articles/${button.dataset.id}/${action}/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) { const data = await response.json(); throw new Error(data.detail || "Workflow action failed."); }
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      button.setAttribute("aria-label", error.message);
      window.alert(error.message);
    }
  });

  async function request(url, options = {}) {
    const access = await WorkspaceUI.ensureAccess();
    const csrf = document.cookie.split('; ').find(item => item.startsWith('csrftoken='))?.slice(10);
    const response = await fetch(url, { ...options, headers: {
      Authorization: `Bearer ${access}`,
      'Content-Type': 'application/json', ...(csrf ? {'X-CSRFToken': decodeURIComponent(csrf)} : {}), ...options.headers,
    }});
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new Error(data?.detail || data?.error || JSON.stringify(data));
    return data;
  }

  async function allArticles() {
    const articles = [];
    let page = 1, data;
    do {
      data = await request(`/articles/search/?page=${page++}`);
      articles.push(...data.articles);
    } while (page <= data.total_pages);
    return articles;
  }

  function createPagination({container, onPage, pageSize = 10, label = 'items'}) {
    let items = [];
    let currentPage = 1;

    function render() {
      const total = items.length;
      const pages = Math.max(1, Math.ceil(total / pageSize));
      currentPage = Math.min(Math.max(currentPage, 1), pages);
      const offset = (currentPage - 1) * pageSize;
      onPage(items.slice(offset, offset + pageSize), {page: currentPage, pages, total, pageSize, offset});
      if (!container) return;
      container.innerHTML = total <= pageSize ? (total ? `<span class="table-pagination__summary">${total} ${label}</span>` : '') : `
        <span class="table-pagination__summary">${offset + 1}–${Math.min(offset + pageSize, total)} of ${total} ${label}</span>
        <div class="table-pagination__controls">
          <button type="button" class="button button--secondary button--small" data-pager-page="1" ${currentPage === 1 ? 'disabled' : ''} aria-label="First page">«</button>
          <button type="button" class="button button--secondary button--small" data-pager-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>
          <span aria-current="page">Page ${currentPage} of ${pages}</span>
          <button type="button" class="button button--secondary button--small" data-pager-page="${currentPage + 1}" ${currentPage === pages ? 'disabled' : ''}>Next</button>
          <button type="button" class="button button--secondary button--small" data-pager-page="${pages}" ${currentPage === pages ? 'disabled' : ''} aria-label="Last page">»</button>
        </div>`;
    }

    container?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-pager-page]');
      if (!button || button.disabled) return;
      currentPage = Number(button.dataset.pagerPage) || 1;
      render();
    });

    return {
      setItems(nextItems) { items = Array.isArray(nextItems) ? nextItems : []; currentPage = 1; render(); },
      refresh() { render(); },
      getPage() { return currentPage; },
    };
  }

  function createTablePagination({container, paginationContainer, pageSize = 10, label = 'items'}) {
    let rows = [];
    let currentPage = 1;

    function render() {
      const filtered = rows.filter((row) => row.dataset.searchMatch !== '0');
      const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
      currentPage = Math.min(Math.max(currentPage, 1), pages);
      const offset = (currentPage - 1) * pageSize;
      const visible = new Set(filtered.slice(offset, offset + pageSize));
      rows.forEach((row) => { row.hidden = !visible.has(row); });
      if (!paginationContainer) return;
      paginationContainer.innerHTML = filtered.length <= pageSize
        ? (filtered.length ? '<span class="table-pagination__summary">' + filtered.length + ' ' + label + '</span>' : '')
        : '<span class="table-pagination__summary">' + (offset + 1) + '–' + Math.min(offset + pageSize, filtered.length) + ' of ' + filtered.length + ' ' + label + '</span>' +
          '<div class="table-pagination__controls">' +
          '<button type="button" class="button button--secondary button--small" data-pager-page="1" ' + (currentPage === 1 ? 'disabled' : '') + ' aria-label="First page">«</button>' +
          '<button type="button" class="button button--secondary button--small" data-pager-page="' + (currentPage - 1) + '" ' + (currentPage === 1 ? 'disabled' : '') + '>Previous</button>' +
          '<span aria-current="page">Page ' + currentPage + ' of ' + pages + '</span>' +
          '<button type="button" class="button button--secondary button--small" data-pager-page="' + (currentPage + 1) + '" ' + (currentPage === pages ? 'disabled' : '') + '>Next</button>' +
          '<button type="button" class="button button--secondary button--small" data-pager-page="' + pages + '" ' + (currentPage === pages ? 'disabled' : '') + ' aria-label="Last page">»</button>' +
          '</div>';
    }

    paginationContainer?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-pager-page]');
      if (!button || button.disabled) return;
      currentPage = Number(button.dataset.pagerPage) || 1;
      render();
    });

    return {
      refresh() {
        rows = container ? [...container.querySelectorAll('tbody tr')] : [];
        render();
      },
      reset() {
        currentPage = 1;
        this.refresh();
      },
    };
  }

  async function editArticle(id, onSave) {
    try {
      const article = await request(`/articles/api/v2/articles/${id}/`);
      document.getElementById('workflow-edit-modal')?.remove();
      const modal = document.createElement('div');
      modal.id = 'workflow-edit-modal'; modal.className = 'modal'; modal.style.display = 'flex';
      modal.setAttribute('role', 'dialog'); modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-label', 'Edit article');
      modal.innerHTML = `<div class="modal-content"><h2>Edit article</h2><form>
        <label>Title<input name="title" required minlength="10" maxlength="35" value="${escapeHtml(article.title)}"></label>
        <label>Subtitle<input name="subtitle" maxlength="50" value="${escapeHtml(article.subtitle)}"></label>
        <label>Content<textarea name="content" required>${escapeHtml(article.content)}</textarea></label>
        <label>Tags<input name="tags" maxlength="255" value="${escapeHtml(article.tags)}"></label>
        <button type="submit">Save changes</button><button type="button" data-cancel>Cancel</button>
        <p role="status"></p></form></div>`;
      document.body.appendChild(modal);
      const trigger = document.activeElement;
      const close = () => { modal.remove(); trigger?.focus(); };
      modal.querySelector('[data-cancel]').onclick = close;
      modal.addEventListener('keydown', event => {
        if (event.key === 'Escape') close();
        if (event.key === 'Tab') {
          const items = [...modal.querySelectorAll('input,textarea,button')];
          if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1).focus(); }
          else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0].focus(); }
        }
      });
      modal.querySelector('input').focus();
      modal.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        const button = modal.querySelector('[type="submit"]'); button.disabled = true;
        try {
          await request(`/articles/api/v2/articles/${id}/`, {method: 'PATCH', body: JSON.stringify(Object.fromEntries(new FormData(event.target)))});
          close(); await onSave();
        } catch (error) { modal.querySelector('[role="status"]').textContent = error.message; }
        finally { button.disabled = false; }
      };
    } catch (error) { window.alert(error.message); }
  }

  window.WorkflowUI = { escapeHtml, statusBadge, timeline, actionButtons, request, allArticles, createPagination, createTablePagination, editArticle };
})(window);
