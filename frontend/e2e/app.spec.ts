import { expect, test } from '@playwright/test'

test('overview shows both official top-10 lists', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /when it matters/i })).toBeVisible()
  await expect(page.getByTestId('leaderboard-batters').locator('li')).toHaveCount(10)
  await expect(page.getByTestId('leaderboard-bowlers').locator('li')).toHaveCount(10)
})

test('rankings → player profile', async ({ page }) => {
  await page.goto('/rankings/bowlers')
  const first = page.getByTestId('leaderboard-bowlers').locator('li').first()
  const name = (await first.locator('.font-semibold').first().textContent())?.trim() ?? ''
  await first.click()
  await expect(page).toHaveURL(/\/players\/bowlers\/\d+/)
  await expect(page.getByTestId('player-name')).toHaveText(name)
  await expect(page.getByText('Match-by-match pressure value')).toBeVisible()
})

test('competition filter switches to competition-only ratings', async ({ page }) => {
  await page.goto('/rankings/batters')
  await expect(page.getByText('RR auction top 10')).toBeVisible()
  await page.getByTestId('filter-competition').selectOption('T20I')
  await expect(page.getByText('RR auction top 10')).toHaveCount(0)
  await expect(page.getByText(/re-estimated within T20I/)).toBeVisible()
  await expect(page.getByTestId('rankings-table').locator('tbody tr').first()).toBeVisible()
})

test('explorer filters by pressure category', async ({ page }) => {
  await page.goto('/explorer')
  await expect(page.getByTestId('explorer-table').locator('tbody tr').first()).toBeVisible()
  await page.getByTestId('explorer-category').selectOption('Extreme')
  await page.getByTestId('explorer-competition').selectOption('IPL')
  await expect(page.getByTestId('explorer-table').locator('tbody tr').first()).toBeVisible()
})

test('global search navigates to a player', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Search players').fill('kohli')
  await page.getByRole('button', { name: /Virat Kohli/ }).first().click()
  await expect(page.getByTestId('player-name')).toHaveText('Virat Kohli')
})

test('validation page shows passing checks and sensitivity grid', async ({ page }) => {
  await page.goto('/validation')
  await expect(page.getByText('No leakage into pre-ball state')).toBeVisible()
  await expect(page.getByTestId('sensitivity-grid').locator('tbody tr')).toHaveCount(13)
})

test('light is the default and dark is temporary', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('html')).toHaveClass(/light/)
  await page.getByTestId('theme-toggle').click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/light/)
})
