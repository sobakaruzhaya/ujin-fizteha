import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/browser",
  workers: 1,
  timeout: 90000,
  use: {
    baseURL: "http://127.0.0.1:8898",
    headless: true,
    reducedMotion: 'reduce',
    viewport: { width: 1440, height: 1000 },
    launchOptions: {
      args: [
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
      ],
    },
  },
  webServer: {
    command:
      'python -c "from app.orchestrator import Orchestrator; from app.control_api import ControlServer; o=Orchestrator(); o.start(); ControlServer(o,port=8898).serve_forever()"',
    url: "http://127.0.0.1:8898/api/health",
    reuseExistingServer: false,
  },
});
