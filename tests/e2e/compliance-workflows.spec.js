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

async function openCompliance(page) {
  await page.goto('/articles/workspace/compliance/');
  await expect(page.locator('h1')).toContainText('Compliance & audit center');
  await expect(page.locator('#compliance-workspace')).toHaveValue(/.+/, { timeout: 15_000 });
}

test.describe('compliance and audit workflows', () => {
  test('creates and releases a legal hold through the UI', async ({ page }) => {
    await loginAsAdmin(page);
    await openCompliance(page);
    const name = `E2E preservation ${Date.now()}`;

    await page.locator('#create-legal-hold').click();
    await page.locator('#legal-hold-form [name="name"]').fill(name);
    await page.locator('#legal-hold-form [name="reason"]').fill('Preserve records for the automated compliance workflow test.');
    await page.locator('#legal-hold-form button[type="submit"]').click();
    await expect(page.locator('[data-app-dialog]')).toBeVisible();
    await page.locator('[data-dialog-confirm]').click();
    await expect(page.locator('#compliance-hold-list')).toContainText(name);

    await page.locator('[data-release-hold]').last().click();
    await expect(page.locator('[data-app-dialog]')).toBeVisible();
    await page.locator('[data-dialog-confirm]').click();
    await expect(page.locator('#compliance-hold-list')).toContainText('Released');
  });

  test('exports the audit trail for the signed-in admin', async ({ page }) => {
    await loginAsAdmin(page);
    const response = await page.request.get('/articles/api/v2/reports/audit/');
    expect(response.ok()).toBeTruthy();
    expect(response.headers()['content-type']).toContain('text/csv');
    expect(await response.text()).toContain('action');
  });

  test('shows a clear evidence error when the compliance service is unavailable', async ({ page }) => {
    await loginAsAdmin(page);
    await page.route('**/articles/api/v2/compliance/evidence/', async (route) => {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Evidence service unavailable for this test.' }) });
    });
    await openCompliance(page);
    await expect(page.locator('#compliance-evidence-status')).toHaveClass(/is-error/);
    await expect(page.locator('#compliance-evidence-status')).toContainText('Evidence service unavailable');
  });
});
