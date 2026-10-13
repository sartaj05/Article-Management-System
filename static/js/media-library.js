(function () {
  const grid = document.getElementById('media-grid');
  const status = document.getElementById('media-status');
  const form = document.getElementById('media-upload-form');
  const query = document.getElementById('media-query');
  const filter = document.getElementById('media-filter');
  const token = localStorage.getItem('access_token');
  let debounce;
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  const headers = (extra) => Object.assign({ Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, extra || {});

  async function loadAssets() {
    const params = new URLSearchParams(); if (query.value.trim()) params.set('q', query.value.trim()); if (filter.value) params.set('media_type', filter.value);
    try {
      const response = await fetch(`/articles/api/v2/media-library/?${params}`, { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Unable to load media.');
      grid.innerHTML = payload.length ? payload.map(assetTemplate).join('') : '<div class="feature-empty">No assets found.</div>';
      status.textContent = `${payload.length} asset${payload.length === 1 ? '' : 's'} available`;
      grid.querySelectorAll('[data-archive-id]').forEach((button) => button.addEventListener('click', () => archiveAsset(button.dataset.archiveId)));
    } catch (error) { grid.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`; status.textContent = 'Media library unavailable'; }
  }

  function assetTemplate(asset) {
    const url = asset.file || asset.external_url || '';
    const previewUrl = asset.variant_urls?.web || url;
    const preview = asset.media_type === 'image' && previewUrl ? `<img src="${escapeHtml(previewUrl)}" alt="${escapeHtml(asset.alt_text || asset.title)}" loading="lazy" decoding="async">` : `<span class="media-card__icon">${escapeHtml(asset.media_type)}</span>`;
    return `<article class="media-card">${preview}<div class="media-card__body"><span class="workspace-result__status">${escapeHtml(asset.media_type)}</span><h2>${escapeHtml(asset.title)}</h2><p>${escapeHtml(asset.alt_text || asset.caption || 'No accessibility description')}</p><small>${escapeHtml(asset.uploaded_by_name || 'You')} · ${new Date(asset.created_at).toLocaleDateString()}</small><button class="button button--secondary button--small" type="button" data-archive-id="${asset.id}">Archive</button></div></article>`;
  }

  async function archiveAsset(id) {
    const confirmed = window.appConfirm ? await window.appConfirm('Archive this asset?', { title: 'Archive asset' }) : window.confirm('Archive this asset?');
    if (!confirmed) return;
    const response = await fetch(`/articles/api/v2/media-library/${id}/`, { method: 'DELETE', headers: headers(), credentials: 'same-origin' });
    if (!response.ok) { status.textContent = 'The asset could not be archived.'; return; }
    loadAssets();
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault(); status.textContent = 'Uploading asset…';
    const data = new FormData(); data.append('file', document.getElementById('media-file').files[0]);
    const fieldIds = { title: 'media-title', media_type: 'media-type', alt_text: 'media-alt', caption: 'media-caption', credit: 'media-credit' };
    Object.entries(fieldIds).forEach(([key, id]) => data.append(key, document.getElementById(id).value));
    try { const response = await fetch('/articles/api/v2/media-library/', { method: 'POST', headers: headers(), body: data, credentials: 'same-origin' }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || Object.values(payload).flat().join(' ')); form.reset(); status.textContent = 'Asset uploaded successfully.'; loadAssets(); } catch (error) { status.textContent = error.message; }
  });
  [query, filter].forEach((field) => field.addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(loadAssets, 250); }));
  loadAssets();
})();
