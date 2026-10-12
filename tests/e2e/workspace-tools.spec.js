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
  await page.waitForURL(new RegExp(account.dashboard.replaceAll('/', '\\/') + '$'));
}

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
