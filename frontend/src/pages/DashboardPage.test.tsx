import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, signedInState } from "@/test/utils";
import { DashboardPage } from "./DashboardPage";

describe("DashboardPage", () => {
  it("shows counts from the server, in the browser's timezone", async () => {
    const api = mockFetch({
      "GET /api/v1/dashboard/summary": () =>
        json({ snippets: 3, notes: 1, focus_sessions: 12, focus_sessions_today: 2 }),
    });
    renderWithProviders(<DashboardPage />, { store: makeStore(signedInState()) });

    expect(await screen.findByText("3 snippets")).toBeInTheDocument();
    expect(screen.getByText("1 note")).toBeInTheDocument();
    expect(screen.getByText("2 today · 12 total")).toBeInTheDocument();
    expect(screen.getAllByText("Open")).toHaveLength(2); // GitHub and API Tester (phase 6)
    const tz = new URL(api.calls[0]!.url).searchParams.get("tz");
    expect(tz).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone);
  });
});
