(() => {
  const root = document.querySelector('.compliance-page-shell');
  if (!root) return;

  const auditList = document.getElementById('compliance-audit-list');
  const auditStatus = document.getElementById('compliance-audit-status');
  const auditFilter = document.getElementById('compliance-audit-filter');
  const auditPagination = document.getElementById('compliance-audit-pagination');
  const requestList = document.getElementById('compliance-request-list');
  const privacyStatus = document.getElementById('compliance-privacy-status');
  const workspaceSelect = document.getElementById('compliance-workspace');
  const workspaceStatus = document.getElementById('compliance-workspace-status');
  const evidenceStatus = document.getElementById('compliance-evidence-status');
  const evidenceDetails = document.getElementById('compliance-evidence-details');
  const reliabilityStatus = document.getElementById('compliance-reliability-status');
  const reliabilityDetails = document.getElementById('compliance-reliability-details');
  const holdsStatus = document.getElementById('compliance-holds-status');
  const holdList = document.getElementById('compliance-hold-list');
  const modal = document.getElementById('legal-hold-modal');
  const holdForm = document.getElementById('legal-hold-form');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const formatDate = (value) => value ? new Date(value).toLocaleString() : '—';
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  let workspaceSlug = root.dataset.workspaceSlug || window.localStorage.getItem('active_workspace_slug') || '';
  let auditPage = 1;

  const request = async (url, options = {}) => {
    const headers = { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf()) } : {}) };
    if (workspaceSlug) headers['X-Workspace-Slug'] = workspaceSlug;
    const response = await fetch(url, { credentials: 'same-origin', ...options, headers: { ...headers, ...(options.headers || {}) } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || 'Compliance data could not be loaded.');
    return payload;
  };
  const setError = (element, error) => { element.textContent = error.message || String(error); element.classList.add('is-error'); };
  const setReady = (element, message) => { element.textContent = message; element.classList.remove('is-error'); };

  async function loadWorkspaces() {
    const workspaces = await request('/api/workspaces/', { headers: {} });
    workspaceSelect.innerHTML = workspaces.length ? workspaces.map((workspace) => `<option value="${escapeHtml(workspace.slug)}">${escapeHtml(workspace.name)}</option>`).join('') : '<option value="">No workspaces available</option>';
    if (!workspaces.some((workspace) => workspace.slug === workspaceSlug)) workspaceSlug = workspaces[0]?.slug || '';
    if (workspaceSlug && workspaces.some((workspace) => workspace.slug === workspaceSlug)) workspaceSelect.value = workspaceSlug;
    if (!workspaceSlug) throw new Error('Select a workspace before opening compliance controls.');
    window.localStorage.setItem('active_workspace_slug', workspaceSlug);
    setReady(workspaceStatus, `Reviewing ${workspaceSelect.selectedOptions[0]?.textContent || workspaceSlug}.`);
  }

  async function loadEvidence() {
    const payload = await request('/articles/api/v2/compliance/evidence/');
    const chain = payload.audit_chain || {};
    const holds = payload.legal_holds || {};
    const retention = payload.retention || {};
    const verified = Boolean(chain.verified);
    document.getElementById('compliance-chain-status').textContent = verified ? 'Verified' : 'Attention';
    document.getElementById('compliance-chain-detail').textContent = `${chain.entries || 0} entries · ${chain.legacy_unhashed_entries || 0} legacy`;
    document.getElementById('compliance-active-holds').textContent = holds.active ?? 0;
    document.getElementById('compliance-hold-detail').textContent = `${holds.total || 0} total hold${holds.total === 1 ? '' : 's'}`;
    document.getElementById('compliance-retention').textContent = `${retention.configured_days || 0} days`;
    const pill = document.getElementById('compliance-evidence-pill');
    pill.textContent = verified ? 'Chain verified' : 'Review required';
    pill.classList.toggle('is-success', verified);
    pill.classList.toggle('is-warning', !verified);
    evidenceDetails.innerHTML = `<div><dt>Workspace</dt><dd>${escapeHtml(payload.workspace?.name || workspaceSlug)}</dd></div><div><dt>Entries</dt><dd>${chain.entries || 0}</dd></div><div><dt>Legacy events</dt><dd>${chain.legacy_unhashed_entries || 0}</dd></div><div><dt>Generated</dt><dd>${formatDate(payload.generated_at)}</dd></div>`;
    setReady(evidenceStatus, verified ? 'The workspace audit chain is internally consistent.' : 'Some audit entries need review before this workspace can be considered verified.');
  }

  async function loadReliability() {
    const payload = await request('/articles/api/v2/operations/reliability/');
    const objectives = payload.objectives || {};
    const restore = payload.restore_verification || {};
    const passed = Number(restore.passed_drills || 0);
    const failed = Number(restore.failed_drills || 0);
    document.getElementById('compliance-recovery').textContent = failed ? 'Attention' : 'Ready';
    document.getElementById('compliance-recovery-detail').textContent = `RTO ${objectives.rto_minutes || '—'}m · RPO ${objectives.rpo_minutes || '—'}m`;
    reliabilityDetails.innerHTML = `<div><dt>Backup region</dt><dd>${escapeHtml(payload.backup?.region || 'Not configured')}</dd></div><div><dt>Latest backup</dt><dd>${formatDate(payload.backup?.latest_completed_at)}</dd></div><div><dt>Restore drills</dt><dd>${passed} passed · ${failed} failed</dd></div><div><dt>Status page</dt><dd>${payload.status_page_enabled ? 'Enabled' : 'Disabled'}</dd></div>`;
    setReady(reliabilityStatus, failed ? 'One or more recovery drills need attention.' : 'Recovery objectives and backup status are healthy.');
  }

  async function loadHolds() {
    const items = await request('/articles/api/v2/compliance/legal-holds/');
    const activeCount = items.filter((item) => item.is_active).length;
    holdList.innerHTML = items.length ? items.map((item) => `<article class="compliance-hold ${item.is_active ? '' : 'compliance-hold--released'}"><div><strong>${escapeHtml(item.name)}</strong><p>${escapeHtml(item.reason)}</p><small>Created by ${escapeHtml(item.created_by || 'System')} · ${formatDate(item.created_at)}</small></div><div class="compliance-hold__actions"><span class="compliance-status-pill ${item.is_active ? 'is-success' : 'is-muted'}">${item.is_active ? 'Active' : 'Released'}</span>${item.is_active ? `<button class="button button--secondary button--small" type="button" data-release-hold="${item.id}">Release</button>` : `<small>Released ${formatDate(item.released_at)}</small>`}</div></article>`).join('') : '<p class="account-empty">No legal holds have been created for this workspace.</p>';
    setReady(holdsStatus, `${activeCount} active hold${activeCount === 1 ? '' : 's'}.`);
  }

  async function loadAudit() {
    const params = new URLSearchParams({ page: auditPage, page_size: 10 });
    if (auditFilter.value.trim()) params.set('action', auditFilter.value.trim());
    if (workspaceSlug) params.set('workspace', workspaceSlug);
    const payload = await request(`/articles/api/v2/audit-logs/?${params}`, { headers: {} });
    const items = payload.results || payload;
    auditList.innerHTML = items.length ? items.map((item) => `<article class="audit-item"><div><strong>${escapeHtml(item.action)}</strong><span>${escapeHtml(item.actor_name || item.actor || 'System')} · ${formatDate(item.created_at)}</span></div><p>${escapeHtml(JSON.stringify(item.details || {}))}</p></article>`).join('') : '<p class="account-empty">No audit events match this filter.</p>';
    setReady(auditStatus, `${items.length} event${items.length === 1 ? '' : 's'} loaded.`);
    const pages = Math.max(1, Math.ceil(Number(payload.count || items.length) / 10));
    auditPage = Math.min(auditPage, pages);
    auditPagination.innerHTML = pages > 1 ? `<div class="feature-pagination__controls"><span>Page ${auditPage} of ${pages}</span><button class="button button--secondary button--small" type="button" data-page="${auditPage - 1}" ${auditPage === 1 ? 'disabled' : ''}>Previous</button><button class="button button--secondary button--small" type="button" data-page="${auditPage + 1}" ${auditPage === pages ? 'disabled' : ''}>Next</button></div>` : '';
  }

  async function loadPrivacyRequests() {
    const response = await fetch('/api/privacy/compliance/', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Privacy requests could not be loaded.');
    const items = await response.json();
    requestList.innerHTML = items.length ? items.map((item) => `<article class="compliance-request"><div><strong>${escapeHtml(item.request_type)}</strong><span>${escapeHtml(item.username)} · ${escapeHtml(item.email)}</span></div><span class="compliance-request__status">${escapeHtml(item.status)}</span><time>${formatDate(item.created_at)}</time></article>`).join('') : '<p class="account-empty">No privacy requests recorded.</p>';
    setReady(privacyStatus, `${items.length} request${items.length === 1 ? '' : 's'} loaded.`);
  }

  async function load() {
    [evidenceStatus, reliabilityStatus, holdsStatus, auditStatus, privacyStatus].forEach((element) => element.classList.remove('is-error'));
    try { await loadWorkspaces(); await Promise.all([loadEvidence(), loadReliability(), loadHolds(), loadAudit(), loadPrivacyRequests()]); }
    catch (error) { setError(workspaceStatus, error); [evidenceStatus, reliabilityStatus, holdsStatus, auditStatus, privacyStatus].forEach((element) => setError(element, error)); }
  }

  function closeHoldModal() { modal.hidden = true; holdForm.reset(); }
  document.getElementById('create-legal-hold').addEventListener('click', () => { modal.hidden = false; holdForm.querySelector('input').focus(); });
  document.getElementById('close-legal-hold').addEventListener('click', closeHoldModal);
  document.getElementById('cancel-legal-hold').addEventListener('click', closeHoldModal);
  modal.addEventListener('click', (event) => { if (event.target === modal) closeHoldModal(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !modal.hidden) closeHoldModal(); });
  holdForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = holdForm.querySelector('button[type="submit"]'); button.disabled = true;
    try { await request('/articles/api/v2/compliance/legal-holds/', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(holdForm).entries())) }); closeHoldModal(); await Promise.all([loadEvidence(), loadHolds(), loadAudit()]); window.appAlert?.('The legal hold is active and now appears in the preservation register.', { kind: 'success', title: 'Legal hold created' }); }
    catch (error) { window.appAlert?.(error.message, { kind: 'error', title: 'Unable to create legal hold' }); }
    finally { button.disabled = false; }
  });
  holdList.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-release-hold]'); if (!button) return;
    const confirmed = await window.appConfirm?.('Release this legal hold? Records will return to the normal retention policy.', { title: 'Release legal hold' });
    if (!confirmed) return;
    button.disabled = true;
    try { await request(`/articles/api/v2/compliance/legal-holds/${button.dataset.releaseHold}/`, { method: 'PATCH', body: JSON.stringify({ is_active: false }) }); await Promise.all([loadEvidence(), loadHolds(), loadAudit()]); }
    catch (error) { window.appAlert?.(error.message, { kind: 'error', title: 'Unable to release legal hold' }); button.disabled = false; }
  });
  workspaceSelect.addEventListener('change', async () => { workspaceSlug = workspaceSelect.value; window.localStorage.setItem('active_workspace_slug', workspaceSlug); workspaceStatus.textContent = 'Switching workspace…'; auditPage = 1; await load(); });
  auditFilter.addEventListener('input', () => { clearTimeout(window.complianceAuditTimer); auditPage = 1; window.complianceAuditTimer = setTimeout(() => loadAudit().catch((error) => setError(auditStatus, error)), 250); });
  auditPagination.addEventListener('click', (event) => { const button = event.target.closest('[data-page]'); if (!button || button.disabled) return; auditPage = Number(button.dataset.page) || 1; loadAudit().catch((error) => setError(auditStatus, error)); });
  document.getElementById('refresh-compliance').addEventListener('click', load);
  load();
})();
