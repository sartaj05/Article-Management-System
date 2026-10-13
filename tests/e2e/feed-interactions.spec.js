const { test, expect } = require('@playwright/test');

test('changing feeds while a request is pending shows the latest selection', async ({ page }) => {
  let releaseFeatured;
  let featuredStarted;
  const pendingFeatured = new Promise((resolve) => { releaseFeatured = resolve; });
  const started = new Promise((resolve) => { featuredStarted = resolve; });

  await page.route('**/articles/api/v2/discover/**', async (route) => {
    const mode = new URL(route.request().url()).searchParams.get('mode');
    if (mode === 'featured') {
      featuredStarted();
      await pendingFeatured;
    }
    await route.fulfill({ json: { next: null, results: [{
      id: mode === 'trending' ? 2 : 1,
      title: mode === 'trending' ? 'The latest trending story' : 'The delayed featured story',
      summary: 'A story used to verify feed navigation.',
      author_name: 'Test author',
    }] } });
  });

  try {
    await page.goto('/');
    await started;
    await page.getByRole('button', { name: 'Trending', exact: true }).click();
    await expect(page.locator('#articles-container')).toContainText('The latest trending story');
    await expect(page.locator('#articles-container')).not.toContainText('The delayed featured story');
    await expect(page.locator('#articles-container')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('[data-feed-mode="trending"]')).toHaveAttribute('aria-pressed', 'true');
  } finally {
    releaseFeatured();
  }
});
