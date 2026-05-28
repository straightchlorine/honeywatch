import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('home loads and is axe-clean', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toBeVisible()
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations).toEqual([])
})
