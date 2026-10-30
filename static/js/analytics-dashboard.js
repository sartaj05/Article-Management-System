(function () {
  const stats = document.getElementById('analytics-stats');
  const authors = document.getElementById('analytics-authors');
  const funnel = document.getElementById('analytics-funnel');
  const status = document.getElementById('analytics-status');
  const executiveSummary = document.getElementById('executive-summary');
  const executivePanels = document.getElementById('executive-panels');
  const executiveUpdated = document.getElementById('executive-updated');
  const token = localStorage.getItem('access_token');
  const headers = { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const metrics = [['articles', 'Articles'], ['published', 'Published'], ['pending_review', 'Pending review'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['total_views', 'Total views'], ['total_likes', 'Likes'], ['total_completed_reads', 'Completed reads'], ['total_read_starts', 'Read starts'], ['read_completion_rate', 'Completion rate', '%'], ['average_read_progress', 'Avg. progress', '%'], ['newsletter_conversions', 'Newsletter conversions'], ['total_shares', 'Shares']];

  async function loadAnalytics() {
    status.textContent = 'Loading analytics…';
    try {
      const response = await fetch('/articles/api/v2/analytics/', { headers, credentials: 'same-origin' });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Analytics unavailable.');
      stats.innerHTML = metrics.map(([key, label, suffix]) => `<article class="analytics-stat"><span>${label}</span><strong>${Number(payload[key] || 0).toLocaleString()}${suffix || ''}</strong></article>`).join('');
      const top = payload.top_authors || [];
      authors.innerHTML = top.length ? top.map((item, index) => `<div class="analytics-author"><span>${index + 1}</span><strong>${escapeHtml(item.username)}</strong><em>${item.article_count} article${item.article_count === 1 ? '' : 's'} · ${Number(item.views || 0).toLocaleString()} views · ${Number(item.completion_rate || 0).toLocaleString()}% completion</em></div>`).join('') : '<p class="feature-empty">No author activity yet.</p>';
      const funnelLabels = { read_start: 'Started reading', read_progress: 'Read in progress', read_complete: 'Completed reading', share: 'Shared' };
      funnel.innerHTML = Object.entries(payload.funnel || {}).map(([key, value]) => `<div class="analytics-funnel__item"><span>${funnelLabels[key] || escapeHtml(key)}</span><strong>${Number(value || 0).toLocaleString()}</strong></div>`).join('');
      status.textContent = `Updated just now · ${Number(payload.active_readers_7d || 0).toLocaleString()} active reader(s) this week`;
    } catch (error) { stats.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; authors.innerHTML = ''; status.textContent = 'Analytics unavailable'; }
  }
  async function loadExecutiveAnalytics() {
    if (!executiveSummary || !executivePanels) return;
    try {
      const response = await fetch('/articles/api/v2/analytics/executive/', { headers, credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Executive analytics unavailable.');
      const summary = [['published', payload.content.published, 'Published stories'], ['active_7d', payload.reader.active_7d, 'Active readers / 7d'], ['paid_transactions', payload.membership.paid_transactions, 'Paid transactions'], ['delivery_rate', `${payload.distribution.delivery_rate}%`, 'Distribution delivery']];
      executiveSummary.innerHTML = summary.map((item) => `<article><strong>${Number.isFinite(item[1]) ? Number(item[1]).toLocaleString() : escapeHtml(item[1])}</strong><span>${item[2]}</span></article>`).join('');
      const panels = [['Reader engagement', ` ${payload.reader.completion_rate}% completion · ${payload.reader.returning_7d} returning`, 'reader'], ['Workflow throughput', `${payload.workflow.submitted} in review · ${payload.workflow.approved} approved`, 'workflow'], ['Membership conversion', `${payload.membership.active_subscriptions} active subscriptions · ${payload.membership.paid_invoices} paid invoices`, 'membership'], ['Distribution health', `${payload.distribution.failed} failed · ${payload.distribution.queued} queued`, 'distribution']];
      executivePanels.innerHTML = panels.map((item) => `<article class="executive-panel executive-panel--${item[2]}"><div class="executive-panel__icon" aria-hidden="true"><i class="fa-solid fa-${item[2] === 'reader' ? 'users' : item[2] === 'workflow' ? 'diagram-project' : item[2] === 'membership' ? 'credit-card' : 'paper-plane'}"></i></div><div><strong>${item[0]}</strong><span>${escapeHtml(item[1])}</span></div></article>`).join('');
      executiveUpdated.textContent = `Updated ${new Date(payload.generated_at).toLocaleTimeString()}`;
    } catch (error) { executiveSummary.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; }
  }
  function refresh() { loadAnalytics(); loadExecutiveAnalytics(); }
  document.getElementById('refresh-analytics').addEventListener('click', refresh);
  refresh();
})();
