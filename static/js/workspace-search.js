(function () {
  const form = document.getElementById('workspace-search-form');
  const results = document.getElementById('workspace-results');
  const status = document.getElementById('workspace-search-status');
  const pagination = document.getElementById('workspace-pagination');
  const token = localStorage.getItem('access_token');
  const fields = {
    q: document.getElementById('workspace-query'),
    status: document.getElementById('workspace-status'),
    category: document.getElementById('workspace-category'),
    sort: document.getElementById('workspace-sort'),
  };
  let currentPage = 1;

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const headers = () => ({ Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) });

  function queryString(page = 1) {
    const params = new URLSearchParams({ page, page_size: 12 });
    Object.entries(fields).forEach(([key, field]) => { if (field.value.trim()) params.set(key === 'status' ? 'workflow_status' : key, field.value.trim()); });
    return params;
  }

  async function search(page = 1) {
    currentPage = page;
    status.textContent = 'Searching…';
    try {
      const response = await fetch(`/articles/api/v2/articles/search/?${queryString(page)}`, { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Search failed.');
      const items = payload.results || [];
      results.innerHTML = items.length ? items.map(cardTemplate).join('') : '<div class="feature-empty">No articles match these filters.</div>';
      status.textContent = `${payload.count || 0} result${payload.count === 1 ? '' : 's'} found`;
      renderPagination(payload);
      const url = new URL(window.location.href);
      ['q', 'workflow_status', 'category', 'sort', 'page'].forEach((key) => url.searchParams.delete(key));
      queryString(page).forEach((value, key) => { if (value && key !== 'page_size') url.searchParams.set(key, value); });
      window.history.replaceState({}, '', url);
    } catch (error) {
      results.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`;
      pagination.innerHTML = '';
      status.textContent = 'Search unavailable';
    }
  }

  function cardTemplate(article) {
    return `<article class="workspace-result"><div><span class="workspace-result__status">${escapeHtml(article.workflow_status)}</span><h2>${escapeHtml(article.title)}</h2><p>${escapeHtml(article.summary || article.subtitle || 'No summary available.')}</p></div><dl><div><dt>Category</dt><dd>${escapeHtml(article.category || 'Uncategorised')}</dd></div><div><dt>Author</dt><dd>${escapeHtml(article.author_name)}</dd></div><div><dt>Updated</dt><dd>${article.updated_at ? new Date(article.updated_at).toLocaleDateString() : '—'}</dd></div></dl></article>`;
  }

  function renderPagination(payload) {
    const pageSize = Number(payload.results?.length || 12);
    const pages = Math.max(1, Math.ceil((payload.count || 0) / pageSize));
    pagination.innerHTML = pages <= 1 ? '' : `<button class="button button--secondary button--small" type="button" ${currentPage === 1 ? 'disabled' : ''} data-page="${currentPage - 1}">Previous</button><span>Page ${currentPage} of ${pages}</span><button class="button button--secondary button--small" type="button" ${currentPage >= pages ? 'disabled' : ''} data-page="${currentPage + 1}">Next</button>`;
  }

  form.addEventListener('submit', (event) => { event.preventDefault(); search(1); });
  pagination.addEventListener('click', (event) => { const button = event.target.closest('[data-page]'); if (button && !button.disabled) search(Number(button.dataset.page)); });
  const params = new URLSearchParams(window.location.search);
  fields.q.value = params.get('q') || '';
  fields.status.value = params.get('workflow_status') || '';
  fields.category.value = params.get('category') || '';
  fields.sort.value = params.get('sort') || 'recent';
  if ([...params.keys()].length) search(Number(params.get('page') || 1));
})();
