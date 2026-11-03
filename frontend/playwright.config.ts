import { loadEnv } from "vite";
import { defineConfig, devices } from "@playwright/test";

const webPort = loadEnv("development", "..", "").WEB_DEV_PORT || "5173";
const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${webPort}`;

// Needs the running stack: `make up`, `make api` and loaded data.
export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL },
  // With E2E_BASE_URL set, the tests run against that deployed site instead of the dev server.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: "npm run dev", url: baseURL, reuseExistingServer: true },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 360, height: 740 },
      },
    },
  ],
});
