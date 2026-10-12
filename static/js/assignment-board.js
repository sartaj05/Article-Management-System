(function () {
  const board = document.getElementById('assignment-board');
  const status = document.getElementById('assignment-status');
  const priority = document.getElementById('assignment-priority');
  const token = localStorage.getItem('access_token');
  const columns = [
    ['queued', 'Queued'],
    ['in_progress', 'In progress'],
    ['review', 'Review'],
    ['blocked', 'Blocked'],
    ['done', 'Done'],
  ];
  const timelineModal = document.getElementById('timeline-modal');

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[character]));
  }

  function headers(extra) {
    return Object.assign({
      'Accept': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }, extra || {});
  }

  async function loadBoard() {
    status.textContent = 'Loading assignments…';
    const query = priority.value ? `?priority=${encodeURIComponent(priority.value)}` : '';
    try {
      const response = await fetch(`/articles/api/v2/assignments/board/${query}`, { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to load assignments.');
      renderBoard(payload.columns || {});
      status.textContent = `${payload.count || 0} assignment${payload.count === 1 ? '' : 's'} tracked`;
    } catch (error) {
      board.innerHTML = `<div class="feature-empty">${escapeHtml(error.message)}</div>`;
      status.textContent = 'Assignment board unavailable';
    }
  }

  function renderBoard(data) {
    board.innerHTML = columns.map(([key, label]) => {
      const cards = data[key] || [];
      return `<section class="assignment-column" data-status="${key}">
        <header><h2>${label}</h2><span>${cards.length}</span></header>
        <div class="assignment-column__items">${cards.length ? cards.map(cardTemplate).join('') : '<p class="assignment-column__empty">Nothing here yet.</p>'}</div>
      </section>`;
    }).join('');
    board.querySelectorAll('[data-assignment-id]').forEach((card) => {
      card.querySelector('select').addEventListener('change', (event) => updateAssignment(card, event.target.value));
    });
  }

  function cardTemplate(item) {
    const due = item.due_at ? new Date(item.due_at).toLocaleDateString() : 'No deadline';
    return `<article class="assignment-card" data-assignment-id="${item.id}" data-article-id="${item.article}">
      <span class="assignment-card__priority assignment-card__priority--${escapeHtml(item.priority)}">${escapeHtml(item.priority)}</span>
      <h3>${escapeHtml(item.article_title)}</h3>
      <p>Owner: ${escapeHtml(item.editor_name || 'Unassigned')}</p>
      <p>By ${escapeHtml(due)}</p>
      ${item.notes ? `<p class="assignment-card__notes">${escapeHtml(item.notes)}</p>` : ''}
      <label class="assignment-card__status">Move to <select>${columns.map(([key, label]) => `<option value="${key}" ${key === item.status ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
      <button class="button button--small assignment-card__timeline" type="button" data-timeline-article="${item.article}">View timeline</button>
    </article>`;
  }

  async function openTimeline(articleId) {
    const steps = document.getElementById('timeline-steps');
    const events = document.getElementById('timeline-events');
    document.getElementById('timeline-title').textContent = 'Loading timeline…';
    document.getElementById('timeline-rejection').hidden = true;
    steps.innerHTML = '';
    events.innerHTML = '';
    timelineModal.hidden = false;
    try {
      const response = await fetch(`/articles/api/v2/articles/${articleId}/timeline/`, { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to load timeline.');
      document.getElementById('timeline-title').textContent = payload.title;
      steps.innerHTML = (payload.workflow_steps || []).map((step) => `<span class="workflow-step workflow-step--${escapeHtml(step.state)}">${escapeHtml(step.label)}</span>`).join('');
      if (payload.rejection_reason) {
        const rejection = document.getElementById('timeline-rejection');
        rejection.textContent = `Rejection reason: ${payload.rejection_reason}`;
        rejection.hidden = false;
      }
      events.innerHTML = (payload.events || []).length ? payload.events.map((event) => `<li><strong>${escapeHtml(event.action.replaceAll('_', ' '))}</strong><span>${escapeHtml(event.actor)} · ${new Date(event.created_at).toLocaleString()}</span></li>`).join('') : '<li class="timeline-events__empty">No workflow events recorded yet.</li>';
    } catch (error) {
      document.getElementById('timeline-title').textContent = error.message;
    }
  }

  async function updateAssignment(card, nextStatus) {
    const articleId = card.dataset.articleId;
    const assignmentId = card.dataset.assignmentId;
    try {
      const response = await fetch(`/articles/api/v2/articles/${articleId}/assignments/`, {
        method: 'PATCH', headers: headers({ 'Content-Type': 'application/json' }), credentials: 'same-origin',
        body: JSON.stringify({ assignment_id: assignmentId, status: nextStatus }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to update assignment.');
      await loadBoard();
    } catch (error) {
      status.textContent = error.message;
      await loadBoard();
    }
  }

  priority.addEventListener('change', loadBoard);
  document.getElementById('assignment-refresh').addEventListener('click', loadBoard);
  board.addEventListener('click', (event) => {
    const button = event.target.closest('[data-timeline-article]');
    if (button) openTimeline(button.dataset.timelineArticle);
  });
  document.getElementById('timeline-close').addEventListener('click', () => { timelineModal.hidden = true; });
  timelineModal.addEventListener('click', (event) => { if (event.target === timelineModal) timelineModal.hidden = true; });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') timelineModal.hidden = true; });
  loadBoard();
})();
