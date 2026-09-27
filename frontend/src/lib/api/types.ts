import type { components } from "./schema";

/** Request/response shapes generated from the backend's OpenAPI schema (`npm run gen:api`). */
export type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type SessionOut = Schemas["SessionOut"];

/** Every API path lives under this same-origin prefix; Vite / Vercel forward it to FastAPI. */
export const API_BASE = "/api/v1";
