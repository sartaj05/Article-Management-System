(() => {
  const auditList = document.getElementById('compliance-audit-list');
  const auditStatus = document.getElementById('compliance-audit-status');
  const auditFilter = document.getElementById('compliance-audit-filter');
  const auditPagination = document.getElementById('compliance-audit-pagination');
  const requestList = document.getElementById('compliance-request-list');
  const privacyStatus = document.getElementById('compliance-privacy-status');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const formatDate = (value) => value ? new Date(value).toLocaleString() : '—';
  let auditPage = 1;

  async function loadAudit() {
    const params = new URLSearchParams({ page: auditPage, page_size: 10 });
    if (auditFilter.value.trim()) params.set('action', auditFilter.value.trim());
    const response = await fetch(`/articles/api/v2/audit-logs/?${params}`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Audit events could not be loaded.');
    const payload = await response.json();
    const items = payload.results || payload;
    auditList.innerHTML = items.length ? items.map((item) => `<article class="audit-item"><div><strong>${escapeHtml(item.action)}</strong><span>${escapeHtml(item.actor_name || item.actor || 'System')} · ${formatDate(item.created_at)}</span></div><p>${escapeHtml(JSON.stringify(item.details || {}))}</p></article>`).join('') : '<p class="account-empty">No audit events match this filter.</p>';
    auditStatus.textContent = `${items.length} event${items.length === 1 ? '' : 's'} loaded.`;
    const pages = Math.max(1, Math.ceil(Number(payload.count || items.length) / 10));
    auditPage = Math.min(auditPage, pages);
    auditPagination.innerHTML = pages > 1 ? `<div class="feature-pagination__controls"><span>Page ${auditPage} of ${pages}</span><button class="button button--secondary button--small" type="button" data-page="${auditPage - 1}" ${auditPage === 1 ? 'disabled' : ''}>Previous</button><button class="button button--secondary button--small" type="button" data-page="${auditPage + 1}" ${auditPage === pages ? 'disabled' : ''}>Next</button></div>` : '';
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
  auditFilter.addEventListener('input', () => { clearTimeout(timer); auditPage = 1; timer = setTimeout(loadAudit, 250); });
  auditPagination?.addEventListener('click', (event) => { const button = event.target.closest('[data-page]'); if (!button || button.disabled) return; auditPage = Number(button.dataset.page) || 1; loadAudit(); });
  document.getElementById('refresh-compliance').addEventListener('click', load);
  load();
})();
