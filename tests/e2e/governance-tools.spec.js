const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
const adminUsername = process.env.E2E_ADMIN_USERNAME || 'e2e_admin';

async function loginAsAdmin(page) {
  await page.goto('/login-template/');
  await page.locator('#username').fill(adminUsername);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(/\/adminMain\/dashboard\/$/, { timeout: 15_000 });
}

async function expectResponsivePage(page, path, heading) {
  await page.goto(path);
  await expect(page.locator('h1')).toContainText(heading);
  const dimensions = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(dimensions.width, `${path} overflows horizontally`).toBeLessThanOrEqual(dimensions.viewport + 1);
}

test('admin can discover and open governance tools from the dashboard', async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.locator('.workspace-tools-menu')).toBeVisible();
  await page.locator('.workspace-tools-menu summary').click();
  for (const label of ['AI health', 'Backups', 'Permissions', 'Compliance', 'Workspace hub']) {
    await expect(page.locator('.workspace-tools-menu__panel').getByRole('link', { name: label, exact: true })).toBeVisible();
  }
});

test('admin governance pages render without horizontal overflow', async ({ page }) => {
  await loginAsAdmin(page);
  await expectResponsivePage(page, '/articles/workspace/compliance/', 'Compliance & audit center');
  await expect(page.locator('#compliance-workspace')).toBeVisible();
  await expect(page.locator('.compliance-overview')).toBeVisible();
  await expectResponsivePage(page, '/articles/workspace/backups/', 'Backup & restore center');
  await expectResponsivePage(page, '/articles/workspace/permissions/', 'Role permissions');
  await expectResponsivePage(page, '/articles/workspace/ai-observability/', 'Quality, cost & reliability');
});
