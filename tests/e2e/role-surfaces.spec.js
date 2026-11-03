const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
const roles = {
  journalist: { username: process.env.E2E_USERNAME || 'e2e_journalist', path: '/journalist/dashboard/' },
  editor: { username: process.env.E2E_EDITOR_USERNAME || 'e2e_editor', path: '/editor/dashboard/' },
  admin: { username: process.env.E2E_ADMIN_USERNAME || 'e2e_admin', path: '/adminMain/dashboard/' },
};

async function loginAs(page, role) {
  const account = roles[role];
  await page.goto('/login-template/');
  await page.locator('#username').fill(account.username);
  await page.locator('#password').fill(password);
  const loginResponse = page.waitForResponse((response) => response.url().endsWith('/api/login/') && response.request().method() === 'POST', { timeout: 30_000 });
  await page.locator('#login-form button[type="submit"]').click();
  const response = await loginResponse;
  if (!response.ok()) throw new Error(`Login failed for ${role}: ${response.status()} ${await response.text()}`);
  await expect(page).toHaveURL(new RegExp(account.path.replaceAll('/', '\\/') + '$'), { timeout: 30_000 });
}

async function expectNoHorizontalOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  expect(dimensions.documentWidth, `document overflow: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(dimensions.viewport + 1);
  expect(dimensions.bodyWidth, `body overflow: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(dimensions.viewport + 1);
}

async function freezeMotion(page) {
  await page.addStyleTag({ content: '* { animation: none !important; transition: none !important; caret-color: transparent !important; }' });
  await page.evaluate(() => document.fonts?.ready);
}

test.describe('role-aware production surfaces', () => {
  test.setTimeout(60_000);
  for (const role of Object.keys(roles)) {
    test(`${role} security center is responsive and visually stable`, async ({ page }) => {
      await loginAs(page, role);
      await page.goto('/account/security/');
      await expect(page.locator('h1')).toContainText('Security & identity');
      await expect(page.locator('header.workspace-topbar')).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await expect(page.locator('#mfa-title')).toBeVisible();
      await expect(page.locator('#api-keys-title')).toBeVisible();
      await freezeMotion(page);
      await expect(page).toHaveScreenshot(`security-center-${role}.png`, {
        animations: 'disabled',
        maxDiffPixelRatio: 0.015,
        mask: [page.locator('#security-center-status'), page.locator('#mfa-state'), page.locator('#mfa-badge'), page.locator('#mfa-setup'), page.locator('#mfa-disable'), page.locator('#security-sessions'), page.locator('#security-events'), page.locator('#api-keys'), page.locator('#sso-providers'), page.locator('#scim-tokens'), page.locator('#sso-status'), page.locator('#scim-status')],
      });

      if (role === 'admin') {
        await page.goto('/articles/workspace/compliance/');
        await expect(page.locator('h1')).toContainText('Compliance & audit center');
        await expect(page.locator('#compliance-workspace')).toHaveValue(/.+/, { timeout: 15_000 });
        await expectNoHorizontalOverflow(page);
        await freezeMotion(page);
        await expect(page).toHaveScreenshot('compliance-center-admin.png', {
          animations: 'disabled',
          maxDiffPixelRatio: 0.015,
          mask: [page.locator('#compliance-workspace-status'), page.locator('#compliance-evidence-status'), page.locator('#compliance-reliability-status'), page.locator('#compliance-holds-status'), page.locator('#compliance-audit-status'), page.locator('#compliance-privacy-status'), page.locator('#compliance-audit-list'), page.locator('#compliance-hold-list'), page.locator('#compliance-request-list')],
        });
      }
    });
  }
});
