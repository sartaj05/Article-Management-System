const { test, expect: baseExpect } = require('@playwright/test');
const expect = baseExpect.configure({timeout: 30_000});

const password = process.env.E2E_PASSWORD || 'StrongPass123!';
const roles = {
  journalist: ['/journalist/dashboard/', process.env.E2E_USERNAME || 'e2e_journalist'],
  editor: ['/editor/dashboard/', process.env.E2E_EDITOR_USERNAME || 'e2e_editor'],
  admin: ['/adminMain/dashboard/', process.env.E2E_ADMIN_USERNAME || 'e2e_admin'],
};
async function login(page, role) {
  await page.goto('/login-template/');
  await page.locator('#username').fill(roles[role][1]);
  await page.locator('#password').fill(password);
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(roles[role][0] + '$'));
  await page.waitForLoadState('load');
}
async function logout(page, role) {
  await page.locator('[data-dashboard-logout]').first().click();
  await expect(page).toHaveURL(new URL('/', page.url()).href);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('access_token'))).toBeNull();
  await page.goto(roles[role][0]);
  await expect(page).toHaveURL(/login-template/);
}
async function closeNotice(page) {
  await page.locator('[data-dialog-confirm]').click();
}

test('invalid login, existing session login, and logout for each role', async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto('/login-template/');
  await page.locator('#username').fill(`unknown_test_${Date.now()}`);
  await page.locator('#password').fill('DefinitelyIncorrect123!');
  await page.locator('#login-form button[type="submit"]').click();
  await expect(page.locator('[data-auth-message]')).toHaveClass(/is-error/);
  for (const role of ['journalist', 'editor', 'admin']) {
    await login(page, role);
    expect((await page.context().cookies()).find(cookie => cookie.name === 'sessionid').expires).toBe(-1);
    // Re-authenticate while the session cookie is still present (CSRF regression).
    await login(page, role);
    await logout(page, role);
  }
});

test('journalist drafts and edits, editor rejects then publishes, admin manages the result', async ({ page, request }) => {
  test.setTimeout(180_000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const title = `QA story ${Date.now()}`;
  let articleId, authorToken, adminToken;
  try {
    await login(page, 'journalist');
    authorToken = await page.evaluate(() => localStorage.getItem('access_token'));
    await page.locator('#create-article-link').click();
    await page.locator('#title').fill(title);
    await page.locator('#subtitle').fill('Testing the editorial workflow');
    await page.locator('#content').fill("The reporter's article checks quotes, editing, and publication.");
    await page.locator('#emailid').fill('qa@example.org');
    await page.locator('#next-to-page2').click();
    await expect(page.locator('#page2')).toHaveClass(/active/);
    await page.locator('#prev-to-page1').click();
    await expect(page.locator('#title')).toHaveValue(title);
    await page.locator('#next-to-page2').click();
    await page.locator('#tags').fill('tech,political');
    await page.locator('#category').selectOption('features');
    await page.locator('#publish_date').fill(new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10));
    await page.locator('[name="agreed_to_terms"]').check();
    const created = page.waitForResponse(response => response.url().includes('/api/articles/create/') && response.request().method() === 'POST');
    await page.getByRole('button', {name: 'Save draft', exact: true}).click();
    const response = await created;
    expect(response.status(), await response.text()).toBe(201);
    const article = await response.json(); articleId = article.id;
    expect(article.tags).toBe('tech,political');
    await expect(page.locator('#success-modal')).toBeHidden();
    let row = page.locator(`#article-${articleId}`);
    await row.locator('.view-article').click();
    await expect(page.locator('#modal-content')).toContainText("reporter's article");
    await page.keyboard.press('Escape');
    await row.locator('.edit-article').click();
    await page.locator('#editContent').fill("The reporter's updated story is ready for review.");
    await page.locator('#editTags').fill('tech');
    await page.locator('#edit-article-form [type="submit"]').click();
    await expect(page.locator('#successModal')).toBeVisible();
    await page.keyboard.press('Escape');
    { const submitted = page.waitForResponse(response => response.url().endsWith(`/articles/${articleId}/submit/`));
      await row.locator('[data-action="submit"]').click();
      const result = await submitted; expect(result.ok()).toBeTruthy(); }
    await expect(row.locator('.status-badge')).toHaveText('Submitted');
    await logout(page, 'journalist');

    await login(page, 'editor');
    await page.locator('#manage-articles-btn').click();
    row = page.locator(`#article-list tr[data-article-id="${articleId}"]`);
    await row.locator('.reject-btn').click();
    await page.locator('[data-dialog-input]').fill('Please add a source before publishing.');
    await closeNotice(page);
    await expect(row.locator('.status-badge')).toHaveText('Rejected');
    await closeNotice(page);
    await logout(page, 'editor');

    await login(page, 'journalist');
    await page.locator('#article-list-link').click();
    row = page.locator(`#article-${articleId}`);
    await expect(row).toContainText('Please add a source');
    { const submitted = page.waitForResponse(response => response.url().endsWith(`/articles/${articleId}/submit/`));
      await row.locator('[data-action="submit"]').click();
      const result = await submitted; expect(result.ok()).toBeTruthy(); }
    await expect(row.locator('.status-badge')).toHaveText('Submitted');
    await logout(page, 'journalist');

    await login(page, 'editor');
    await page.locator('#manage-articles-btn').click();
    row = page.locator(`#article-list tr[data-article-id="${articleId}"]`);
    await row.locator('.approve-btn').click();
    await closeNotice(page);
    await expect(row.locator('.status-badge')).toHaveText('Approved');
    await closeNotice(page);
    await row.locator('.publish-btn').click();
    await closeNotice(page);
    await expect(page.locator('#published-article-list')).toContainText(title);
    await closeNotice(page);
    await logout(page, 'editor');
    const publicArticle = await request.get(`/articles/api/v2/articles/${articleId}/`);
    expect(publicArticle.ok()).toBeTruthy();
    expect(await publicArticle.json()).toMatchObject({workflow_status: 'published', is_visible: true, tags: 'tech'});

    await login(page, 'admin');
    adminToken = await page.evaluate(() => localStorage.getItem('access_token'));
    await page.locator('.nav-link[data-page="users"]').first().click();
    await expect(page.locator('#user-list')).toContainText(roles.journalist[1]);
    await expect(page.locator('#user-list')).toContainText(roles.editor[1]);
    await page.locator('.nav-link[data-page="articles"]').first().click();
    row = page.locator(`#articles-list tr[data-article-id="${articleId}"]`);
    await row.locator('.edit-btn').click();
    await page.locator('#workflow-edit-modal [name="subtitle"]').fill('Reviewed by the admin');
    await page.locator('#workflow-edit-modal [type="submit"]').click();
    await expect(page.locator('#workflow-edit-modal')).toHaveCount(0);
    await row.locator('.delete-article-btn').click();
    await closeNotice(page);
    await expect(row).toHaveCount(0);
    expect((await request.get(`/articles/api/v2/articles/${articleId}/`)).status()).toBe(404);
    await logout(page, 'admin');
    const cachedPrivateUrls = await page.evaluate(async () => {
      const keys = await caches.keys();
      const requests = (await Promise.all(keys.map(async key => (await caches.open(key)).keys()))).flat();
      return requests.map(item => new URL(item.url).pathname).filter(path => path !== '/' && !path.startsWith('/static/'));
    });
    expect(cachedPrivateUrls).toEqual([]);
    expect(errors).toEqual([]);
  } finally {
    // Remove only the synthetic story created by this test, including after failures.
    if (articleId && authorToken) {
      if (adminToken) await request.post(`/articles/api/v2/articles/${articleId}/restore/`, {headers: {Authorization: `Bearer ${adminToken}`}});
      await request.delete(`/articles/delete/${articleId}/`, {headers: {Authorization: `Bearer ${authorToken}`}});
    }
  }
});

