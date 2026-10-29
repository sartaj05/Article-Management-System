const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
const articlePath = '/articles/read/e2e-public-reader-story/';
const accounts = {
  journalist: { username: process.env.E2E_USERNAME || 'e2e_journalist', dashboard: '/journalist/dashboard/' },
  editor: { username: process.env.E2E_EDITOR_USERNAME || 'e2e_editor', dashboard: '/editor/dashboard/' },
  admin: { username: process.env.E2E_ADMIN_USERNAME || 'e2e_admin', dashboard: '/adminMain/dashboard/' },
};

async function login(page, role) {
  const account = accounts[role];
  await page.goto('/login-template/');
  await page.locator('#username').fill(account.username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(account.dashboard.replaceAll('/', '\\/') + '$'));
}

async function api(page, url, { method = 'GET', body } = {}) {
  return page.evaluate(async ({ url, method, body }) => {
    const csrf = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
    const headers = { Accept: 'application/json' };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      headers['X-CSRFToken'] = decodeURIComponent(csrf);
    }
    const response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let payload;
    try { payload = JSON.parse(text); } catch (_) { payload = text; }
    return { status: response.status, payload };
  }, { url, method, body });
}

test('translation comparison and localized distribution are published end to end', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await login(page, 'editor');
  await page.goto(articlePath);
  const articleId = await page.locator('audio[data-audio-article]').getAttribute('data-audio-article');
  expect(articleId).toBeTruthy();

  await page.goto('/articles/workspace/translations/');
  const articleIdField = page.locator('#translation-form [name="article_id"]');
  await articleIdField.fill(articleId);
  await articleIdField.press('Tab');
  const translationCard = page.locator('.translation-card').filter({ hasText: 'E2E Hindi Reader Story' });
  await expect(translationCard).toBeVisible();
  const compareResponse = page.waitForResponse((response) => response.url().includes('/articles/api/v2/translations/') && response.url().endsWith('/compare/'));
  await translationCard.locator('[data-compare]').click();
  let comparisonResponse;
  try {
    comparisonResponse = await compareResponse;
  } catch (error) {
    const state = await page.locator('[data-compare]').evaluate((button) => ({ disabled: button.disabled, id: button.dataset.id }));
    throw new Error(`${error.message}; page errors: ${pageErrors.join('; ')}; button: ${JSON.stringify(state)}`);
  }
  expect(comparisonResponse.status(), pageErrors.join('; ')).toBe(200);
  const comparison = translationCard.locator('.translation-comparison');
  await expect(comparison).toBeVisible();
  await expect(comparison).toContainText('Source vs hi');
  await expect(comparison.locator('ins').first()).toBeVisible();

  const rss = await api(page, '/rss/hi.xml');
  expect(rss.status).toBe(200);
  expect(rss.payload).toContain('E2E Hindi Reader Story');
  expect(rss.payload).toContain('/articles/read/e2e-public-reader-story/hi/');

  const sitemap = await api(page, '/sitemap.xml');
  expect(sitemap.status).toBe(200);
  expect(sitemap.payload).toContain('/articles/read/e2e-public-reader-story/hi/');
});

test('unread notification badge is rendered from the live count endpoint', async ({ page }) => {
  await login(page, 'editor');
  const badgeResponse = page.waitForResponse((response) => response.url().includes('/articles/api/v2/notifications/unread-count/'));
  await page.goto('/editor/dashboard/');
  await expect(page.locator('a[href="/articles/workspace/notifications/"] .notification-unread-badge')).toBeVisible();
  expect((await badgeResponse).status()).toBe(200);
  await expect(page.locator('a[href="/articles/workspace/notifications/"] .notification-unread-badge')).toHaveText(/^[1-9]\d*$/);
});

test('reader digest history loads from the authenticated account endpoint', async ({ page }) => {
  await login(page, 'journalist');
  const digestResponse = page.waitForResponse((response) => response.url().includes('/api/alerts/digests/'));
  await page.goto('/account/settings/#reader-digest-history');
  expect((await digestResponse).status()).toBe(200);
  await expect(page.locator('#reader-digest-history')).toContainText('No digest deliveries yet.');
});

test('workspace creation exposes scoped controls and quotas end to end', async ({ page }) => {
  await login(page, 'admin');
  const name = `E2E Workspace ${Date.now()}`;
  const created = await api(page, '/api/workspaces/', { method: 'POST', body: { name } });
  expect(created.status).toBe(201);
  expect(created.payload.name).toBe(name);

  const controls = await api(page, `/api/workspaces/${created.payload.slug}/controls/`);
  expect(controls.status).toBe(200);
  expect(controls.payload.membership.role).toBe('owner');
  expect(controls.payload.quotas.seats).toMatchObject({ used: 1, limit: 5 });
  expect(controls.payload.analytics_scope.workspace_slug).toBe(created.payload.slug);
});
