(() => {
  const list = document.getElementById('editorial-comments-list');
  const form = document.getElementById('editorial-comment-form');
  const status = document.getElementById('editorial-comments-status');
  const articleId = document.body.dataset.articleId;
  if (!list || !form || !articleId) return;
  const token = localStorage.getItem('access_token');
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const request = async (method = 'GET', body) => {
    const response = await fetch(`/articles/api/v2/articles/${articleId}/editorial-comments/`, { method, credentials: 'same-origin', headers: { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf()) } : {}) }, body: body ? JSON.stringify(body) : undefined });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Editorial comments are unavailable.');
    return data;
  };
  const setStatus = (message, error = false) => { status.textContent = message; status.classList.toggle('is-error', error); };
  const load = async () => {
    try {
      const comments = await request();
      list.innerHTML = comments.length ? comments.map((comment) => `<article class="editorial-comment ${comment.status === 'resolved' ? 'is-resolved' : ''}"><div class="editorial-comment__meta"><strong>${escape(comment.author_name)}</strong><small>${new Date(comment.created_at).toLocaleString()}</small><span>${escape(comment.status)}</span></div><p>${escape(comment.body)}</p>${comment.mentions?.length ? `<small class="editorial-comment__mentions">Mentioned: ${comment.mentions.map(escape).join(', ')}</small>` : ''}<button class="btn btn-secondary" type="button" data-comment-id="${comment.id}" data-next-status="${comment.status === 'resolved' ? 'open' : 'resolved'}">${comment.status === 'resolved' ? 'Reopen' : 'Resolve'}</button></article>`).join('') : '<p class="account-empty">No review notes yet.</p>';
      const open = comments.filter((comment) => comment.status === 'open').length;
      setStatus(`${open} open note${open === 1 ? '' : 's'}.`);
    } catch (error) { setStatus(error.message, true); }
  };
  list.addEventListener('click', async (event) => { const button = event.target.closest('[data-comment-id]'); if (!button) return; button.disabled = true; try { await request('PATCH', { comment_id: button.dataset.commentId, status: button.dataset.nextStatus }); await load(); } catch (error) { setStatus(error.message, true); button.disabled = false; } });
  form.addEventListener('submit', async (event) => { event.preventDefault(); const button = form.querySelector('button'); button.disabled = true; try { const data = Object.fromEntries(new FormData(form).entries()); await request('POST', data); form.reset(); await load(); } catch (error) { setStatus(error.message, true); } finally { button.disabled = false; } });
  document.getElementById('refresh-editorial-comments')?.addEventListener('click', load);
  load();
})();
