import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { makeStore } from "@/app/store";
import { SnippetForm } from "@/features/snippets";
import { json, mockFetch, sse, sseResponse } from "@/test/fetchMock";
import { snippet } from "@/test/factories";
import { renderWithProviders, signedInState } from "@/test/utils";
import { AiUsageBadge } from "./AiUsageBadge";
import { AskNotesPanel } from "./AskNotesPanel";
import { ExplainPanel } from "./ExplainPanel";

const store = () => makeStore(signedInState());

describe("ExplainPanel", () => {
  it("streams the explanation at the chosen level", async () => {
    const target = snippet({ title: "Debounce" });
    const api = mockFetch({
      [`POST /api/v1/snippets/${target.id}/ai/explain`]: () =>
        sseResponse([sse("token", { text: "It **waits** " }), sse("token", { text: "for a pause." }), sse("done", {})]),
      "GET /api/v1/me/ai-usage": () => json({ used: 1, limit: 50, remaining: 49, resets_at: "2026-09-28T00:00:00Z" }),
    });
    renderWithProviders(<ExplainPanel snippet={target} />, { store: store() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "expert" }));

    expect(await screen.findByText("waits")).toHaveProperty("tagName", "STRONG");
    expect(screen.getByText(/for a pause/)).toBeInTheDocument();
    const sent = api.calls.find((c) => c.url.endsWith("/ai/explain"))!;
    expect(await sent.json()).toEqual({ level: "expert" });
  });

  it("stops mid-answer by aborting the request", async () => {
    const target = snippet();
    let signal: AbortSignal | null = null;
    mockFetch({
      [`POST /api/v1/snippets/${target.id}/ai/explain`]: (request) => {
        signal = request.signal;
        return sseResponse([sse("token", { text: "Partial answer" })], { hang: true });
      },
      "GET /api/v1/me/ai-usage": () => json({ used: 1, limit: 50, remaining: 49, resets_at: "2026-09-28T00:00:00Z" }),
    });
    renderWithProviders(<ExplainPanel snippet={target} />, { store: store() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Explain" }));
    await screen.findByText("Partial answer");
    await user.click(screen.getByRole("button", { name: "Stop" }));

    expect(await screen.findByText("Stopped.")).toBeInTheDocument();
    expect(signal!.aborted).toBe(true);
  });

  it("shows an error event's message", async () => {
    const target = snippet();
    mockFetch({
      [`POST /api/v1/snippets/${target.id}/ai/explain`]: () =>
        sseResponse([sse("error", { code: "AI_FAILED", message: "The AI service failed." })]),
      "GET /api/v1/me/ai-usage": () => json({ used: 1, limit: 50, remaining: 49, resets_at: "2026-09-28T00:00:00Z" }),
    });
    renderWithProviders(<ExplainPanel snippet={target} />, { store: store() });
    await userEvent.setup().click(screen.getByRole("button", { name: "Explain" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The AI service failed.");
  });
});

describe("AskNotesPanel", () => {
  it("renders the answer with clickable citations that open the note", async () => {
    mockFetch({
      "POST /api/v1/notes/ask": () =>
        sseResponse([
          sse("sources", [{ n: 1, note_id: "note-1", note_title: "Runbook", heading: "Deploy", excerpt: "…" }]),
          sse("token", { text: "Run the migrations [1]. Also [4]." }),
          sse("done", {}),
        ]),
      "GET /api/v1/me/ai-usage": () => json({ used: 1, limit: 50, remaining: 49, resets_at: "2026-09-28T00:00:00Z" }),
    });
    const onOpenNote = vi.fn();
    renderWithProviders(<AskNotesPanel onOpenNote={onOpenNote} />, { store: store() });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Question"), "how do I deploy?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await user.click(await screen.findByRole("button", { name: "Open source 1" }));
    expect(onOpenNote).toHaveBeenCalledWith("note-1");
    expect(screen.queryByRole("button", { name: "Open source 4" })).toBeNull(); // no such source
    expect(within(screen.getByRole("list", { name: "Sources" })).getByText(/Runbook/)).toBeInTheDocument();
  });
});

describe("tag suggestions in the edit form", () => {
  it("adds only the suggestions the user picks", async () => {
    const target = snippet({ tags: ["timing"], language: null });
    mockFetch({
      [`POST /api/v1/snippets/${target.id}/ai/tags`]: () =>
        json({ language: "javascript", tags: ["timing", "debounce"], description: "Delays calls." }),
    });
    renderWithProviders(<SnippetForm snippet={target} onDone={() => {}} />, { store: store() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Suggest tags with AI" }));
    expect(await screen.findByRole("button", { name: "Add tag debounce" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add tag timing" })).toBeNull(); // already there

    await user.click(screen.getByRole("button", { name: "Add tag debounce" }));
    await user.click(screen.getByRole("button", { name: "Use language javascript" }));

    expect(screen.getByLabelText(/Tags/)).toHaveValue("timing, debounce");
    expect(screen.getByLabelText("Language")).toHaveValue("javascript");
  });
});

describe("AiUsageBadge", () => {
  it("shows what's left today", async () => {
    mockFetch({
      "GET /api/v1/me/ai-usage": () => json({ used: 38, limit: 50, remaining: 12, resets_at: "2026-09-28T00:00:00Z" }),
    });
    renderWithProviders(<AiUsageBadge />, { store: store() });
    await waitFor(() => expect(screen.getByText("12/50 AI requests left today")).toBeInTheDocument());
  });
});
