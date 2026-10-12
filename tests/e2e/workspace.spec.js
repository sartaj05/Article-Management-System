const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_journalist';
const password = process.env.E2E_PASSWORD || 'StrongPass123!';

async function login(page) {
  await page.goto('/login-template/');
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(/journalist\/dashboard\//, { timeout: 15_000 });
}

test('public login page keeps a responsive shared shell', async ({ page }) => {
  await page.goto('/login-template/');
  await expect(page.locator('header .brand, header .workspace-topbar__brand').first()).toBeVisible();
  await expect(page.locator('#login-form')).toBeVisible();
});

test('journalist workspace opens and closes support chat', async ({ page }) => {
  await login(page);
  const launcher = page.locator('[data-support-open]');
  await expect(launcher).toBeVisible();
  await launcher.click();
  await expect(page.locator('#support-chat-panel')).toBeVisible();
  await page.locator('[data-support-close]').click();
  await expect(page.locator('#support-chat-panel')).toBeHidden();
});

test('mobile workspace keeps tables usable and closes modals with Escape', async ({ page }) => {
  await login(page);
  await page.goto('/journalist/dashboard/');
  await page.locator('#article-list-link').click();
  await expect(page.locator('#article-list-page')).toHaveClass(/active/);
  await expect(page.locator('#article-table')).toBeVisible();
  await page.locator('.view-article').first().click();
  await page.keyboard.press('Escape');
  await expect(page.locator('.modal:visible')).toHaveCount(0);
});
