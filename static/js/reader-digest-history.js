(function () {
  const history = document.getElementById('reader-digest-history');
  if (!history) return;
  const escape = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  fetch('/api/alerts/digests/', { credentials: 'same-origin', headers: { Accept: 'application/json' } }).then((response) => response.json().then((items) => ({ response, items }))).then(({ response, items }) => {
    if (!response.ok) throw new Error(items.detail || 'Digest history unavailable.');
    history.innerHTML = items.length ? `<h3>Recent digest deliveries</h3>${items.map((item) => `<article class="saved-search-item"><span><strong>${escape(item.frequency)} digest · ${escape(item.period_key)}</strong><small>${item.notification_count} alert(s) · ${escape(item.status)} · attempts ${item.attempts}</small></span></article>`).join('')}` : '<p class="account-empty">No digest deliveries yet.</p>';
  }).catch((error) => { history.innerHTML = `<p class="account-empty">${escape(error.message)}</p>`; });
})();
