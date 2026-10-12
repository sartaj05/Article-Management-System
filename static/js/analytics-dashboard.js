(function () {
  const stats = document.getElementById('analytics-stats');
  const authors = document.getElementById('analytics-authors');
  const status = document.getElementById('analytics-status');
  const token = localStorage.getItem('access_token');
  const headers = { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const metrics = [['articles', 'Articles'], ['published', 'Published'], ['pending_review', 'Pending review'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['total_views', 'Total views'], ['total_likes', 'Likes'], ['total_completed_reads', 'Completed reads'], ['total_shares', 'Shares']];

  async function loadAnalytics() {
    status.textContent = 'Loading analytics…';
    try {
      const response = await fetch('/articles/api/v2/analytics/', { headers, credentials: 'same-origin' });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Analytics unavailable.');
      stats.innerHTML = metrics.map(([key, label]) => `<article class="analytics-stat"><span>${label}</span><strong>${Number(payload[key] || 0).toLocaleString()}</strong></article>`).join('');
      const top = payload.top_authors || [];
      authors.innerHTML = top.length ? top.map((item, index) => `<div class="analytics-author"><span>${index + 1}</span><strong>${escapeHtml(item.username)}</strong><em>${item.article_count} article${item.article_count === 1 ? '' : 's'}</em></div>`).join('') : '<p class="feature-empty">No author activity yet.</p>';
      status.textContent = 'Updated just now';
    } catch (error) { stats.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; authors.innerHTML = ''; status.textContent = 'Analytics unavailable'; }
  }
  document.getElementById('refresh-analytics').addEventListener('click', loadAnalytics);
  loadAnalytics();
})();
