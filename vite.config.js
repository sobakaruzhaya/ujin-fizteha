import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
export default defineConfig({
  root: "frontend",
  base: "/web/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./frontend/src", import.meta.url)) },
  },
  build: { outDir: "../app/web/dist", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
});
