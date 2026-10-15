const { defineConfig, devices } = require('@playwright/test');
const fs = require('node:fs');
const localPython = process.platform === 'win32' ? 'venv/Scripts/python.exe' : 'venv/bin/python';
const python = process.env.E2E_PYTHON || (fs.existsSync(localPython) ? localPython : 'python');
const baseURL = process.env.BASE_URL || 'http://127.0.0.1:8001';

module.exports = defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  fullyParallel: false,
  timeout: 30_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
  },
  webServer: {
    command: `"${python}" manage.py migrate --settings=config.e2e_settings --noinput && "${python}" manage.py prepare_e2e --settings=config.e2e_settings && "${python}" manage.py runserver 127.0.0.1:8001 --settings=config.e2e_settings --noreload`,
    url: `${baseURL}/login-template/`,
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
