import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: { outDir: process.env.VERCEL ? "dist" : "../backend/static", emptyOutDir: true },  // Vercel publica "dist"; o Docker usa a pasta do servidor
  server: { proxy: { "/api": "http://localhost:8000" } },
});
