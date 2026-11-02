import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

// The service in development (`uv run iplikci servis calistir`). The dev server hands it the API and the login
// link; the proxy names the service as the origin, as the service's own pages do (ADR-0007).
const SERVICE = "http://127.0.0.1:8643";

// The PWA (ADR-0008): a manifest to install the interface as an app, and a service worker that keeps only the app
// shell (the built files) so it opens at once; the API's answers are never kept. Registered by a file of its own,
// never an inline script (the CSP allows none). The manifest and the icons carry nothing personal: the service
// gives them without a session, so the browser can read them as it installs.
const pwa = VitePWA({
  registerType: "autoUpdate",
  injectRegister: "script-defer",
  includeAssets: ["favicon-16.png", "favicon-32.png", "logo.png", "apple-touch-icon.png"],
  manifest: {
    name: "İplikçi Nedim",
    short_name: "İplikçi Nedim",
    description: "Kişisel finans asistanı: bankalardan gelen belgeler, defter, yorum ve bildirimler, bu bilgisayarda.",
    lang: "tr",
    dir: "ltr",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0f766e",
    icons: [
      { src: "/pwa-192x192.png", sizes: "192x192", type: "image/png" },
      { src: "/pwa-512x512.png", sizes: "512x512", type: "image/png" },
      { src: "/pwa-maskable-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
  workbox: {
    globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
    navigateFallback: "/index.html",
    // Addresses that are no page of the app: the API, the login link and the health check go to the service.
    navigateFallbackDenylist: [/^\/api\//, /^\/giris/, /^\/healthz/],
    runtimeCaching: [],
    cleanupOutdatedCaches: true,
  },
});

export default defineConfig({
  plugins: [react(), tailwindcss(), pwa],
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
    // A screen's first render with its user events takes a second or two in jsdom, and many times that on a busy
    // machine or a shared CI runner; the default five seconds turned that into failures of tests that pass.
    testTimeout: 30_000,
  },
});
