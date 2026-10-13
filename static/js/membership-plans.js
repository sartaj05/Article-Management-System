(() => {
  const list = document.getElementById('membership-plans');
  const status = document.getElementById('membership-status');
  if (!list) return;

  const showStatus = (message, error = false) => {
    status.textContent = message;
    status.classList.toggle('is-error', error);
  };

  const loadPlans = async () => {
    try {
      const [plansResponse, membershipResponse] = await Promise.all([
        fetch('/api/membership/plans/', { headers: { Accept: 'application/json' } }),
        fetch('/api/membership/me/', { headers: { Accept: 'application/json' } }),
      ]);
      const plans = await plansResponse.json();
      const membership = membershipResponse.ok ? await membershipResponse.json() : { active: false };
      list.innerHTML = '';
      if (!plans.length) {
        list.innerHTML = '<p class="account-empty">Membership plans will appear here soon.</p>';
        return;
      }
      if (membership.active) showStatus('You have an active membership. Premium access is enabled.');
      plans.forEach((plan) => {
        const card = document.createElement('article');
        card.className = 'membership-plan-card';
        const features = Array.isArray(plan.features) ? plan.features : [];
        card.innerHTML = `
          <span class="feature-eyebrow">${plan.interval === 'year' ? 'Yearly' : 'Monthly'}</span>
          <h2>${plan.name}</h2>
          <p>${plan.description || 'Premium reading access for the Article Studio newsroom.'}</p>
          <strong class="membership-plan-card__price">${plan.currency} ${plan.price}<small> / ${plan.interval}</small></strong>
          <ul>${features.map((feature) => `<li>${feature}</li>`).join('')}</ul>
          <button class="button" type="button" data-plan-id="${plan.id}" ${membership.active ? 'disabled' : ''}>${membership.active ? 'Active membership' : 'Choose plan'}</button>`;
        list.appendChild(card);
      });
      list.querySelectorAll('[data-plan-id]').forEach((button) => {
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            const response = await fetch('/api/membership/checkout/', {
              method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.getCsrfToken?.() || '' },
              body: JSON.stringify({ plan_id: button.dataset.planId }),
            });
            const data = await response.json();
            showStatus(data.detail || (response.ok ? 'Membership updated.' : 'This plan needs payment setup.'), !response.ok && response.status !== 402);
            if (response.ok) button.textContent = 'Active membership';
          } catch (error) {
            showStatus('We could not update your membership. Please try again.', true);
            button.disabled = false;
          }
        });
      });
    } catch (error) {
      list.innerHTML = '<p class="account-empty">Membership plans are temporarily unavailable.</p>';
      showStatus('Please try again later.', true);
    }
  };
  loadPlans();
})();
