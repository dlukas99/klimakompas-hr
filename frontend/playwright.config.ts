import { defineConfig, devices } from "@playwright/test";

// Needs the running stack: `make up`, `make api` and loaded data.
export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
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
