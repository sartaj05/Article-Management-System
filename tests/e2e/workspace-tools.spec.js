const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
const accounts = {
  journalist: { username: process.env.E2E_USERNAME || 'e2e_journalist', dashboard: '/journalist/dashboard/' },
  editor: { username: process.env.E2E_EDITOR_USERNAME || 'e2e_editor', dashboard: '/editor/dashboard/' },
  admin: { username: process.env.E2E_ADMIN_USERNAME || 'e2e_admin', dashboard: '/adminMain/dashboard/' },
};

async function loginAs(page, role) {
  const account = accounts[role];
  await page.goto('/login-template/');
  await page.locator('#username').fill(account.username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(account.dashboard.replaceAll('/', '\\/') + '$'), { timeout: 15_000 });
}

test('editor keeps the full workspace header when opening Search', async ({ page }) => {
  await loginAs(page, 'editor');
  await page.goto('/editor/dashboard/');
  const expectedLinks = ['Home', 'Manage', 'Approve', 'Review', 'Search', 'Media', 'Notifications', 'Analytics', 'Monitoring', 'Assignments', 'Published', 'Log out'];
  for (const label of expectedLinks) {
    await expect(page.locator('header.workspace-topbar').getByRole('link', { name: new RegExp(`^${label}`) })).toBeVisible();
  }

  await page.getByRole('link', { name: /^Search/ }).click();
  await expect(page).toHaveURL(/\/articles\/workspace\/search\/$/);
  for (const label of expectedLinks) {
    await expect(page.locator('header.workspace-topbar').getByRole('link', { name: new RegExp(`^${label}`) })).toBeVisible();
  }
  await expect(page.locator('header.workspace-topbar a[aria-current="page"]')).toHaveText('Search');
  await expect(page.locator('header.workspace-topbar')).not.toContainText('Workspace');
});

test('logout blocks Chrome Back from reopening a workspace page', async ({ page }) => {
  await loginAs(page, 'editor');
  await page.goto('/articles/editor/assignments/');
  await expect(page.locator('script[src*="workspace-ui.js"]')).toHaveCount(1);
  await expect.poll(() => page.evaluate(() => typeof window.WorkspaceUI)).toBe('object');
  await page.getByRole('link', { name: 'Log out', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('access_token'))).toBeNull();
  await page.goBack();
  await expect(page).toHaveURL(/login-template/);
});

test('analytics dashboard presents the executive overview and newsroom pulse', async ({ page }) => {
  await loginAs(page, 'editor');
  await page.goto('/articles/workspace/analytics/');
  await expect(page.locator('.analytics-page')).toBeVisible();
  await expect(page.locator('.analytics-stat')).toHaveCount(13);
  await expect(page.locator('#analytics-pulse')).toBeVisible();
  await expect(page.locator('#analytics-pulse .analytics-pulse__row')).toHaveCount(3);
  await expect(page.locator('#executive-summary article')).toHaveCount(4);
  await expect(page.locator('.analytics-quick-actions')).toBeVisible();
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(dimensions.width, 'analytics dashboard overflows horizontally').toBeLessThanOrEqual(dimensions.viewport + 1);
});

async function expectUsablePage(page, path, heading) {
  await page.goto(path);
  await expect(page.locator('h1')).toContainText(heading);
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(dimensions.width, `${path} overflows horizontally`).toBeLessThanOrEqual(dimensions.viewport + 1);
}

for (const role of Object.keys(accounts)) {
  test(`${role} can open shared workspace tools`, async ({ page }) => {
    await loginAs(page, role);
    await expectUsablePage(page, '/articles/workspace/search/', 'Search articles');
    await expectUsablePage(page, '/articles/workspace/media/', 'Media library');
    await expectUsablePage(page, '/articles/workspace/notifications/', 'Notifications');
    await expectUsablePage(page, '/articles/workspace/analytics/', 'Editorial analytics');
    if (role !== 'journalist') {
      await expectUsablePage(page, '/articles/editor/assignments/', 'Assignment board');
      await expectUsablePage(page, '/articles/workspace/monitoring/', 'Monitoring & audit');
    }
  });
}
