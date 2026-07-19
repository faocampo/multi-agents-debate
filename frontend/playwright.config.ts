import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "../backend/.venv/bin/python ../e2e/fake_provider.py",
      url: "http://127.0.0.1:9999/health",
      reuseExistingServer: false,
    },
    {
      command:
        "LLM_BASE_URL=http://127.0.0.1:9999/v1 LLM_API_KEY=fake LLM_MODEL=fake-model ROLES_FILE=../frontend/test-results/e2e-roles.json ../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/docs",
      reuseExistingServer: false,
    },
    {
      command: "npm run preview -- --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
    },
  ],
});
