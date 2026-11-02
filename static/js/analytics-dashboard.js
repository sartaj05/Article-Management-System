(function () {
  const stats = document.getElementById('analytics-stats');
  const pulse = document.getElementById('analytics-pulse');
  const health = document.getElementById('analytics-health');
  const authors = document.getElementById('analytics-authors');
  const funnel = document.getElementById('analytics-funnel');
  const status = document.getElementById('analytics-status');
  const executiveSummary = document.getElementById('executive-summary');
  const executivePanels = document.getElementById('executive-panels');
  const executiveUpdated = document.getElementById('executive-updated');
  const token = localStorage.getItem('access_token');
  const headers = { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const formatNumber = (value) => Number(value || 0).toLocaleString();
  const metrics = [
    { key: 'articles', label: 'Articles', helper: 'Stories in the newsroom', tone: 'brand', featured: true },
    { key: 'published', label: 'Published', helper: 'Stories live for readers', tone: 'teal', featured: true },
    { key: 'pending_review', label: 'Pending review', helper: 'Waiting for an editorial decision', tone: 'amber', featured: true },
    { key: 'total_views', label: 'Total views', helper: 'Across published stories', tone: 'blue', featured: true },
    { key: 'read_completion_rate', label: 'Completion rate', helper: 'Readers reaching the end', suffix: '%', tone: 'green', featured: true },
    { key: 'newsletter_conversions', label: 'Newsletter conversions', helper: 'Readers becoming subscribers', tone: 'coral', featured: true },
    { key: 'approved', label: 'Approved', helper: 'Ready for publication', tone: 'teal' },
    { key: 'rejected', label: 'Rejected', helper: 'Returned for changes', tone: 'coral' },
    { key: 'total_likes', label: 'Likes', helper: 'Positive reader reactions', tone: 'brand' },
    { key: 'total_completed_reads', label: 'Completed reads', helper: 'Finished reading sessions', tone: 'green' },
    { key: 'total_read_starts', label: 'Read starts', helper: 'Readers who opened a story', tone: 'blue' },
    { key: 'average_read_progress', label: 'Avg. progress', helper: 'Average story completion', suffix: '%', tone: 'green' },
    { key: 'total_shares', label: 'Shares', helper: 'Stories shared by readers', tone: 'amber' },
  ];

  function renderStats(payload) {
    stats.innerHTML = metrics.map((metric, index) => `<article class="analytics-stat analytics-stat--${metric.tone} ${metric.featured ? 'analytics-stat--featured' : ''}">
      <div class="analytics-stat__top"><span>${metric.label}</span><b aria-hidden="true">${String(index + 1).padStart(2, '0')}</b></div>
      <strong>${formatNumber(payload[metric.key])}${metric.suffix || ''}</strong>
      <small>${metric.helper}</small>
    </article>`).join('');
  }

  function renderPulse(payload) {
    const articles = Number(payload.articles || 0);
    const published = Number(payload.published || 0);
    const completion = Number(payload.read_completion_rate || 0);
    const pending = Number(payload.pending_review || 0);
    const rows = [
      { label: 'Publishing momentum', value: `${formatNumber(published)} live`, note: articles ? `${Math.round((published / articles) * 100)}% of your article inventory is published` : 'Publish your first story to start the trend', progress: articles ? Math.min(100, (published / articles) * 100) : 0, tone: 'brand' },
      { label: 'Reader attention', value: `${formatNumber(payload.total_views)} views`, note: `${formatNumber(payload.active_readers_7d)} active readers this week`, progress: Math.min(100, completion), tone: 'teal' },
      { label: 'Editorial queue', value: `${formatNumber(pending)} waiting`, note: pending ? 'Review these stories to keep the newsroom moving' : 'Your review queue is clear', progress: Math.min(100, pending * 10), tone: pending ? 'amber' : 'green' },
    ];
    pulse.innerHTML = rows.map((row) => `<div class="analytics-pulse__row analytics-pulse__row--${row.tone}"><div class="analytics-pulse__label"><strong>${row.label}</strong><span>${row.note}</span></div><b>${row.value}</b><div class="analytics-pulse__track" role="progressbar" aria-label="${escapeHtml(row.label)}" aria-valuenow="${Math.round(row.progress)}" aria-valuemin="0" aria-valuemax="100"><i style="width:${row.progress}%"></i></div></div>`).join('');
    const needsAttention = pending > 0;
    health.textContent = needsAttention ? 'Needs attention' : 'On track';
    health.className = `analytics-health analytics-health--${needsAttention ? 'attention' : 'healthy'}`;
  }

  async function loadAnalytics() {
    status.textContent = 'Refreshing newsroom data…';
    try {
      const response = await fetch('/articles/api/v2/analytics/', { headers, credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Analytics unavailable.');
      renderStats(payload);
      renderPulse(payload);
      const top = payload.top_authors || [];
      authors.innerHTML = top.length ? top.map((item, index) => `<div class="analytics-author"><span>${index + 1}</span><strong>${escapeHtml(item.username)}</strong><em>${item.article_count} article${item.article_count === 1 ? '' : 's'} · ${formatNumber(item.views)} views · ${formatNumber(item.completion_rate)}% completion</em></div>`).join('') : '<p class="feature-empty">No author activity yet.</p>';
      const funnelLabels = { read_start: 'Started reading', read_progress: 'Read in progress', read_complete: 'Completed reading', share: 'Shared' };
      funnel.innerHTML = Object.entries(payload.funnel || {}).map(([key, value]) => `<div class="analytics-funnel__item"><span>${funnelLabels[key] || escapeHtml(key)}</span><strong>${formatNumber(value)}</strong></div>`).join('');
      status.textContent = `Updated just now · ${formatNumber(payload.active_readers_7d)} active reader(s) this week`;
    } catch (error) {
      stats.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`;
      pulse.innerHTML = '<p class="feature-empty">Performance pulse is unavailable right now.</p>';
      authors.innerHTML = '';
      funnel.innerHTML = '';
      status.textContent = 'Analytics unavailable';
      health.textContent = 'Unavailable';
      health.className = 'analytics-health analytics-health--attention';
    }
  }

  async function loadExecutiveAnalytics() {
    try {
      const response = await fetch('/articles/api/v2/analytics/executive/', { headers, credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Executive analytics unavailable.');
      const summary = [['published', payload.content.published, 'Published stories'], ['active_7d', payload.reader.active_7d, 'Active readers / 7d'], ['paid_transactions', payload.membership.paid_transactions, 'Paid transactions'], ['delivery_rate', `${payload.distribution.delivery_rate}%`, 'Distribution delivery']];
      executiveSummary.innerHTML = summary.map((item) => `<article><strong>${typeof item[1] === 'number' ? formatNumber(item[1]) : escapeHtml(item[1])}</strong><span>${item[2]}</span></article>`).join('');
      const panels = [['Reader engagement', `${payload.reader.completion_rate}% completion · ${payload.reader.returning_7d} returning`, 'reader'], ['Workflow throughput', `${payload.workflow.submitted} in review · ${payload.workflow.approved} approved`, 'workflow'], ['Membership conversion', `${payload.membership.active_subscriptions} active subscriptions · ${payload.membership.paid_invoices} paid invoices`, 'membership'], ['Distribution health', `${payload.distribution.failed} failed · ${payload.distribution.queued} queued`, 'distribution']];
      executivePanels.innerHTML = panels.map((item) => `<article class="executive-panel executive-panel--${item[2]}"><div class="executive-panel__icon" aria-hidden="true"></div><div><strong>${item[0]}</strong><span>${escapeHtml(item[1])}</span></div></article>`).join('');
      executiveUpdated.textContent = `Updated ${new Date(payload.generated_at).toLocaleTimeString()}`;
    } catch (error) {
      executiveSummary.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`;
    }
  }

  function refresh() { loadAnalytics(); loadExecutiveAnalytics(); }
  document.getElementById('refresh-analytics').addEventListener('click', refresh);
  refresh();
})();
