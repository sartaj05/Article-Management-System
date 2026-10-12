const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  fullyParallel: false,
  timeout: 30_000,
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'python manage.py migrate --noinput && python manage.py prepare_e2e && python manage.py runserver 127.0.0.1:8000 --noreload',
    url: 'http://127.0.0.1:8000/login-template/',
    timeout: 120_000,
    reuseExistingServer: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'tablet',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 768, height: 1024 },
      },
    },
    { name: 'mobile', use: { ...devices['Pixel 5'], browserName: 'chromium' } },
    {
      name: 'narrow-mobile',
      use: {
        ...devices['Pixel 5'],
        browserName: 'chromium',
        viewport: { width: 360, height: 800 },
      },
    },
  ],
});
