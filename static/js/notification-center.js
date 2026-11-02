(function () {
  const list = document.getElementById('notification-list');
  const status = document.getElementById('notification-status');
  const token = localStorage.getItem('access_token');
  const pagination = document.getElementById('notification-pagination');
  let currentPage = 1;
  const headers = () => ({ Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) });
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));

  async function loadNotifications(page = currentPage) {
    currentPage = page;
    status.textContent = 'Loading notifications…';
    try {
      const response = await fetch('/articles/api/v2/notifications/?page=' + page + '&page_size=10', { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Unable to load notifications.');
      const items = Array.isArray(payload) ? payload : (payload.results || []);
      list.innerHTML = items.length ? items.map(template).join('') : '<div class="feature-empty">You are all caught up.</div>';
      status.textContent = `${items.filter((item) => !item.is_read).length} unread notification${items.filter((item) => !item.is_read).length === 1 ? '' : 's'}`;
      renderPagination(payload);
      list.querySelectorAll('[data-read-id]').forEach((button) => button.addEventListener('click', () => markRead(button.dataset.readId)));
    } catch (error) { list.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; status.textContent = 'Notifications unavailable'; }
  }

  function renderPagination(payload) {
    const count = Number(payload.count || 0);
    const pageSize = Number(payload.results?.length || 10);
    const pages = Math.max(1, Math.ceil(count / pageSize));
    pagination.innerHTML = pages <= 1 ? '' : `<div class="feature-pagination__controls"><button class="button button--secondary button--small" type="button" data-page="1" ${currentPage === 1 ? 'disabled' : ''}>First</button><button class="button button--secondary button--small" type="button" data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>Previous</button><span aria-current="page">Page ${currentPage} of ${pages}</span><button class="button button--secondary button--small" type="button" data-page="${currentPage + 1}" ${currentPage >= pages ? 'disabled' : ''}>Next</button><button class="button button--secondary button--small" type="button" data-page="${pages}" ${currentPage >= pages ? 'disabled' : ''}>Last</button></div>`;
  }

  function template(item) {
    return `<article class="notification-item ${item.is_read ? '' : 'notification-item--unread'}"><div class="notification-item__icon">${item.is_read ? '✓' : '!'}</div><div class="notification-item__body"><strong>${escapeHtml(item.notification_type)}</strong><p>${escapeHtml(item.message)}</p><small>${new Date(item.created_at).toLocaleString()}</small></div>${item.is_read ? '' : `<button class="button button--secondary button--small" type="button" data-read-id="${item.id}">Mark read</button>`}</article>`;
  }

  async function markRead(id) {
    const response = await fetch(`/articles/api/v2/notifications/${id}/read/`, { method: 'PATCH', headers: Object.assign(headers(), { 'Content-Type': 'application/json' }), credentials: 'same-origin' });
    if (response.ok) loadNotifications(currentPage); else status.textContent = 'Notification could not be marked as read.';
  }
  async function markAllRead() {
    const response = await fetch('/articles/api/v2/notifications/read-all/', { method: 'PATCH', headers: Object.assign(headers(), { 'Content-Type': 'application/json' }), credentials: 'same-origin' });
    if (response.ok) loadNotifications(currentPage); else status.textContent = 'Notifications could not be marked as read.';
  }
  document.getElementById('refresh-notifications').addEventListener('click', () => loadNotifications(currentPage));
  document.getElementById('mark-all-notifications-read')?.addEventListener('click', markAllRead);
  pagination?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-page]');
    if (button && !button.disabled) loadNotifications(Number(button.dataset.page));
  });
  loadNotifications();
})();
