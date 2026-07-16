import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const demoDir = fileURLToPath(new URL("../../examples/demo", import.meta.url));

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8100",
    trace: "on-first-retry",
  },
  webServer: {
    command: "rm -rf data && ../../.venv/bin/python -m app.main && ../../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100",
    cwd: demoDir,
    url: "http://127.0.0.1:8100/",
    timeout: 60000,
    reuseExistingServer: false,
  },
});
