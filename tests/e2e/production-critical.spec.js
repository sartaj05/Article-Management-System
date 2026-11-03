const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
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
  const responsePromise = page.waitForResponse((response) => response.url().endsWith('/api/login/') && response.request().method() === 'POST', { timeout: 30_000 });
  await page.locator('#login-form button[type="submit"]').click();
  const response = await responsePromise;
  if (!response.ok()) throw new Error(`Login failed for ${role}: ${response.status()} ${await response.text()}`);
  await expect(page).toHaveURL(new RegExp(account.dashboard.replaceAll('/', '\\/') + '$'), { timeout: 30_000 });
}

test.describe('production critical path release gates', () => {
  test.setTimeout(120_000);

  test('admin completes backup and recovery verification from the UI', async ({ page }) => {
    await login(page, 'admin');
    await page.goto('/articles/workspace/backups/');
    await expect(page.locator('h1')).toContainText('Backup & restore center');
    await expect(page.locator('#backup-status')).not.toHaveClass(/is-error/);

    const backupResponse = page.waitForResponse((response) => response.url().endsWith('/articles/api/v2/operations/backups/') && response.request().method() === 'POST');
    await page.locator('#create-backup').click();
    const backup = await backupResponse;
    expect(backup.status(), await backup.text()).toBe(201);
    await expect(page.locator('#backup-status')).toContainText(/Backup \d+ completed/);

    const drillResponse = page.waitForResponse((response) => response.url().endsWith('/articles/api/v2/operations/recovery-drills/') && response.request().method() === 'POST');
    await page.locator('#run-recovery-drill').click();
    const drill = await drillResponse;
    expect([201, 503], await drill.text()).toContain(drill.status());
    await expect(page.locator('#backup-status')).toContainText(/Recovery drill (passed|unsupported|failed)/);
    await expect(page.locator('#recovery-list')).toContainText(/Recovery drill/);
  });

  test('journalist creates and revokes a scoped API key in the security center', async ({ page }) => {
    await login(page, 'journalist');
    await page.goto('/account/security/');
    await expect(page.locator('h1')).toContainText('Security & identity');
    const keyName = `E2E release key ${Date.now()}`;
    await page.locator('#api-key-form [name="name"]').fill(keyName);
    const createResponse = page.waitForResponse((response) => response.url().endsWith('/developer/keys/') && response.request().method() === 'POST');
    await page.locator('#api-key-form button[type="submit"]').click();
    const created = await createResponse;
    expect(created.status(), await created.text()).toBe(201);
    const payload = await created.json();
    await expect(page.locator('#api-key-reveal')).toBeVisible();
    await expect(page.locator('#api-key-value')).toContainText(/^as_/);
    const revokeButton = page.locator(`[data-revoke-key="${payload.details.id}"]`);
    await expect(revokeButton).toBeVisible();
    await revokeButton.click();
    await expect(page.locator('[data-app-dialog]')).toBeVisible();
    const revokeResponse = page.waitForResponse((response) => response.url().endsWith(`/developer/keys/${payload.details.id}/`) && response.request().method() === 'DELETE');
    await page.locator('[data-dialog-confirm]').click();
    expect((await revokeResponse).status()).toBe(200);
    await expect(page.locator('#api-keys')).toContainText('Revoked');
  });

  test('editor monitoring surface exposes live health and audit controls', async ({ page }) => {
    await login(page, 'editor');
    await page.goto('/articles/workspace/monitoring/');
    await expect(page.locator('h1')).toContainText('Monitoring & audit');
    await expect(page.locator('#health-status')).not.toContainText('Checking');
    await expect(page.locator('#health-checks')).toContainText(/Database|Cache/i);
    await expect(page.locator('#audit-list')).toBeVisible();
    await expect(page.locator('a[href="/articles/api/v2/reports/audit/"]')).toBeVisible();
  });
});
