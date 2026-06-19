import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
// Cockpit unifié (refonte SF) : UNE seule entrée index.html → src/main.tsx →
// AppShell. En dev, Vite sert sur :5173 et proxy /api/* vers FastAPI :9000
// (cf. scripts/run_ops_dashboard.py). Le WebSocket de l'atelier libre
// (/api/atelier/ws) est proxifié (ws: true). En prod, Caddy sert le build.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:9000",
        changeOrigin: false,
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
