(() => {
  const list = document.getElementById('membership-plans');
  const status = document.getElementById('membership-status');
  const billing = document.getElementById('membership-billing');
  if (!list) return;

  const showStatus = (message, error = false) => {
    status.textContent = message;
    status.classList.toggle('is-error', error);
  };

  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const money = (amount, currency) => `${escape(currency)} ${escape(amount)}`;
  const renderBilling = async (membership) => {
    if (!billing) return;
    const entitlementResponse = await fetch('/api/membership/entitlements/', { headers: { Accept: 'application/json' } });
    const entitlement = entitlementResponse.ok ? await entitlementResponse.json() : { invoices: [] };
    billing.hidden = false;
    const activeSubscription = membership.subscriptions?.find((item) => ['active', 'past_due'].includes(item.status));
    document.getElementById('membership-summary').innerHTML = activeSubscription
      ? `<article><span>Status</span><strong class="billing-status billing-status--${escape(activeSubscription.status)}">${escape(activeSubscription.status.replace('_', ' '))}</strong><small>${escape(activeSubscription.plan.name)} · ${escape(activeSubscription.provider)}</small></article><article><span>Renewal</span><strong>${activeSubscription.auto_renew ? 'Automatic' : 'Manual'}</strong><small>${activeSubscription.expires_at ? `Until ${new Date(activeSubscription.expires_at).toLocaleDateString()}` : 'No expiry recorded'}</small></article>`
      : '<article><span>Status</span><strong>Checkout ready</strong><small>Choose a plan above to activate membership.</small></article>';
    const cancelButton = document.getElementById('cancel-membership');
    cancelButton.hidden = !activeSubscription || !activeSubscription.auto_renew;
    document.getElementById('membership-transactions').innerHTML = membership.transactions?.length ? membership.transactions.map((item) => `<article class="membership-billing__row"><span><strong>${escape(item.plan)}</strong><small>${escape(item.provider)} · ${new Date(item.created_at).toLocaleDateString()}</small></span><b>${money(item.amount, item.currency)}</b><em class="billing-status billing-status--${escape(item.status)}">${escape(item.status)}</em></article>`).join('') : '<p class="account-empty">No transactions yet.</p>';
    document.getElementById('membership-invoices').innerHTML = entitlement.invoices?.length ? entitlement.invoices.map((item) => `<article class="membership-billing__row"><span><strong>${escape(item.invoice_number)}</strong><small>${escape(item.plan)} · due ${new Date(item.due_at).toLocaleDateString()}</small></span><b>${money(item.amount, item.currency)}</b><em class="billing-status billing-status--${escape(item.status)}">${escape(item.status)}</em></article>`).join('') : '<p class="account-empty">No invoices yet.</p>';
  };

  const pollCheckoutStatus = async (checkoutToken, attempts = 0) => {
    if (!checkoutToken || attempts >= 15) return;
    try {
      const response = await fetch(`/api/membership/checkout/${encodeURIComponent(checkoutToken)}/`, { headers: { Accept: 'application/json' } });
      const data = await response.json();
      if (response.ok && data.status === 'succeeded') {
        showStatus('Payment confirmed. Your membership is active.');
        await loadPlans();
        return;
      }
      if (response.ok && data.status === 'failed') {
        showStatus('Payment failed. Please try checkout again.', true);
        return;
      }
    } catch (error) { /* Retry while the provider webhook is in flight. */ }
    window.setTimeout(() => pollCheckoutStatus(checkoutToken, attempts + 1), 2000);
  };

  const loadPlans = async () => {
    let membership = { active: false, subscriptions: [], transactions: [] };
    try {
      const [plansResponse, membershipResponse] = await Promise.all([
        fetch('/api/membership/plans/', { headers: { Accept: 'application/json' } }),
        fetch('/api/membership/me/', { headers: { Accept: 'application/json' } }),
      ]);
      const plans = await plansResponse.json();
      membership = membershipResponse.ok ? await membershipResponse.json() : membership;
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
          ${Number(plan.price) > 0 ? '<label class="membership-provider">Payment provider<select data-provider><option value="stripe">Stripe</option><option value="razorpay">Razorpay</option><option value="manual">Manual</option></select></label>' : ''}
          <button class="button" type="button" data-plan-id="${plan.id}" ${membership.active ? 'disabled' : ''}>${membership.active ? 'Active membership' : 'Choose plan'}</button>`;
        list.appendChild(card);
      });
      list.querySelectorAll('[data-plan-id]').forEach((button) => {
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            const provider = button.closest('.membership-plan-card').querySelector('[data-provider]')?.value || 'manual';
            const response = await fetch('/api/membership/checkout/', {
              method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.getCsrfToken?.() || '' },
              body: JSON.stringify({ plan_id: button.dataset.planId, provider }),
            });
            const data = await response.json();
            showStatus(data.detail || (response.ok ? 'Membership updated.' : 'This plan needs payment setup.'), !response.ok && response.status !== 402);
            if (response.ok && data.checkout_required) {
              if (data.checkout_url) window.open(data.checkout_url, '_blank', 'noopener');
              pollCheckoutStatus(data.checkout_token);
            } else if (response.ok) button.textContent = 'Active membership';
          } catch (error) {
            showStatus('We could not update your membership. Please try again.', true);
            button.disabled = false;
          }
        });
      });
      await renderBilling(membership);
    } catch (error) {
      list.innerHTML = '<p class="account-empty">Membership plans are temporarily unavailable.</p>';
      showStatus('Please try again later.', true);
    }
  };
  document.getElementById('cancel-membership')?.addEventListener('click', async () => {
    if (!window.confirm('Cancel automatic renewal for this membership?')) return;
    const button = document.getElementById('cancel-membership'); button.disabled = true;
    try {
      const response = await fetch('/api/membership/cancel/', { method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': window.getCsrfToken?.() || '' } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Membership cancellation failed.');
      document.getElementById('billing-action-status').textContent = 'Automatic renewal cancelled. Your current access remains active until expiry.';
      await loadPlans();
    } catch (error) {
      document.getElementById('billing-action-status').textContent = error.message;
      document.getElementById('billing-action-status').classList.add('is-error');
    } finally { button.disabled = false; }
  });
  loadPlans();
})();
