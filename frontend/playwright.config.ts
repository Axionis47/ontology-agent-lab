import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3047",
    httpCredentials: {
      username: "oak",
      password: "oak-e2e-private-preview-password",
    },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        ".venv/bin/python -m uvicorn tests.mcp_server:app --host 127.0.0.1 --port 9147 --no-access-log --log-level critical",
      cwd: "../backend",
      url: "http://127.0.0.1:9147/health",
      reuseExistingServer: false,
    },
    {
      command: ".venv/bin/python -m scripts.e2e_server",
      cwd: "../backend",
      url: "http://127.0.0.1:8047/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run start -- -p 3047",
      url: "http://localhost:3047",
      reuseExistingServer: false,
      env: {
        OAK_API_URL: "http://127.0.0.1:8047",
        OAK_API_KEY: "e2e-private-key-" + "x".repeat(32),
        OAK_LOCAL_PREVIEW: "false",
        OAK_PREVIEW_USER: "oak",
        OAK_PREVIEW_PASSWORD: "oak-e2e-private-preview-password",
      },
    },
  ],
});
