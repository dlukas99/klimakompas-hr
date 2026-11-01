import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The dependency optimizer breaks the path to MapLibre's module worker.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  worker: { format: "es" },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/tiles": {
        target: "http://localhost:3000",
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
