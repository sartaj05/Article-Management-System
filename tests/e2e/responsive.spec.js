const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';

const roles = {
  journalist: { username: process.env.E2E_USERNAME || 'e2e_journalist', path: '/journalist/dashboard/' },
  editor: { username: process.env.E2E_EDITOR_USERNAME || 'e2e_editor', path: '/editor/dashboard/' },
  admin: { username: process.env.E2E_ADMIN_USERNAME || 'e2e_admin', path: '/adminMain/dashboard/' },
};

async function loginAs(page, role = 'journalist') {
  const account = roles[role];
  await page.goto('/login-template/');
  await page.locator('#username').fill(account.username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(account.path.replaceAll('/', '\\/') + '$'), { timeout: 15_000 });
}

async function expectNoHorizontalOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    windowWidth: window.innerWidth,
    visualViewport: window.visualViewport ? window.visualViewport.width : null,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
    overflowingElements: [...document.querySelectorAll('body *')]
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return { tag: element.tagName, id: element.id, className: element.className, left: rect.left, right: rect.right, width: rect.width };
      })
      .filter((item) => item.right > document.documentElement.clientWidth + 1 || item.left < -1)
      .sort((a, b) => b.right - a.right)
      .slice(0, 8),
  }));

  expect(dimensions.documentWidth, `document overflow: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(dimensions.viewport + 1);
  expect(dimensions.bodyWidth, `body overflow: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(dimensions.viewport + 1);
}

async function expectWithinViewport(page, selector) {
  const target = typeof selector === 'string' ? page.locator(selector) : selector;
  const label = typeof selector === 'string' ? selector : 'target';
  const result = await target.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      left: rect.left,
      right: rect.right,
      top: rect.top,
      bottom: rect.bottom,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });

  expect(result.left, `${label} starts outside viewport`).toBeGreaterThanOrEqual(-1);
  expect(result.right, `${label} ends outside viewport`).toBeLessThanOrEqual(result.viewportWidth + 1);
  expect(result.top, `${label} starts outside viewport height`).toBeGreaterThanOrEqual(-1);
  expect(result.bottom, `${label} ends outside viewport height`).toBeLessThanOrEqual(result.viewportHeight + 1);
}

async function expectHorizontallyWithinViewport(page, selector) {
  const result = await page.locator(selector).evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, viewportWidth: window.innerWidth };
  });

  expect(result.left, `${selector} starts outside viewport`).toBeGreaterThanOrEqual(-1);
  expect(result.right, `${selector} ends outside viewport`).toBeLessThanOrEqual(result.viewportWidth + 1);
}

test.describe('responsive public and authentication shells', () => {
  for (const path of ['/', '/login-template/', '/register-template/', '/forgot-password/']) {
    test(`${path} has a usable responsive shell`, async ({ page }) => {
      await page.goto(path);
      await expect(page.locator('header.site-header')).toBeVisible();
      await expect(page.locator('footer.site-footer')).toBeAttached();
      await expectNoHorizontalOverflow(page);
      await expectWithinViewport(page, 'header.site-header');
      await expectHorizontallyWithinViewport(page, 'footer.site-footer');
    });
  }
});

test.describe('responsive authenticated workspaces', () => {
  for (const [role, account] of Object.entries(roles)) {
    test(`${role} workspace shell stays inside the viewport`, async ({ page }) => {
      await loginAs(page, role);
      await expect(page.locator('header.workspace-topbar')).toBeVisible();
      await expect(page.locator('.support-chat__launcher')).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await expectWithinViewport(page, 'header.workspace-topbar');
      await expectWithinViewport(page, '.support-chat__launcher');
      await expect(page).toHaveTitle(/Article Studio|Dashboard/i);
      expect(page.url()).toContain(account.path);
    });
  }
});

test('journalist articles table and detail modal remain usable on narrow screens', async ({ page }) => {
  await loginAs(page, 'journalist');
  await page.goto('/journalist/dashboard/');
  await page.locator('#article-list-link').click();
  await expect(page.locator('#article-list-page')).toHaveClass(/active/);
  await expect(page.locator('#article-table')).toBeVisible({ timeout: 15_000 });
  await expectNoHorizontalOverflow(page);

  const firstArticle = page.locator('#article-table tbody tr').first();
  await expect(firstArticle).toBeVisible({ timeout: 15_000 });
  await firstArticle.locator('.view-article').click();
  const modal = page.locator('.modal:visible').first();
  await expect(modal).toBeVisible();
  await expectWithinViewport(page, modal.locator('.modal-content'));
  await page.keyboard.press('Escape');
  await expect(page.locator('.modal:visible')).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
});

test('support chat panel and controls remain inside the viewport', async ({ page }) => {
  await loginAs(page, 'journalist');
  await page.locator('[data-support-open]').click();
  await expect(page.locator('#support-chat-panel')).toBeVisible();
  await expectWithinViewport(page, '#support-chat-panel');
  await expectWithinViewport(page, '.support-chat__form');
  await expectNoHorizontalOverflow(page);
  await page.locator('[data-support-close]').click();
  await expect(page.locator('#support-chat-panel')).toBeHidden();
});
