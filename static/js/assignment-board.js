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

  function csrfToken() {
    const cookie = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
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

  async function loadSLA() {
    const summary = document.getElementById('sla-summary');
    try {
      const response = await fetch('/articles/api/v2/assignments/sla/', { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to load SLA metrics.');
      summary.innerHTML = `<article><span>Overdue</span><strong>${payload.overdue_count}</strong></article><article><span>Due in 48 hours</span><strong>${payload.upcoming_deadline_count}</strong></article><article><span>Average review</span><strong>${payload.average_review_hours == null ? '—' : `${payload.average_review_hours}h`}</strong></article><article><span>Editors tracked</span><strong>${payload.workload.length}</strong></article>`;
    } catch (error) { summary.innerHTML = `<p class="feature-empty">${escapeHtml(error.message)}</p>`; }
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
      <button class="button button--secondary button--small" type="button" data-discussion-assignment="${item.id}">Discuss</button>
      <div class="assignment-discussion" data-discussion-panel hidden><div class="assignment-discussion__comments" data-comments-list></div><form data-comment-form><textarea name="body" rows="2" maxlength="2000" required placeholder="Add an internal note…"></textarea><input name="mentions" placeholder="Mention usernames, separated by commas"><button class="button button--small" type="submit">Post note</button></form></div>
    </article>`;
  }

  async function loadDiscussion(card, toggle = true) {
    const panel = card.querySelector('[data-discussion-panel]');
    const list = card.querySelector('[data-comments-list]');
    if (toggle) panel.hidden = !panel.hidden;
    if (panel.hidden) return;
    list.textContent = 'Loading discussion…';
    try {
      const response = await fetch(`/articles/api/v2/assignments/${card.dataset.assignmentId}/comments/`, { headers: headers(), credentials: 'same-origin' });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Unable to load discussion.');
      list.innerHTML = payload.length ? payload.map((comment) => `<article><strong>${escapeHtml(comment.author_name)}</strong><small>${new Date(comment.created_at).toLocaleString()}</small><p>${escapeHtml(comment.body)}</p><button class="button button--secondary button--small" type="button" data-resolve-comment="${comment.id}" data-comment-status="${comment.status}">${comment.status === 'resolved' ? 'Reopen' : 'Resolve'}</button></article>`).join('') : '<p class="feature-empty">No internal notes yet.</p>';
    } catch (error) { list.textContent = error.message; }
  }

  async function createDiscussionComment(form) {
    const card = form.closest('[data-assignment-id]');
    const data = Object.fromEntries(new FormData(form).entries());
    const response = await fetch(`/articles/api/v2/assignments/${card.dataset.assignmentId}/comments/`, {
      method: 'POST', headers: headers({ 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }), credentials: 'same-origin',
      body: JSON.stringify({ body: data.body, mentions: data.mentions }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Unable to post note.');
    form.reset();
    await loadDiscussion(card, false);
  }

  async function resolveDiscussionComment(button) {
    const card = button.closest('[data-assignment-id]');
    const statusValue = button.dataset.commentStatus === 'resolved' ? 'open' : 'resolved';
    const response = await fetch(`/articles/api/v2/assignments/${card.dataset.assignmentId}/comments/`, {
      method: 'PATCH', headers: headers({ 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }), credentials: 'same-origin',
      body: JSON.stringify({ comment_id: button.dataset.resolveComment, status: statusValue }),
    });
    if (!response.ok) throw new Error('Unable to update note.');
    await loadDiscussion(card, false);
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
    const discussionButton = event.target.closest('[data-discussion-assignment]');
    if (discussionButton) loadDiscussion(discussionButton.closest('[data-assignment-id]'));
    const resolveButton = event.target.closest('[data-resolve-comment]');
    if (resolveButton) resolveDiscussionComment(resolveButton).catch((error) => { status.textContent = error.message; });
  });
  board.addEventListener('submit', (event) => {
    const form = event.target.closest('[data-comment-form]');
    if (!form) return;
    event.preventDefault();
    createDiscussionComment(form).catch((error) => { status.textContent = error.message; });
  });
  document.getElementById('timeline-close').addEventListener('click', () => { timelineModal.hidden = true; });
  timelineModal.addEventListener('click', (event) => { if (event.target === timelineModal) timelineModal.hidden = true; });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') timelineModal.hidden = true; });
  loadBoard();
  loadSLA();
})();