test('login accepts an MFA challenge and the keep-signed-in preference', async ({ page }) => {
  await page.goto('/login-template/');
  let challenged = false, submittedCode;
  await page.route('**/api/login/', async route => {
    if (!challenged) {
      challenged = true;
      await route.fulfill({status: 401, json: {detail: 'A valid authenticator code is required.', mfa_required: true}});
    } else {
      submittedCode = route.request().postDataJSON().otp;
      await route.continue();
    }
  });
  await page.locator('#username').fill(roles.journalist[1]);
  await page.locator('#password').fill(password);
  await page.locator('[name="remember"]').check();
  await page.locator('#login-form [type="submit"]').click();
  await expect(page.locator('#otp')).toBeVisible();
  await page.locator('#otp').fill('123456');
  await page.locator('#login-form [type="submit"]').click();
  await expect(page).toHaveURL(/\/journalist\/dashboard\/$/);
  expect(submittedCode).toBe('123456');
  expect((await page.context().cookies()).find(cookie => cookie.name === 'sessionid').expires).toBeGreaterThan(Date.now() / 1000);
  await page.waitForLoadState('load');
  await logout(page, 'journalist');
});

test('each role renews expired access and the sign-out page ends its session', async ({ page }) => {
  test.setTimeout(90_000);
  for (const role of Object.keys(roles)) {
    await login(page, role);
    await page.evaluate(() => localStorage.setItem('access_token', 'expired-test-access-token'));
    const renewed = page.waitForResponse(response => response.url().endsWith('/api/token/refresh/'));
    await page.evaluate(() => window.WorkspaceUI.ensureAccess());
    expect((await renewed).ok()).toBeTruthy();
    await page.reload();
    await expect(page).toHaveURL(new RegExp(roles[role][0] + '$'));
    expect(await page.evaluate(() => localStorage.getItem('access_token'))).not.toBe('expired-test-access-token');
    await page.goto('/logout-template/');
    await logout(page, role);
  }
});
