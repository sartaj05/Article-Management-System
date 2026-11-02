const { test, expect } = require('@playwright/test');

test.describe('deployment smoke checks', () => {
  test('health endpoint reports a ready application', async ({ request }) => {
    const response = await request.get('/health/');
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).status).toBe('healthy');
  });

  test('public responses include deployment security headers', async ({ request }) => {
    const response = await request.get('/health/');
    expect(response.headers()['x-request-id']).toBeTruthy();
    expect(response.headers()['content-security-policy']).toBeTruthy();
    expect(response.headers()['permissions-policy']).toBeTruthy();
  });
});
