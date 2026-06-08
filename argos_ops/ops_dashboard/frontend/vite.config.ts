import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
// En dev local : Vite sert le frontend sur :5173 et proxy /api/* vers le backend
// FastAPI sur :9000 (cf. scripts/run_ops_dashboard.py). En prod (P16.B), Caddy
// servira les deux sur ops.omnividens.fr et le proxy n'est plus nécessaire.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:9000",
        changeOrigin: false,
        // L'atelier libre utilise un WebSocket (/api/atelier/ws) — proxifier
        // l'upgrade WS, sinon la connexion échoue depuis :5173.
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
