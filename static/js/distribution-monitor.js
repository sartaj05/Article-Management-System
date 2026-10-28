(function () {
  const list = document.getElementById('distribution-jobs');
  const status = document.getElementById('distribution-job-summary');
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  if (!list || !status) return;
  const escape = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  async function load() {
    try {
      const response = await fetch('/articles/api/v2/distribution-jobs/', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Distribution queue unavailable.');
      status.textContent = `${data.count} job(s) · ${data.summary.delivered || 0} delivered · ${data.summary.queued || 0} queued · ${data.summary.awaiting_provider || 0} awaiting provider`;
      list.innerHTML = data.jobs.length ? data.jobs.map((job) => `<article class="integration-item"><span><strong>${escape(job.article)} · ${escape(job.channel)}</strong><small>${escape(job.status)} · attempts ${job.attempts}${job.last_error ? ` · ${escape(job.last_error)}` : ''}</small></span>${['failed', 'awaiting_provider'].includes(job.status) ? `<button class="button button--small" data-retry-distribution="${job.id}">Retry</button>` : ''}</article>`).join('') : '<p class="account-empty">No distribution jobs yet.</p>';
    } catch (error) { status.textContent = error.message; }
  }
  list.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-retry-distribution]');
    if (!button) return;
    button.disabled = true;
    const response = await fetch(`/articles/api/v2/distribution-jobs/${button.dataset.retryDistribution}/`, { method: 'PATCH', credentials: 'same-origin', headers: { Accept: 'application/json', 'X-CSRFToken': decodeURIComponent(csrf()) } });
    if (!response.ok) status.textContent = 'Distribution job could not be queued.';
    await load();
  });
  document.getElementById('refresh-distribution-jobs')?.addEventListener('click', load);
  load();
})();
