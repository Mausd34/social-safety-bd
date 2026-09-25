import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to Django, so the browser only ever talks to one
// origin. That removes CORS from the equation entirely in development.
// Override the target with VITE_BACKEND_URL if Django runs elsewhere.
const BACKEND = process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true }
    }
  },
  build: {
    rollupOptions: {
      output: {
        // Split the heavy, rarely-changing vendor code out of the app bundle so
        // it can be cached separately and re-used across deploys.
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          maps: ["leaflet", "react-leaflet"],
          charts: ["recharts"]
        }
      }
    }
  }
});

