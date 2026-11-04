(function () {
  const launcher = document.querySelector('[data-guided-tour-launch]');
  if (!launcher) return;
  const role = launcher.dataset.guidedTourRole || 'journalist';
  const copy = {
    journalist: [
      { selectors: ['[data-page-link="create-article-page"]', '#create-article-link'], title: 'Start a story', body: 'Create a new article, save a draft, and keep the editorial process moving.' },
      { selectors: ['[data-page-link="article-list-page"]', '#article-list-link'], title: 'Manage your work', body: 'Return to your article list to edit drafts, check status, and continue writing.' },
      { selectors: ['.workspace-tools-menu'], title: 'Find newsroom tools', body: 'Translations, integrations, and the workspace hub are grouped here for quick access.' },
      { selectors: ['[data-dashboard-logout]'], title: 'Your secure exit', body: 'Use Log out whenever you finish working on a shared device.' },
    ],
    editor: [
      { selectors: ['#manage-articles-btn', 'a[href*="article-list-page"]'], title: 'Manage the pipeline', body: 'Start here to review the newsroom inventory and open an article.' },
      { selectors: ['#approve-articles-btn', 'a[href*="approve"]'], title: 'Approve with confidence', body: 'Review submitted stories, make decisions, and keep publishing quality high.' },
      { selectors: ['a[href*="assignment-board"]'], title: 'Coordinate the team', body: 'Use assignments to track ownership, priorities, and review deadlines.' },
      { selectors: ['a[href*="analytics-dashboard"]'], title: 'Measure impact', body: 'Analytics connects publishing output with reader engagement and business signals.' },
    ],
    admin: [
      { selectors: ['a[href*="workspace-hub"]'], title: 'Operate the workspace', body: 'Manage identity, members, onboarding, and workspace-level controls.' },
      { selectors: ['a[href*="monitoring-dashboard"]'], title: 'Watch reliability', body: 'Monitoring brings service health, failed jobs, and operational signals together.' },
      { selectors: ['a[href*="compliance-center"]'], title: 'Govern access and data', body: 'Compliance and audit tools help your team verify sensitive actions.' },
      { selectors: ['a[href*="analytics-dashboard"]'], title: 'Share executive context', body: 'Use analytics to explain newsroom performance to stakeholders.' },
    ],
  }[role] || [];
  let index = 0;
  let target = null;
  let overlay = null;
  const seenKey = `article-studio-tour-seen-${role}`;
  const findTarget = (step) => step.selectors.map((selector) => document.querySelector(selector)).find(Boolean);
  const close = () => {
    target?.classList.remove('is-guided-tour-target');
    overlay?.remove(); overlay = null; target = null;
    document.body.classList.remove('has-guided-tour');
    window.localStorage.setItem(seenKey, '1');
  };
  const render = () => {
    target?.classList.remove('is-guided-tour-target');
    const step = copy[index];
    target = findTarget(step);
    if (target) { target.classList.add('is-guided-tour-target'); target.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    overlay.querySelector('[data-tour-title]').textContent = step.title;
    overlay.querySelector('[data-tour-body]').textContent = step.body;
    overlay.querySelector('[data-tour-count]').textContent = `${index + 1} / ${copy.length}`;
    overlay.querySelector('[data-tour-back]').hidden = index === 0;
    overlay.querySelector('[data-tour-next]').textContent = index === copy.length - 1 ? 'Finish tour' : 'Next';
  };
  const open = () => {
    if (!copy.length || overlay) return;
    document.body.classList.add('has-guided-tour');
    overlay = document.createElement('div');
    overlay.className = 'guided-tour-overlay';
    overlay.innerHTML = `<div class="guided-tour-backdrop" data-tour-close></div><section class="guided-tour-card" role="dialog" aria-modal="true" aria-labelledby="guided-tour-title"><div class="guided-tour-card__top"><span>ARTICLE STUDIO · ${role.toUpperCase()} TOUR</span><b data-tour-count></b></div><h2 id="guided-tour-title" data-tour-title></h2><p data-tour-body></p><div class="guided-tour-card__actions"><button type="button" class="button button--secondary button--small" data-tour-skip>Skip tour</button><span></span><button type="button" class="button button--secondary button--small" data-tour-back>Back</button><button type="button" class="button button--small" data-tour-next>Next</button></div></section>`;
    document.body.appendChild(overlay);
    overlay.querySelector('[data-tour-close]').addEventListener('click', close);
    overlay.querySelector('[data-tour-skip]').addEventListener('click', close);
    overlay.querySelector('[data-tour-back]').addEventListener('click', () => { index = Math.max(0, index - 1); render(); });
    overlay.querySelector('[data-tour-next]').addEventListener('click', () => { if (index === copy.length - 1) close(); else { index += 1; render(); } });
    render();
  };
  launcher.addEventListener('click', () => { index = 0; open(); });
  if (!window.__ARTICLE_STUDIO_E2E__ && !window.localStorage.getItem(seenKey)) window.setTimeout(open, 700);
})();
