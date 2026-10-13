(() => {
  const auditList = document.getElementById('compliance-audit-list');
  const auditStatus = document.getElementById('compliance-audit-status');
  const auditFilter = document.getElementById('compliance-audit-filter');
  const requestList = document.getElementById('compliance-request-list');
  const privacyStatus = document.getElementById('compliance-privacy-status');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const formatDate = (value) => value ? new Date(value).toLocaleString() : '—';

  async function loadAudit() {
    const query = auditFilter.value.trim() ? `?action=${encodeURIComponent(auditFilter.value.trim())}` : '';
    const response = await fetch(`/articles/api/v2/audit-logs/${query}`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Audit events could not be loaded.');
    const payload = await response.json();
    const items = payload.results || payload;
    auditList.innerHTML = items.length ? items.map((item) => `<article class="audit-item"><div><strong>${escapeHtml(item.action)}</strong><span>${escapeHtml(item.actor_name || item.actor || 'System')} · ${formatDate(item.created_at)}</span></div><p>${escapeHtml(JSON.stringify(item.details || {}))}</p></article>`).join('') : '<p class="account-empty">No audit events match this filter.</p>';
    auditStatus.textContent = `${items.length} event${items.length === 1 ? '' : 's'} loaded.`;
  }

  async function loadPrivacyRequests() {
    const response = await fetch('/api/privacy/compliance/', { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Privacy requests could not be loaded.');
    const items = await response.json();
    requestList.innerHTML = items.length ? items.map((item) => `<article class="compliance-request"><div><strong>${escapeHtml(item.request_type)}</strong><span>${escapeHtml(item.username)} · ${escapeHtml(item.email)}</span></div><span class="compliance-request__status">${escapeHtml(item.status)}</span><time>${formatDate(item.created_at)}</time></article>`).join('') : '<p class="account-empty">No privacy requests recorded.</p>';
    privacyStatus.textContent = `${items.length} request${items.length === 1 ? '' : 's'} loaded.`;
  }

  async function load() {
    try { await Promise.all([loadAudit(), loadPrivacyRequests()]); } catch (error) { auditStatus.textContent = error.message; privacyStatus.textContent = error.message; }
  }
  let timer;
  auditFilter.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(loadAudit, 250); });
  document.getElementById('refresh-compliance').addEventListener('click', load);
  load();
})();
