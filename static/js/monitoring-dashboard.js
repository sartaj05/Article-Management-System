(function () {
  const healthStatus = document.getElementById('health-status');
  const checks = document.getElementById('health-checks');
  const requestId = document.getElementById('health-request-id');
  const auditList = document.getElementById('audit-list');
  const auditPagination = document.getElementById('audit-pagination');
  const auditStatus = document.getElementById('audit-status');
  const action = document.getElementById('audit-action');
  const operationsSummary = document.getElementById('operations-summary');
  const operationsIncidents = document.getElementById('operations-incidents');
  const operationsLastChecked = document.getElementById('operations-last-checked');
  const queueHealth = document.getElementById('queue-health');
  const providerHealth = document.getElementById('provider-health');
  const runtimeStatus = document.getElementById('runtime-status');
  const token = localStorage.getItem('access_token');
  const headers = { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  let debounce;
  let auditPage = 1;
  async function loadHealth() {
    try {
      const response = await fetch('/health/?verbose=1', { headers, credentials: 'same-origin' });
      const payload = await response.json();
      healthStatus.textContent = payload.status === 'healthy' ? 'All services healthy' : 'Attention required';
      healthStatus.className = payload.status === 'healthy' ? 'is-healthy' : 'is-unhealthy';
      checks.innerHTML = Object.entries(payload.checks || {}).map(([key, value]) => `<span class="health-check health-check--${escapeHtml(value)}"><strong>${escapeHtml(key)}</strong>${escapeHtml(value)}</span>`).join('');
      document.getElementById('health-metadata').innerHTML = `<span>Environment <strong>${escapeHtml(payload.environment || '—')}</strong></span><span>Database <strong>${escapeHtml(payload.database_engine || '—')}</strong></span><span>Latency <strong>${escapeHtml(payload.latency_ms ?? '—')} ms</strong></span>`;
      requestId.textContent = payload.request_id ? `Request ID: ${payload.request_id}` : '';
    } catch (error) { healthStatus.textContent = 'Health check unavailable'; checks.innerHTML = ''; }
  }
  async function loadOperations() {
    try {
      const response = await fetch('/articles/api/v2/operations/overview/', { headers, credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to load operations overview.');
      const labels = { distribution_failed: 'Failed distribution', distribution_queued: 'Queue backlog', webhook_failed: 'Failed webhooks', digest_failed: 'Failed digests', payment_events_24h: 'Payment events / 24h', overdue_assignments: 'Overdue assignments' };
      operationsSummary.innerHTML = Object.entries(labels).map(([key, label]) => `<div class="operations-stat operations-stat--${payload.summary[key] ? 'attention' : 'clear'}"><strong>${payload.summary[key] || 0}</strong><span>${label}</span></div>`).join('');
      operationsIncidents.innerHTML = payload.incidents.length ? payload.incidents.map((item) => `<article class="operations-incident operations-incident--${escapeHtml(item.severity)}"><div><strong>${escapeHtml(item.area)}</strong><span>${escapeHtml(item.message)}</span></div><a class="button button--secondary button--small" href="${escapeHtml(item.action_url)}">Open</a></article>`).join('') : '<p class="operations-clear"><i class="fa-solid fa-circle-check" aria-hidden="true"></i> No operational incidents require attention.</p>';
      operationsLastChecked.textContent = payload.last_checked_at ? `Checked ${new Date(payload.last_checked_at).toLocaleTimeString()}` : 'Checked just now';
    } catch (error) { operationsIncidents.innerHTML = `<p class="feature-status is-error">${escapeHtml(error.message)}</p>`; }
  }
  async function loadRuntime() {
    try {
      const [queueResponse, providerResponse] = await Promise.all([
        fetch('/articles/api/v2/operations/queue/', { headers, credentials: 'same-origin' }),
        fetch('/provider-health/', { headers, credentials: 'same-origin' }),
      ]);
      const queue = await queueResponse.json();
      const providers = await providerResponse.json();
      if (!queueResponse.ok) throw new Error(queue.detail || 'Queue health unavailable.');
      if (!providerResponse.ok) throw new Error(providers.detail || 'Provider health unavailable.');
      const workerCount = Object.keys(queue.workers || {}).length;
      queueHealth.innerHTML = `<div class="operations-stat operations-stat--${queue.status === 'healthy' ? 'clear' : 'attention'}"><strong>${workerCount}</strong><span>Healthy workers</span></div><div class="operations-stat operations-stat--${queue.queue_length ? 'attention' : 'clear'}"><strong>${escapeHtml(queue.queue_length ?? '—')}</strong><span>Queued tasks</span></div><div class="operations-stat operations-stat--clear"><strong>${escapeHtml(queue.default_queue)}</strong><span>Default queue</span></div>`;
      const providerItems = [];
      Object.entries(providers).forEach(([group, values]) => {
        Object.entries(values).forEach(([name, value]) => {
          const configured = typeof value === 'object' ? value.configured : value;
          providerItems.push(`<div class="operations-stat operations-stat--${configured ? 'clear' : 'attention'}"><strong>${configured ? 'Ready' : 'Setup'}</strong><span>${escapeHtml(group)} / ${escapeHtml(name)}</span></div>`);
        });
      });
      providerHealth.innerHTML = providerItems.join('');
      runtimeStatus.textContent = queue.status === 'healthy' ? 'Runtime ready' : 'Runtime attention required';
      runtimeStatus.className = `feature-status ${queue.status === 'healthy' ? 'is-healthy' : 'is-error'}`;
    } catch (error) {
      runtimeStatus.textContent = error.message;
      runtimeStatus.className = 'feature-status is-error';
      queueHealth.innerHTML = '';
      providerHealth.innerHTML = '';
    }
  }
  async function loadAudit() {
    auditStatus.textContent = 'Loading audit events…';
    const params = new URLSearchParams({ page: auditPage, page_size: 10 });
    if (action.value.trim()) params.set('action', action.value.trim());
    try {
      const response = await fetch(`/articles/api/v2/audit-logs/?${params}`, { headers, credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to load audit events.');
      const items = payload.results || payload;
      auditList.innerHTML = items.length ? items.map((item) => `<article class="audit-item"><strong>${escapeHtml(item.action)}</strong><span>${escapeHtml(item.actor_name || 'System')} · ${new Date(item.created_at).toLocaleString()}</span><small>${item.article ? `Article #${item.article}` : escapeHtml(item.target_model || 'System')}</small></article>`).join('') : '<div class="feature-empty">No audit events found.</div>';
      auditStatus.textContent = `${payload.count ?? items.length} event${(payload.count ?? items.length) === 1 ? '' : 's'} shown`;
      const pages = Math.max(1, Math.ceil(Number(payload.count || items.length) / 10));
      auditPage = Math.min(auditPage, pages);
      auditPagination.innerHTML = pages > 1 ? `<div class="feature-pagination__controls"><span>Page ${auditPage} of ${pages}</span><button class="button button--secondary button--small" type="button" data-audit-page="${auditPage - 1}" ${auditPage === 1 ? 'disabled' : ''}>Previous</button><button class="button button--secondary button--small" type="button" data-audit-page="${auditPage + 1}" ${auditPage === pages ? 'disabled' : ''}>Next</button></div>` : '';
    } catch (error) { auditList.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; auditStatus.textContent = 'Audit feed unavailable'; }
  }
  function refresh() { loadHealth(); loadRuntime(); loadOperations(); loadAudit(); }
  action.addEventListener('input', () => { clearTimeout(debounce); auditPage = 1; debounce = setTimeout(loadAudit, 300); });
  auditPagination?.addEventListener('click', (event) => { const button = event.target.closest('[data-audit-page]'); if (!button || button.disabled) return; auditPage = Number(button.dataset.auditPage) || 1; loadAudit(); });
  document.getElementById('refresh-monitoring').addEventListener('click', refresh);
  refresh();
})();
