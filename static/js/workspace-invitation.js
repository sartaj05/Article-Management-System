(() => {
  const root = document.querySelector('[data-invitation-token]');
  if (!root) return;
  const status = document.getElementById('invitation-status');
  const title = document.getElementById('invitation-title');
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  fetch(`/api/workspaces/invitations/${root.dataset.invitationToken}/accept/`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'X-CSRFToken': decodeURIComponent(csrf()) } })
    .then(async (response) => { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || 'This invitation could not be accepted.'); return data; })
    .then((data) => { title.textContent = `Welcome to ${data.workspace.name}`; status.textContent = `You joined as ${data.membership.role}. Your workspace is ready.`; status.classList.add('is-success'); })
    .catch((error) => { title.textContent = 'Invitation unavailable'; status.textContent = error.message; status.classList.add('is-error'); });
})();
