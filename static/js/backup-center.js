(() => {
  const list = document.getElementById('backup-list');
  const summary = document.getElementById('backup-summary');
  const status = document.getElementById('backup-status');
  const recoveryList = document.getElementById('recovery-list');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const formatSize = (bytes) => bytes ? `${(bytes / 1024 / 1024).toFixed(2)} MB` : '—';
  async function load() {
    try {
      const response = await fetch('/articles/api/v2/operations/backups/', { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Backup status unavailable.');
      summary.innerHTML = `<article><span>Database</span><strong>${escapeHtml(data.database_engine)}</strong></article><article><span>Retention</span><strong>${escapeHtml(data.retention_days)} days</strong></article><article><span>Records</span><strong>${data.records.length}</strong></article>`;
      list.innerHTML = data.records.length ? data.records.map((item) => `<article class="backup-item"><div><strong>${escapeHtml(item.kind)} · ${escapeHtml(item.status)}</strong><span>${escapeHtml(item.path || item.error || 'No file generated')}</span></div><div><small>${formatSize(item.size_bytes)} · ${item.verified == null ? '—' : item.verified ? 'Checksum verified' : 'Checksum failed'}</small><time>${new Date(item.created_at).toLocaleString()}</time></div></article>`).join('') : '<p class="account-empty">No backups recorded yet.</p>';
      recoveryList.innerHTML = (data.recovery_drills || []).map((item) => `<article class="backup-item"><div><strong>Recovery drill · ${escapeHtml(item.status)}</strong><span>${escapeHtml(item.details)}</span></div><time>${new Date(item.checked_at).toLocaleString()}</time></article>`).join('');
      status.textContent = 'Backup status updated.';
    } catch (error) { status.textContent = error.message; status.classList.add('is-error'); }
  }
  document.getElementById('create-backup').addEventListener('click', async () => {
    const button = document.getElementById('create-backup'); button.disabled = true; status.textContent = 'Creating and verifying backup…';
    try { const response = await fetch('/articles/api/v2/operations/backups/', { method: 'POST', headers: { Accept: 'application/json', 'X-CSRFToken': document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '' }, credentials: 'same-origin' }); const data = await response.json(); if (!response.ok) throw new Error(data.error || data.detail || 'Backup failed.'); status.textContent = `Backup ${data.id} completed.`; await load(); } catch (error) { status.textContent = error.message; status.classList.add('is-error'); } finally { button.disabled = false; }
  });
  document.getElementById('create-media-backup').addEventListener('click', async (event) => {
    const button = event.currentTarget; button.disabled = true; status.textContent = 'Creating media snapshot…';
    try { const response = await fetch('/articles/api/v2/operations/backups/', { method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '' }, body: JSON.stringify({ kind: 'media' }), credentials: 'same-origin' }); const data = await response.json(); if (!response.ok) throw new Error(data.error || data.detail || 'Media backup failed.'); status.textContent = `Media snapshot ${data.id} completed.`; await load(); } catch (error) { status.textContent = error.message; status.classList.add('is-error'); } finally { button.disabled = false; }
  });
  document.getElementById('run-recovery-drill').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true; status.textContent = 'Running recovery validation…';
    try { const response = await fetch('/articles/api/v2/operations/recovery-drills/', { method: 'POST', headers: { Accept: 'application/json', 'X-CSRFToken': document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '' }, credentials: 'same-origin' }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || data.details || 'Recovery check failed.'); status.textContent = `Recovery drill ${data.status}.`; await load(); } catch (error) { status.textContent = error.message; status.classList.add('is-error'); } finally { event.currentTarget.disabled = false; }
  });
  document.getElementById('refresh-backups').addEventListener('click', load); load();
})();
