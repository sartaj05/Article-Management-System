const { test, expect } = require('@playwright/test');

// Exercise real intrinsic image dimensions, a missing cover, and long titles.
const cover = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="#233c60"/></svg>')}`;

for (const width of [320, 360, 768, 1024, 1440]) {
  for (const count of [1, 3]) {
    test(`${count} article cards do not overlap at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.route('**/articles/api/v2/discover/**', (route) => route.fulfill({ json: {
        next: null,
        results: Array.from({ length: count }, (_, index) => ({
          id: index + 1,
          title: index === 1 ? 'Averylongunbrokenarticletitlethatmuststayinsideitscolumn' : 'How a Digital Newsroom Builds Trust',
          summary: 'Clear reporting, careful editing, and a wider perspective on the stories that matter.',
          author_name: 'Newsroom reporter',
          category: 'news',
          image: index % 2 === 0 ? cover : null,
        })),
      } }));
      await page.goto('/');
      await expect(page.locator('.article-card')).toHaveCount(count);
      const layout = await page.locator('.article-card').evaluateAll((cards) => cards.map((card) => {
        const bounds = card.getBoundingClientRect();
        const coverBounds = card.querySelector('.article-cover').getBoundingClientRect();
        const info = card.querySelector('.article-info').getBoundingClientRect();
        const title = card.querySelector('h3').getBoundingClientRect();
        return {
          overlap: Math.min(coverBounds.right, info.right) - Math.max(coverBounds.left, info.left) > 1 &&
            Math.min(coverBounds.bottom, info.bottom) - Math.max(coverBounds.top, info.top) > 1,
          coverContained: coverBounds.left >= bounds.left - 1 && coverBounds.right <= bounds.right + 1,
          textContained: title.left >= info.left && title.right <= info.right + 1 && info.right <= bounds.right + 1,
          textOverflow: card.querySelector('.article-info').scrollWidth > info.width + 1,
        };
      }));
      for (const card of layout) {
        expect(card).toEqual({ overlap: false, coverContained: true, textContained: true, textOverflow: false });
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    });
  }
}
