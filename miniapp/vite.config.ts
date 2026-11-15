import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Development: `npm run dev` serves the app on http://localhost:5173 and forwards
// /api and /static to the FastAPI server on :8000, so the app and the API share
// one address (one tunnel, no CORS). Production: `npm run build` -> dist/,
// which the API serves itself.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/static": "http://localhost:8000",
    },
    // Allow the free tunnel hostnames (Vite blocks unknown hosts by default).
    allowedHosts: [".trycloudflare.com", ".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app"],
  },
  build: {
    target: "es2020",
    outDir: "dist",
    sourcemap: false,
  },
});
