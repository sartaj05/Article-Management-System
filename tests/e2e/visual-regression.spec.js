const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';

async function login(page, username, dashboard) {
  await page.goto('/login-template/');
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(`${dashboard.replaceAll('/', '\\/')}$`));
}

async function freezeMotion(page) {
  await page.addStyleTag({ content: '* { animation: none !important; transition: none !important; caret-color: transparent !important; }' });
  await page.evaluate(() => document.fonts?.ready);
}

test.describe('client demo visual regression', () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  test('public newsroom and demo launcher remain presentation ready', async ({ page }) => {
    await page.goto('/');
    await freezeMotion(page);
    await expect(page).toHaveScreenshot('public-newsroom.png', { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });

    await page.goto('/demo/');
    await page.locator('#demo-personas').waitFor();
    await freezeMotion(page);
    await expect(page).toHaveScreenshot('demo-launcher.png', { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });
  });

  test('editor operations and billing pages remain presentation ready', async ({ page }) => {
    await login(page, process.env.E2E_EDITOR_USERNAME || 'e2e_editor', '/editor/dashboard/');
    await page.goto('/editor/dashboard/');
    await freezeMotion(page);
    await expect(page).toHaveScreenshot('editor-dashboard.png', { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });

    await page.goto('/membership/');
    await freezeMotion(page);
    await expect(page).toHaveScreenshot('membership-billing.png', { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });

    await page.goto('/articles/workspace/monitoring/');
    await page.locator('#health-status').waitFor();
    await freezeMotion(page);
    await expect(page).toHaveScreenshot('monitoring-dashboard.png', { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });
  });
});
