import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://localhost:8000';

test.describe('Login flow', () => {
  test('redirects to /login when unauthenticated', async ({ page }) => {
    await page.goto(BASE + '/');
    await page.waitForURL('**/login');
    expect(page.url()).toContain('/login');
  });

  test('shows error on wrong password', async ({ page }) => {
    await page.goto(BASE + '/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    await expect(page.locator('.error')).toBeVisible();
  });

  test('successful login redirects to dashboard', async ({ page }) => {
    await page.goto(BASE + '/login');
    // Use credentials from config.yaml (default: admin/changeme)
    await page.fill('input[type="text"]', process.env.SOLAR_USER || 'admin');
    await page.fill('input[type="password"]', process.env.SOLAR_PASS || 'changeme');
    await page.click('button[type="submit"]');
    await page.waitForURL(BASE + '/');
    expect(page.url()).toBe(BASE + '/');
  });
});

test.describe('SPA routing', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto(BASE + '/login');
    await page.fill('input[type="text"]', process.env.SOLAR_USER || 'admin');
    await page.fill('input[type="password"]', process.env.SOLAR_PASS || 'changeme');
    await page.click('button[type="submit"]');
    await page.waitForURL(BASE + '/');
  });

  test('direct navigation to /history works', async ({ page }) => {
    await page.goto(BASE + '/history');
    // Should NOT show 404
    await expect(page.locator('h2')).toContainText('Verlauf');
  });

  test('direct navigation to /stats works', async ({ page }) => {
    await page.goto(BASE + '/stats');
    await expect(page.locator('h2')).toContainText('Statistik');
  });
});

test.describe('Live dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE + '/login');
    await page.fill('input[type="text"]', process.env.SOLAR_USER || 'admin');
    await page.fill('input[type="password"]', process.env.SOLAR_PASS || 'changeme');
    await page.click('button[type="submit"]');
    await page.waitForURL(BASE + '/');
  });

  test('shows metric cards on live page', async ({ page }) => {
    // Six metric cards should be visible
    const cards = page.locator('.card');
    await expect(cards).toHaveCount(6);
  });

  test('status badge is visible', async ({ page }) => {
    await expect(page.locator('.status-badge')).toBeVisible();
  });
});
