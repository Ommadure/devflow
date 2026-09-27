import type { Note, Snippet } from "@/lib/api/types";

let n = 0;
const nextId = () => `00000000-0000-4000-8000-${String(++n).padStart(12, "0")}`;

export function snippet(overrides: Partial<Snippet> = {}): Snippet {
  return {
    id: nextId(),
    title: "Debounce",
    description: "Delay a call until input settles",
    code: "function debounce(fn, ms) {}",
    language: "javascript",
    tags: ["timing"],
    favorite: false,
    embedding_status: "ready",
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:00Z",
    ...overrides,
  };
}

export function note(overrides: Partial<Note> = {}): Note {
  return {
    id: nextId(),
    title: "Plan",
    content: "# Phase 3",
    created_at: "2026-09-27T10:00:00Z",
    updated_at: "2026-09-27T10:00:00Z",
    ...overrides,
  };
}

export const page = <T,>(items: T[], next_cursor: string | null = null) => ({ items, next_cursor });
