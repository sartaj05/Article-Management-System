(function () {
  const articleId = document.body.dataset.articleId;
  const token = localStorage.getItem('access_token');
  const status = document.getElementById('revision-status');
  const list = document.getElementById('revision-list');
  if (!articleId || !status || !list) return;
  const headers = (extra) => Object.assign({ Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, extra || {});
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const fields = { title: document.getElementById('title'), subtitle: document.getElementById('subtitle'), content: document.getElementById('content') };

  async function getJson(url, options) {
    const response = await fetch(url, Object.assign({ credentials: 'same-origin', headers: headers() }, options || {}));
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Revision request failed.');
    return payload;
  }

  document.getElementById('restore-autosave')?.addEventListener('click', async () => {
    status.textContent = 'Loading latest autosave…';
    try {
      const payload = await getJson(`/articles/api/v2/articles/${articleId}/autosave/`);
      if (!payload.autosave) { status.textContent = 'No autosave is available yet.'; return; }
      const draft = payload.autosave;
      ['title', 'subtitle', 'content'].forEach((key) => { if (fields[key] && draft[key] !== undefined) fields[key].value = draft[key]; });
      status.textContent = `Autosave from ${new Date(draft.updated_at).toLocaleString()} restored into the editor. Save the article to keep it.`;
    } catch (error) { status.textContent = error.message; }
  });

  document.getElementById('load-revisions')?.addEventListener('click', async () => {
    status.textContent = 'Loading revisions…';
    try {
      const payload = await getJson(`/articles/api/v2/articles/${articleId}/revisions/`);
      const revisions = Array.isArray(payload) ? payload : (payload.results || []);
      list.hidden = false;
      list.innerHTML = revisions.length ? revisions.map((revision, index) => `<article class="revision-item"><div><strong>Revision ${revisions.length - index}</strong><span>${escapeHtml(revision.editor_name || 'Unknown')} · ${new Date(revision.created_at).toLocaleString()}</span></div><div><button class="btn btn-secondary revision-compare" type="button" data-revision-id="${revision.id}">Compare current</button><button class="btn btn-secondary revision-restore" type="button" data-revision-id="${revision.id}">Restore</button></div></article>`).join('') : '<p>No saved revisions yet.</p>';
      status.textContent = `${revisions.length} saved revision${revisions.length === 1 ? '' : 's'} found.`;
      list.querySelectorAll('.revision-compare').forEach((button) => button.addEventListener('click', () => compare(button.dataset.revisionId, revisions[0]?.id)));
      list.querySelectorAll('.revision-restore').forEach((button) => button.addEventListener('click', () => restore(button.dataset.revisionId)));
    } catch (error) { status.textContent = error.message; }
  });

  async function compare(from, to) {
    if (!from) { status.textContent = 'Choose a revision to compare.'; return; }
    try {
      const payload = await getJson(`/articles/api/v2/articles/${articleId}/revisions/compare/?from=${from}&to=current`);
      const diff = (payload.content_diff || []).join('\n');
      status.textContent = payload.changed ? `Comparison ready: ${payload.additions || 0} additions, ${payload.deletions || 0} deletions.` : 'No changes between these revisions.';
      const existing = document.getElementById('revision-diff');
      if (existing) existing.remove();
      const pre = document.createElement('pre');
      pre.id = 'revision-diff'; pre.className = 'revision-diff'; pre.textContent = diff || 'No content changes.';
      list.appendChild(pre);
    } catch (error) { status.textContent = error.message; }
  }

  async function restore(revisionId) {
    if (!window.confirm('Restore this revision? The current article will be saved as a new revision first.')) return;
    try {
      await getJson(`/articles/api/v2/articles/${articleId}/revisions/restore/`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ revision_id: revisionId }) });
      status.textContent = 'Revision restored. Reload the editor to review the restored content.';
    } catch (error) { status.textContent = error.message; }
  }
})();
