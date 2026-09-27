import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { json, mockFetch } from "@/test/fetchMock";
import { page, snippet } from "@/test/factories";
import { renderWithProviders, signedInState } from "@/test/utils";
import { SnippetsPage } from "./SnippetsPage";

function renderPage() {
  return renderWithProviders(<SnippetsPage />, { store: makeStore(signedInState()) });
}

describe("SnippetsPage", () => {
  it("lists snippets with their tags and language", async () => {
    mockFetch({
      "GET /api/v1/snippets": () => json(page([snippet({ title: "Debounce", tags: ["timing", "react"] })])),
      "GET /api/v1/snippets/tags": () => json([{ tag: "timing", count: 1 }]),
    });
    renderPage();

    const card = await screen.findByRole("article", { name: "Debounce" });
    expect(within(card).getByText("javascript")).toBeInTheDocument();
    expect(within(card).getByText("#react")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /#timing/ })).toBeInTheDocument();
  });

  it("searches after typing pauses and labels how each result matched", async () => {
    const api = mockFetch({
      "GET /api/v1/snippets": () => json(page([])),
      "GET /api/v1/snippets/tags": () => json([]),
      "GET /api/v1/snippets/search": () =>
        json({
          items: [
            { ...snippet({ title: "Throttle" }), score: 0.0164, match_type: "semantic" },
            { ...snippet({ title: "useDebounce" }), score: 0.0161, match_type: "both" },
          ],
        }),
    });
    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Search snippets"), "stop a function firing too often");

    const throttle = await screen.findByRole("article", { name: "Throttle" });
    expect(within(throttle).getByText("Semantic")).toBeInTheDocument();
    const debounce = screen.getByRole("article", { name: "useDebounce" });
    expect(within(debounce).getByText("Keyword + meaning")).toBeInTheDocument();
    expect(screen.getByText("2 results, best first")).toBeInTheDocument();

    const searches = api.calls.filter((c) => c.url.includes("/snippets/search"));
    expect(searches).toHaveLength(1); // one request for the whole phrase, not one per key
    const params = new URL(searches[0]!.url).searchParams;
    expect([params.get("q"), params.get("mode")]).toEqual(["stop a function firing too often", "hybrid"]);
  });

  it("switches the search mode", async () => {
    const api = mockFetch({
      "GET /api/v1/snippets": () => json(page([])),
      "GET /api/v1/snippets/tags": () => json([]),
      "GET /api/v1/snippets/search": () => json({ items: [] }),
    });
    renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Search snippets"), "debounce");
    await user.click(screen.getByRole("button", { name: "Keyword" }));

    await waitFor(() => {
      const last = new URL(api.calls.at(-1)!.url).searchParams;
      expect(last.get("mode")).toBe("keyword");
    });
    expect(await screen.findByText("No snippets match these filters.")).toBeInTheDocument();
  });

  it("marks snippets that are still being indexed", async () => {
    mockFetch({
      "GET /api/v1/snippets": () =>
        json(page([snippet({ title: "Fresh", embedding_status: "pending" }), snippet({ title: "Old" })])),
      "GET /api/v1/snippets/tags": () => json([]),
    });
    renderPage();

    const fresh = await screen.findByRole("article", { name: "Fresh" });
    expect(within(fresh).getByText("Indexing…")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Old" })).queryByText("Indexing…")).toBeNull();
  });

  it("filters by tag and favourites", async () => {
    const api = mockFetch({
      "GET /api/v1/snippets": () => json(page([snippet()])),
      "GET /api/v1/snippets/tags": () => json([{ tag: "timing", count: 1 }]),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /#timing/ }));
    await user.click(screen.getByRole("button", { name: "Favourites" }));

    await waitFor(() => {
      const last = new URL(api.calls.at(-1)!.url).searchParams;
      expect([last.get("tag"), last.get("favorite")]).toEqual(["timing", "true"]);
    });
  });

  it("adds a snippet through the modal", async () => {
    const api = mockFetch({
      "GET /api/v1/snippets": () => json(page([])),
      "GET /api/v1/snippets/tags": () => json([]),
      "POST /api/v1/snippets": () => json(snippet(), 201),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Add your first snippet" }));
    const dialog = screen.getByRole("dialog", { name: "Add snippet" });
    await user.type(within(dialog).getByLabelText("Title"), "Debounce");
    await user.type(within(dialog).getByLabelText(/Tags/), "React Hooks, timing");
    await user.type(within(dialog).getByLabelText("Code"), "debounce()");
    await user.click(within(dialog).getByRole("button", { name: "Add snippet" }));

    await waitFor(() => expect(api.count("POST /api/v1/snippets")).toBe(1));
    const sent = api.calls.find((c) => c.method === "POST")!;
    expect(await sent.json()).toMatchObject({
      title: "Debounce",
      code: "debounce()",
      tags: ["react-hooks", "timing"],
      description: null,
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("deletes after confirming", async () => {
    const target = snippet({ title: "Old hack" });
    const api = mockFetch({
      "GET /api/v1/snippets": () => json(page([target])),
      "GET /api/v1/snippets/tags": () => json([]),
      [`DELETE /api/v1/snippets/${target.id}`]: () => new Response(null, { status: 204 }),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Delete Old hack" }));
    const dialog = screen.getByRole("dialog", { name: "Delete snippet?" });
    expect(api.count(`DELETE /api/v1/snippets/${target.id}`)).toBe(0); // not before confirming
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(api.count(`DELETE /api/v1/snippets/${target.id}`)).toBe(1));
  });

  it("loads the next page with the cursor", async () => {
    const api = mockFetch({
      "GET /api/v1/snippets": (request) =>
        new URL(request.url).searchParams.get("cursor") === "c2"
          ? json(page([snippet({ title: "Second page" })]))
          : json(page([snippet({ title: "First page" })], "c2")),
      "GET /api/v1/snippets/tags": () => json([]),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Load more" }));

    expect(await screen.findByRole("article", { name: "Second page" })).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "First page" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    expect(api.count("GET /api/v1/snippets")).toBe(2);
  });

  it("copies the code", async () => {
    mockFetch({
      "GET /api/v1/snippets": () => json(page([snippet({ title: "Debounce", code: "debounce()" })])),
      "GET /api/v1/snippets/tags": () => json([]),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Copy Debounce" }));

    // userEvent.setup() provides the clipboard; read back what was written.
    expect(await navigator.clipboard.readText()).toBe("debounce()");
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();
  });
});
