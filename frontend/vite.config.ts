/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run preview` serves the production headers (CSP included) from vercel.json, so a
// CSP mistake shows up in the browser console locally instead of after a deploy.
const vercel = JSON.parse(
  readFileSync(new URL("./vercel.json", import.meta.url), "utf8"),
) as {
  headers: { source: string; headers: { key: string; value: string }[] }[];
};
const productionHeaders = Object.fromEntries(
  vercel.headers
    .find((rule) => rule.source === "/(.*)")!
    .headers.filter(({ key }) => key !== "Strict-Transport-Security") // localhost is http
    .map(({ key, value }) => [key, value]),
);

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
  preview: {
    headers: productionHeaders,
    proxy: { "/api/v1": process.env.API_URL ?? "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
