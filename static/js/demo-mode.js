(function () {
  const personas = document.getElementById('demo-personas');
  const status = document.getElementById('demo-status');
  const reset = document.getElementById('demo-reset');
  if (!personas) return;
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const escape = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
  async function request(options = {}) {
    const response = await fetch('/demo/api/', { credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf()) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Demo request failed.');
    return data;
  }
  function render(data) {
    personas.innerHTML = data.personas.map((persona) => `<article class="demo-persona demo-persona--${escape(persona.key)}"><div class="demo-persona__icon"><i class="fa-solid fa-${escape(persona.icon)}" aria-hidden="true"></i></div><div><span class="feature-eyebrow">${escape(persona.label)} view</span><h3>${escape(persona.label)}</h3><p>${escape(persona.description)}</p></div><button class="button button--small" type="button" data-demo-persona="${escape(persona.key)}">Enter as ${escape(persona.label)} <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></button></article>`).join('');
  }
  async function load() { try { render(await request()); } catch (error) { personas.innerHTML = `<p class="demo-error">${escape(error.message)}</p>`; } }
  personas.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-demo-persona]');
    if (!button) return;
    button.disabled = true;
    if (status) status.textContent = `Opening the ${button.dataset.demoPersona} view…`;
    try { const data = await request({ method: 'POST', body: JSON.stringify({ persona: button.dataset.demoPersona }) }); window.location.assign(data.dashboard_url); }
    catch (error) { if (status) status.textContent = error.message; button.disabled = false; }
  });
  reset?.addEventListener('click', async () => { reset.disabled = true; if (status) status.textContent = 'Refreshing the demo workspace…'; try { const data = await request({ method: 'POST', body: JSON.stringify({ action: 'reset' }) }); if (status) status.textContent = data.message; await load(); } catch (error) { if (status) status.textContent = error.message; } finally { reset.disabled = false; } });
  load();
})();
