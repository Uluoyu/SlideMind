import { defineConfig } from '@playwright/test';

// The E2E API uses its own database/storage; never touches the user's local workspace data.
export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './artifacts/playwright',
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure',
    channel: process.env.PLAYWRIGHT_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined),
  },
  webServer: [
    {
      command: 'uv run python scripts/e2e_api.py',
      url: 'http://127.0.0.1:8001/ready',
      timeout: 60_000,
      env: { SLIDEMIND_RENDERER_URL: 'http://127.0.0.1:3002' },
    },
    {
      command: 'node apps/ppt-renderer/src/server.mjs',
      url: 'http://127.0.0.1:3002/health',
      env: { RENDERER_PORT: '3002' },
    },
    {
      command: 'npm run dev --workspace @slidemind/web -- --port 5174',
      url: 'http://127.0.0.1:5174',
      env: { SLIDEMIND_API_PROXY: 'http://127.0.0.1:8001' },
    },
  ],
});
