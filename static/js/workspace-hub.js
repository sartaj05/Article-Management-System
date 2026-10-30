(() => {
  const root = document.querySelector('[data-workspace-hub]');
  if (!root) return;
  const list = document.getElementById('workspace-list');
  const listStatus = document.getElementById('workspace-list-status');
  const details = document.getElementById('workspace-details');
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  let selected;

  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf()) } : {}) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Workspace request failed.');
    return data;
  };

  const setStatus = (element, message, error = false) => { element.textContent = message; element.classList.toggle('is-error', error); };
  const showDetails = async (workspace) => {
    selected = workspace;
    details.hidden = false;
    document.getElementById('workspace-name').textContent = workspace.name;
    document.getElementById('workspace-description').textContent = workspace.description || 'No description yet.';
    document.getElementById('workspace-role').textContent = 'Loading role…';
    try {
      const [controls, members, billing] = await Promise.all([
        request(`/api/workspaces/${encodeURIComponent(workspace.slug)}/controls/`),
        request(`/api/workspaces/${encodeURIComponent(workspace.slug)}/members/`),
        request(`/api/workspaces/${encodeURIComponent(workspace.slug)}/billing/`),
      ]);
      document.getElementById('workspace-role').textContent = controls.membership.role.replace('_', ' ');
      document.getElementById('workspace-member-count').textContent = `${members.length} member${members.length === 1 ? '' : 's'}`;
      document.getElementById('workspace-metrics').innerHTML = `
        <article><span>Plan</span><strong>${escape(billing.plan)}</strong><small>${escape(billing.billing_status)}</small></article>
        <article><span>Seats</span><strong>${billing.members} / ${billing.seat_limit}</strong><small>${billing.seats_available} available</small></article>
        <article><span>Articles</span><strong>${controls.quotas.articles.used}</strong><small>${controls.quotas.articles.limit ?? 'Unlimited'} capacity</small></article>`;
      document.getElementById('workspace-members').innerHTML = members.length ? members.map((member) => `<article class="workspace-hub__member"><span class="workspace-hub__avatar">${escape(member.username.slice(0, 1).toUpperCase())}</span><span><strong>${escape(member.username)}</strong><small>${escape(member.email)}</small></span><b>${escape(member.role)}</b></article>`).join('') : '<p class="account-empty">No members yet.</p>';
      document.getElementById('workspace-invite-section').hidden = !['owner', 'admin'].includes(controls.membership.role);
    } catch (error) { setStatus(listStatus, error.message, true); }
  };

  const load = async () => {
    try {
      const workspaces = await request('/api/workspaces/');
      list.innerHTML = workspaces.length ? workspaces.map((workspace) => `<button type="button" class="workspace-hub__card ${selected?.slug === workspace.slug ? 'is-selected' : ''}" data-workspace-slug="${escape(workspace.slug)}"><span class="workspace-hub__card-mark">✦</span><span><strong>${escape(workspace.name)}</strong><small>${workspace.member_count} member${workspace.member_count === 1 ? '' : 's'} · ${escape(workspace.plan)}</small></span><i>›</i></button>`).join('') : '<p class="account-empty">Create your first workspace to get started.</p>';
      setStatus(listStatus, `${workspaces.length} workspace${workspaces.length === 1 ? '' : 's'} available.`);
      if (selected) { const refreshed = workspaces.find((item) => item.slug === selected.slug); if (refreshed) await showDetails(refreshed); }
    } catch (error) { setStatus(listStatus, error.message, true); }
  };

  list.addEventListener('click', async (event) => {
    const card = event.target.closest('[data-workspace-slug]');
    if (!card) return;
    try {
      await request(`/api/workspaces/${encodeURIComponent(card.dataset.workspaceSlug)}/select/`, { method: 'POST', body: '{}' });
      await load();
      const workspaces = await request('/api/workspaces/');
      await showDetails(workspaces.find((workspace) => workspace.slug === card.dataset.workspaceSlug));
    } catch (error) { setStatus(listStatus, error.message, true); }
  });
  document.getElementById('workspace-refresh').addEventListener('click', load);
  document.getElementById('workspace-create-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button'); button.disabled = true;
    try { const workspace = await request('/api/workspaces/', { method: 'POST', body: Object.fromEntries(new FormData(form).entries()) }); form.reset(); setStatus(document.getElementById('workspace-create-status'), `${workspace.name} is ready.`); selected = workspace; await load(); await showDetails(workspace); }
    catch (error) { setStatus(document.getElementById('workspace-create-status'), error.message, true); } finally { button.disabled = false; }
  });
  document.getElementById('workspace-invite-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button'); button.disabled = true;
    try { const invitation = await request(`/api/workspaces/${encodeURIComponent(selected.slug)}/invite/`, { method: 'POST', body: Object.fromEntries(new FormData(form).entries()) }); form.reset(); setStatus(document.getElementById('workspace-invite-status'), `Invitation sent to ${invitation.email}.`); await showDetails(selected); }
    catch (error) { setStatus(document.getElementById('workspace-invite-status'), error.message, true); } finally { button.disabled = false; }
  });
  load();
})();
