import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

// Ports come from the repository's .env, so the stack can run next to other projects.
const env = loadEnv("development", "..", "");
const apiPort = env.API_PORT || "8000";
const martinPort = env.MARTIN_PORT || "3000";
const webPort = Number(env.WEB_DEV_PORT || 5173);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The dependency optimizer breaks the path to MapLibre's module worker.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  worker: { format: "es" },
  server: {
    port: webPort,
    strictPort: true,
    proxy: {
      "/api": `http://localhost:${apiPort}`,
      "/tiles": {
        target: `http://localhost:${martinPort}`,
        rewrite: (path) => path.replace(/^\/tiles/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/unit/setup.ts"],
    css: false,
  },
});
