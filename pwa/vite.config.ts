import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Installable PWA (Android + iOS) served by Cloudflare Pages. Mic via getUserMedia.
// All live API calls go through the Cloudflare Worker proxy — never embed keys here.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Warp Compass",
        short_name: "Compass",
        description: "Direction to Operational Clarity",
        theme_color: "#15c95b",
        background_color: "#f3faf5",
        display: "standalone",
        orientation: "portrait",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
    }),
  ],
  // PRODUCTION: the PWA + its key-proxy Pages Functions (pwa/functions/) share one origin, so the
  // relative paths /llm, /stt, /tts resolve with no code change. LOCAL DEV, two options:
  //   • `npm run dev:cf`  → `wrangler pages dev` serves the Functions in front of Vite (full stack,
  //     reads secrets from pwa/.dev.vars) — closest to production, no proxy needed.
  //   • `npm run dev`     → plain Vite; the proxy below forwards to the standalone Worker
  //     (`wrangler dev` in worker/ on :8787) for those who prefer that split.
  server: {
    port: 5173,
    proxy: {
      "/llm": "http://localhost:8787",
      "/stt": "http://localhost:8787",
      "/tts": "http://localhost:8787",
    },
  },
});
