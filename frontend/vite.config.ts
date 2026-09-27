/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `@/features/notes` instead of `../../features/notes` (spec §6).
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    // Same-origin in dev too: the browser calls /api/*, Vite forwards it to FastAPI.
    // Production does the same with a Vercel rewrite, so the refresh cookie stays first-party.
    proxy: {
      // Exactly the API's prefix. A bare "/api" also matched the page route "/api" (the
      // API Tester), so reloading that page fetched a 404 from the backend.
      "/api/v1": process.env.API_URL ?? "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
