const { test, expect } = require('@playwright/test');

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
const articlePath = '/articles/read/e2e-public-reader-story/';

async function login(page, username, dashboard) {
  await page.goto('/login-template/');
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(`${dashboard.replaceAll('/', '\\/')}$`));
}

async function clearFollow(page, interestType, value) {
  const removed = await page.evaluate(async ({ interestType: type, value: interestValue }) => {
    const csrf = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
    const response = await fetch('/reader/interests/', {
      method: 'DELETE', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf) },
      body: JSON.stringify({ interest_type: type, value: interestValue }),
    });
    return response.ok;
  }, { interestType, value });
  expect(removed).toBeTruthy();
}

test('journalist reader features and editor campaign analytics work end to end', async ({ page }) => {
  const collectionName = `E2E collection ${Date.now()}`;
  await login(page, process.env.E2E_USERNAME || 'e2e_journalist', '/journalist/dashboard/');
  await clearFollow(page, 'author', process.env.E2E_USERNAME || 'e2e_journalist');
  await clearFollow(page, 'category', 'news');

  await page.goto(articlePath);
  await expect(page.locator('#correction-history-title')).toBeVisible();
  await expect(page.locator('.article-correction-history')).toContainText('The verified figure is 14.');
  await expect(page.locator('audio[data-audio-article]')).toBeVisible();

  const authorFollow = page.locator('[data-follow-type="author"]');
  const authorFollowSaved = page.waitForResponse((response) => response.url().includes('/reader/interests/') && response.request().method() === 'POST');
  await authorFollow.click();
  expect((await authorFollowSaved).ok()).toBeTruthy();
  await expect(authorFollow).toHaveAttribute('aria-pressed', 'true');
  const topicFollow = page.locator('[data-follow-type="category"]');
  const topicFollowSaved = page.waitForResponse((response) => response.url().includes('/reader/interests/') && response.request().method() === 'POST');
  await topicFollow.click();
  expect((await topicFollowSaved).ok()).toBeTruthy();
  await expect(topicFollow).toHaveAttribute('aria-pressed', 'true');

  await page.goto('/account/settings/#reading-collections');
  await page.locator('#reading-collection-form [name="name"]').fill(collectionName);
  await page.locator('#reading-collection-form [type="submit"]').click();
  const collection = page.locator('.reading-collection').filter({ hasText: collectionName });
  await expect(collection).toBeVisible();

  await page.goto(articlePath);
  await page.locator('#article-collection-select').selectOption({ label: collectionName });
  await page.locator('#article-add-to-collection [type="submit"]').click();
  await expect(page.locator('#article-add-to-collection .account-status')).toContainText('Story saved');
  const audio = page.locator('audio[data-audio-article]');
  const mediaKey = await audio.getAttribute('data-audio-media');
  const progress = await audio.evaluate(async (player) => {
    const articleId = player.dataset.audioArticle;
    const mediaKey = player.dataset.audioMedia;
    const csrf = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
    const response = await fetch(`/articles/api/v2/articles/${articleId}/progress/`, {
      method: 'PATCH', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf) },
      body: JSON.stringify({ media_key: mediaKey, progress_percent: 40, position_seconds: 36 }),
    });
    return { status: response.status, body: await response.json() };
  });
  expect(progress.status).toBe(200);
  expect(progress.body).toMatchObject({ media_key: mediaKey, progress_percent: 40, position_seconds: 36 });

  const listResponse = await page.evaluate(async () => {
    const response = await fetch('/articles/api/v2/reading-collections/', { headers: { Accept: 'application/json' } });
    return response.json();
  });
  const savedCollection = listResponse.find((item) => item.name === collectionName);
  expect(savedCollection.items).toHaveLength(1);
  expect(savedCollection.items[0].title).toBe('E2E Public Reader Story');

  await page.goto('/account/settings/#reading-collections');
  await page.locator('.reading-collection').filter({ hasText: collectionName }).locator('[data-delete-collection]').click();
  await expect(page.locator('.reading-collection').filter({ hasText: collectionName })).toHaveCount(0);
  await page.goto(articlePath);
  await expect(authorFollow).toHaveAttribute('aria-pressed', 'true');
  const authorUnfollowSaved = page.waitForResponse((response) => response.url().includes('/reader/interests/') && response.request().method() === 'DELETE');
  await authorFollow.click();
  expect((await authorUnfollowSaved).ok()).toBeTruthy();
  await expect(authorFollow).toHaveAttribute('aria-pressed', 'false');
  await expect(topicFollow).toHaveAttribute('aria-pressed', 'true');
  const topicUnfollowSaved = page.waitForResponse((response) => response.url().includes('/reader/interests/') && response.request().method() === 'DELETE');
  await topicFollow.click();
  expect((await topicUnfollowSaved).ok()).toBeTruthy();
  await expect(topicFollow).toHaveAttribute('aria-pressed', 'false');

  await page.goto('/journalist/dashboard/');
  const browser = page.context().browser();
  const logoutResponse = page.waitForResponse((response) => response.url().includes('/api/logout/') && response.request().method() === 'POST');
  await page.locator('[data-dashboard-logout]').click();
  expect((await logoutResponse).ok()).toBeTruthy();
  await expect(page).toHaveURL(/\/$/);
  await page.close();
  const editorContext = await browser.newContext();
  const editorPage = await editorContext.newPage();
  await login(editorPage, process.env.E2E_EDITOR_USERNAME || 'e2e_editor', '/editor/dashboard/');
  const editions = await editorPage.evaluate(async () => {
    const response = await fetch('/api/newsletter/editions/', { headers: { Accept: 'application/json' } });
    return response.json();
  });
  const campaign = editions.find((item) => item.subject === 'E2E Newsletter Campaign');
  expect(campaign).toBeTruthy();
  await editorPage.goto(`/newsletter/campaign/${campaign.id}/`);
  await expect(editorPage).toHaveURL(/\/membership\/$/);
  const analyticsResponsePromise = editorPage.waitForResponse((response) => response.url().includes('/api/newsletter/analytics/'));
  await editorPage.goto('/newsletter/campaigns/');
  const analyticsResponse = await analyticsResponsePromise;
  expect(analyticsResponse.status()).toBe(200);
  await expect(editorPage.locator('#newsletter-analytics-status')).toContainText('sent campaign');
  await expect(editorPage.locator('#newsletter-analytics-list')).toContainText('E2E Newsletter Campaign');
  await expect(editorPage.locator('.newsletter-performance-row').first()).toContainText('clicks');
  await expect(editorPage.locator('.newsletter-performance-row').first().locator('span').nth(1).locator('strong')).not.toHaveText('0');
  await editorContext.close();
});
