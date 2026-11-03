(function () {
  const root = document.querySelector('[data-status-page]');
  if (!root) return;
  const overall = document.getElementById('status-overall');
  const services = document.getElementById('status-services');
  const checkedAt = document.getElementById('status-checked-at');
  const availability = document.getElementById('status-availability');
  const serviceCount = document.getElementById('status-service-count');
  const note = document.getElementById('status-note');
  const labels = { database: 'Database', cache: 'Cache', storage: 'Media storage' };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const check = async () => {
    services.innerHTML = '<p class="status-page__loading">Checking production services…</p>';
    try {
      const response = await fetch('/status/', { headers: { Accept: 'application/json' }, credentials: 'same-origin', cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Status check failed.');
      const entries = Object.entries(payload.services || {});
      const operational = payload.status === 'operational';
      overall.dataset.state = operational ? 'operational' : 'degraded';
      overall.querySelector('strong').textContent = operational ? 'All systems operational' : 'Some systems need attention';
      checkedAt.textContent = `Checked ${new Date(payload.checked_at).toLocaleTimeString()}`;
      availability.textContent = operational ? 'Operational' : 'Degraded';
      serviceCount.textContent = `${entries.filter(([, state]) => state === 'operational').length} / ${entries.length}`;
      services.innerHTML = entries.map(([key, state]) => `<article class="status-page__service" data-state="${escapeHtml(state)}"><span class="status-page__service-icon" aria-hidden="true"><i></i></span><div><strong>${escapeHtml(labels[key] || key)}</strong><small>${state === 'operational' ? 'Operational' : 'Degraded'}</small></div><b>${state === 'operational' ? 'Healthy' : 'Investigating'}</b></article>`).join('');
      note.textContent = operational ? 'No active incidents are affecting the platform.' : 'Our team is investigating one or more degraded services.';
    } catch (error) {
      overall.dataset.state = 'degraded';
      overall.querySelector('strong').textContent = 'Status unavailable';
      checkedAt.textContent = 'Unable to complete check';
      availability.textContent = 'Unknown';
      serviceCount.textContent = '—';
      services.innerHTML = '<p class="status-page__loading status-page__loading--error">We could not complete the service check. Please try again.</p>';
      note.textContent = error.message;
    }
  };
  document.getElementById('status-refresh').addEventListener('click', check);
  check();
  window.setInterval(check, 30000);
})();
