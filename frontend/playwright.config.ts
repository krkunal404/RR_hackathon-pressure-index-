import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/**
 * End-to-end tests run against the FastAPI server, which also serves the built
 * React app. Build first (`npm run build`), then `npm run test:e2e`.
 */
const python = path.join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:8010', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: `"${python}" -m uvicorn backend.main:app --app-dir "${projectRoot}" --port 8010`,
    url: 'http://127.0.0.1:8010/api/health',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
