(function () {
  const list = document.getElementById('notification-list');
  const status = document.getElementById('notification-status');
  const token = localStorage.getItem('access_token');
  const headers = () => ({ Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) });
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));

  async function loadNotifications() {
    status.textContent = 'Loading notifications…';
    try {
      const response = await fetch('/articles/api/v2/notifications/', { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Unable to load notifications.');
      const items = Array.isArray(payload) ? payload : (payload.results || []);
      list.innerHTML = items.length ? items.map(template).join('') : '<div class="feature-empty">You are all caught up.</div>';
      status.textContent = `${items.filter((item) => !item.is_read).length} unread notification${items.filter((item) => !item.is_read).length === 1 ? '' : 's'}`;
      list.querySelectorAll('[data-read-id]').forEach((button) => button.addEventListener('click', () => markRead(button.dataset.readId)));
    } catch (error) { list.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; status.textContent = 'Notifications unavailable'; }
  }

  function template(item) {
    return `<article class="notification-item ${item.is_read ? '' : 'notification-item--unread'}"><div class="notification-item__icon">${item.is_read ? '✓' : '!'}</div><div class="notification-item__body"><strong>${escapeHtml(item.notification_type)}</strong><p>${escapeHtml(item.message)}</p><small>${new Date(item.created_at).toLocaleString()}</small></div>${item.is_read ? '' : `<button class="button button--secondary button--small" type="button" data-read-id="${item.id}">Mark read</button>`}</article>`;
  }

  async function markRead(id) {
    const response = await fetch(`/articles/api/v2/notifications/${id}/read/`, { method: 'PATCH', headers: Object.assign(headers(), { 'Content-Type': 'application/json' }), credentials: 'same-origin' });
    if (response.ok) loadNotifications(); else status.textContent = 'Notification could not be marked as read.';
  }
  document.getElementById('refresh-notifications').addEventListener('click', loadNotifications);
  loadNotifications();
})();
