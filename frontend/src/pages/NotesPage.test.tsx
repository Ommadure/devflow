import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { json, mockFetch } from "@/test/fetchMock";
import { note, page } from "@/test/factories";
import { renderWithProviders, signedInState } from "@/test/utils";
import { NotesPage } from "./NotesPage";

function renderPage() {
  return renderWithProviders(<NotesPage />, { store: makeStore(signedInState()) });
}

describe("NotesPage", () => {
  it("creates a note and opens it in the editor", async () => {
    const created = note({ title: "", content: "" });
    const api = mockFetch({
      "GET /api/v1/notes": () => json(page([])),
      "POST /api/v1/notes": () => json(created, 201),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "New" }));

    expect(await screen.findByLabelText("Title")).toHaveValue("");
    expect(api.count(`GET /api/v1/notes/${created.id}`)).toBe(0); // seeded from the POST
  });

  it("autosaves after typing stops", async () => {
    const existing = note({ title: "Plan", content: "" });
    const api = mockFetch({
      "GET /api/v1/notes": () => json(page([existing])),
      [`GET /api/v1/notes/${existing.id}`]: () => json(existing),
      [`PATCH /api/v1/notes/${existing.id}`]: async (request) =>
        json({ ...existing, ...(await request.json()), updated_at: new Date().toISOString() }),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /^Plan/ }));
    await user.type(await screen.findByLabelText("Content (markdown)"), "- ship phase 3");

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Saved")).toBeInTheDocument(), { timeout: 3000 });
    const patches = api.calls.filter((c) => c.method === "PATCH");
    expect(patches).toHaveLength(1);
    expect(await patches[0]!.json()).toEqual({ title: "Plan", content: "- ship phase 3" });
  });

  it("previews markdown without running embedded HTML", async () => {
    const existing = note({ title: "Risky", content: "**bold** <img src=x onerror=alert(1)>" });
    mockFetch({
      "GET /api/v1/notes": () => json(page([existing])),
      [`GET /api/v1/notes/${existing.id}`]: () => json(existing),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /^Risky/ }));
    await user.click(await screen.findByRole("button", { name: "preview" }));

    const editor = screen.getByRole("region", { name: "Editor" });
    expect(within(editor).getByText("bold").tagName).toBe("STRONG");
    expect(editor.querySelector("img")).toBeNull();
  });

  it("deletes the open note and closes the editor", async () => {
    const existing = note({ title: "Scratch" });
    mockFetch({
      "GET /api/v1/notes": () => json(page([existing])),
      [`GET /api/v1/notes/${existing.id}`]: () => json(existing),
      [`DELETE /api/v1/notes/${existing.id}`]: () => new Response(null, { status: 204 }),
    });
    const { store } = renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /^Scratch/ }));
    await user.click(screen.getByRole("button", { name: "Delete Scratch" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(store.getState().notesUi.activeNoteId).toBeNull());
  });
});
