import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The service in development (`uv run iplikci servis calistir`). The dev server hands it the API and the login
// link; the proxy names the service as the origin, as the service's own pages do (ADR-0007).
const SERVICE = "http://127.0.0.1:8643";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Into the Python package: the service serves the interface itself, no Node at run time (ADR-0008).
    outDir: "../src/iplikci/api/ui",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: SERVICE, changeOrigin: true, headers: { origin: SERVICE } },
      "/giris": { target: SERVICE, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});
