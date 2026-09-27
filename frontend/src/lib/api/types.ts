import type { components } from "./schema";

/** Request/response shapes generated from the backend's OpenAPI schema (`npm run gen:api`). */
export type Schemas = components["schemas"];
export type User = Schemas["UserOut"];
export type SessionOut = Schemas["SessionOut"];
export type Snippet = Schemas["SnippetOut"];
export type TagCount = Schemas["TagCount"];
export type Note = Schemas["NoteOut"];
export type PomodoroSession = Schemas["PomodoroSessionOut"];
export type DashboardSummary = Schemas["DashboardSummary"];

/** Every list endpoint answers `{ items, next_cursor }`; null means "no more pages". */
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

/** Every API path lives under this same-origin prefix; Vite / Vercel forward it to FastAPI. */
export const API_BASE = "/api/v1";
