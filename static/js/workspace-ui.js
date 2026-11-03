(function () {
  "use strict";

  const STORAGE_KEYS = ["access_token", "refresh_token", "user", "lastActivePage"];
  let initialized = false;

  // Legacy dashboard requests use the same browser session as the login form.
  if (window.jQuery) window.jQuery.ajaxPrefilter(function (options, original, xhr) {
    if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(options.type) && !options.crossDomain) {
      const token = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.slice(10);
      if (token) xhr.setRequestHeader('X-CSRFToken', decodeURIComponent(token));
    }
  });

  function clearWorkspaceSession() {
    STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key));
  }

  let refreshing;
  async function ensureAccess() {
    const access = localStorage.getItem('access_token');
    try {
      const payload = JSON.parse(atob(access.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      if (payload.exp > Date.now() / 1000 + 30) return access;
    } catch (_) { /* Request a fresh access token for an expired or missing token. */ }
    if (!refreshing) refreshing = (async () => {
      const response = await fetch('/api/token/refresh/', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({refresh: localStorage.getItem('refresh_token')}),
      });
      if (!response.ok) throw new Error('Your session expired. Sign in again to continue.');
      const data = await response.json();
      localStorage.setItem('access_token', data.access);
      return data.access;
    })().finally(() => { refreshing = null; });
    return refreshing;
  }

  let signingOut = false;
  async function signOut() {
    if (signingOut) return;
    signingOut = true;
    const csrfToken = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='))?.split('=').slice(1).join('=');
    const headers = { 'Content-Type': 'application/json', Accept: 'application/json', ...(csrfToken ? { 'X-CSRFToken': decodeURIComponent(csrfToken) } : {}) };
    try {
      const refresh = window.localStorage.getItem('refresh_token');
      let response = await fetch('/api/logout/', { method: 'POST', headers, body: JSON.stringify({ refresh }) });
      // An expired refresh token must not prevent ending a valid browser session.
      if (response.status === 400 && refresh) response = await fetch('/api/logout/', { method: 'POST', headers, body: '{}' });
      if (!response.ok) throw new Error('Unable to sign out. Please try again.');
      clearWorkspaceSession();
      window.location.replace('/');
    } catch (error) {
      window.appAlert?.(error.message || 'Unable to sign out. Please try again.', { kind: 'error', title: 'Sign out failed' });
    } finally { signingOut = false; }
  }

  // Chrome may restore an authenticated page from the back/forward cache
  // without making a new request. After logout, force those restored pages
  // through the login guard instead of displaying stale workspace content.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted && !localStorage.getItem("access_token") && !localStorage.getItem("refresh_token")) {
      window.location.replace("/login-template/");
    }
  });

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
      signOut();
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

  function createCollectionPager({ container, pagination, pageSize = 10, label = 'items', render }) {
    let items = [];
    let currentPage = 1;

    function draw() {
      const pages = Math.max(1, Math.ceil(items.length / pageSize));
      currentPage = Math.min(Math.max(currentPage, 1), pages);
      const offset = (currentPage - 1) * pageSize;
      render(items.slice(offset, offset + pageSize), { page: currentPage, pages, total: items.length, pageSize, offset });
      if (!pagination) return;
      pagination.innerHTML = items.length <= pageSize
        ? (items.length ? `<span class="feature-pagination__summary">${items.length} ${label}</span>` : '')
        : `<span class="feature-pagination__summary">${offset + 1}–${Math.min(offset + pageSize, items.length)} of ${items.length} ${label}</span>
          <div class="feature-pagination__controls">
            <button class="button button--secondary button--small" type="button" data-collection-page="1" ${currentPage === 1 ? 'disabled' : ''} aria-label="First page">«</button>
            <button class="button button--secondary button--small" type="button" data-collection-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>
            <span aria-current="page">Page ${currentPage} of ${pages}</span>
            <button class="button button--secondary button--small" type="button" data-collection-page="${currentPage + 1}" ${currentPage === pages ? 'disabled' : ''}>Next</button>
            <button class="button button--secondary button--small" type="button" data-collection-page="${pages}" ${currentPage === pages ? 'disabled' : ''} aria-label="Last page">»</button>
          </div>`;
    }

    pagination?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-collection-page]');
      if (!button || button.disabled) return;
      currentPage = Number(button.dataset.collectionPage) || 1;
      draw();
      container?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    return {
      setItems(nextItems) { items = Array.isArray(nextItems) ? nextItems : []; currentPage = 1; draw(); },
      refresh() { draw(); },
      getPage() { return currentPage; },
    };
  }

  window.WorkspaceUI = Object.freeze({ clearWorkspaceSession, ensureAccess, signOut, init, createCollectionPager });
  document.addEventListener("DOMContentLoaded", init);
})();
