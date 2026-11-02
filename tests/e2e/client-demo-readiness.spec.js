const { test, expect } = require('@playwright/test');

test.describe('client demo public newsroom', () => {
  test('keeps the hero hierarchy readable at every configured viewport', async ({ page }) => {
    await page.goto('/');
    const desk = page.locator('.reading-desk--home');
    const hero = page.locator('.desk-masthead');
    await expect(desk).toBeVisible();
    await expect(hero).toBeVisible();
    await expect(page.locator('#desk-title')).toContainText('The newsroom');
    await expect(page.locator('.desk-masthead .button--light')).toBeVisible();

    const layout = await page.evaluate(() => {
      const masthead = document.querySelector('.desk-masthead');
      const title = document.querySelector('#desk-title');
      const cta = document.querySelector('.desk-masthead .button--light');
      const titleStyles = getComputedStyle(title);
      const mastheadStyles = getComputedStyle(masthead);
      return {
        viewport: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        heroWidth: masthead.getBoundingClientRect().width,
        titleColor: titleStyles.color,
        heroBackground: mastheadStyles.backgroundImage,
        ctaRight: cta.getBoundingClientRect().right,
      };
    });

    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport + 1);
    expect(layout.heroWidth).toBeLessThanOrEqual(layout.viewport);
    expect(layout.titleColor).not.toBe('rgb(255, 255, 255)');
    expect(layout.heroBackground).toContain('linear-gradient');
    expect(layout.ctaRight).toBeLessThanOrEqual(layout.viewport + 1);
  });
});
