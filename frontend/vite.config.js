import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev: /api проксируется на Flask (python wsgi.py, порт 5000)
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:5000" } },
});
