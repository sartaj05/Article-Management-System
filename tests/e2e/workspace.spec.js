const { test, expect } = require('@playwright/test');

const username = process.env.E2E_USERNAME || 'e2e_journalist';
const password = process.env.E2E_PASSWORD || 'StrongPass123!';

async function login(page) {
  await page.goto('/login-template/');
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(/journalist\/dashboard/);
}

test('public login page keeps a responsive shared shell', async ({ page }) => {
  await page.goto('/login-template/');
  await expect(page.locator('header .site-header__brand, header .workspace-topbar__brand').first()).toBeVisible();
  await expect(page.locator('#login-form')).toBeVisible();
});

test('journalist workspace opens and closes support chat', async ({ page }) => {
  await login(page);
  const launcher = page.getByRole('button', { name: /help & support/i });
  await expect(launcher).toBeVisible();
  await launcher.click();
  await expect(page.getByRole('dialog', { name: /article studio support/i })).toBeVisible();
  await page.getByRole('button', { name: /close support/i }).click();
  await expect(page.getByRole('dialog', { name: /article studio support/i })).toBeHidden();
});

test('mobile workspace keeps tables usable and closes modals with Escape', async ({ page }) => {
  await login(page);
  await page.goto('/journalist/dashboard/');
  await page.locator('#article-list-link').click();
  await expect(page.locator('.responsive-table, table').first()).toBeVisible();
  await page.getByRole('button', { name: /^view$/i }).first().click();
  await page.keyboard.press('Escape');
  await expect(page.locator('.modal:visible')).toHaveCount(0);
});
