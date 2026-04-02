import { defineConfig } from "@playwright/test";


const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT || 3000);


export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "on-first-retry",
    channel: "msedge"
  },
  webServer: {
    command: `npm run dev -- --hostname 127.0.0.1 --port ${frontendPort}`,
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: !process.env.CI,
    env: {
      NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000",
      NEXT_PUBLIC_DEFAULT_USER_ID: process.env.NEXT_PUBLIC_DEFAULT_USER_ID || "dev-user",
      NEXT_PUBLIC_DEFAULT_TENANT_ID: process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID || "dev-tenant",
      NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS: process.env.NEXT_PUBLIC_DEFAULT_ACCOUNT_IDS || "acc-001"
    }
  }
});
