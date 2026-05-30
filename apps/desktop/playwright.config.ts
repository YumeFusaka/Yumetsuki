import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://127.0.0.1:5317',
    headless: true,
  },
  webServer: {
    command: 'pnpm --dir frontend dev -- --port 5317',
    port: 5317,
    reuseExistingServer: true,
  },
})
