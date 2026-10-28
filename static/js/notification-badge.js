(function () {
  const links = Array.from(document.querySelectorAll('a[href*="/workspace/notifications/"]'));
  if (!links.length) return;

  const update = async () => {
    try {
      const response = await fetch('/articles/api/v2/notifications/unread-count/', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const payload = await response.json();
      links.forEach((link) => {
        let badge = link.querySelector('.notification-unread-badge');
        if (payload.count > 0) {
          if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notification-unread-badge';
            link.appendChild(badge);
          }
          badge.textContent = payload.count > 99 ? '99+' : String(payload.count);
          badge.setAttribute('aria-label', `${payload.count} unread notifications`);
        } else if (badge) {
          badge.remove();
        }
      });
    } catch (error) { /* The navigation remains usable when the count endpoint is unavailable. */ }
  };

  update();
  window.setInterval(update, 30000);
  window.addEventListener('focus', update);
})();
