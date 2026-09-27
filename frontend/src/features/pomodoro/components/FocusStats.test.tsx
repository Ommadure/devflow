import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, signedInState } from "@/test/utils";
import { FocusStats } from "./FocusStats";

describe("FocusStats", () => {
  it("shows streaks and gives screen readers the numbers as a table", async () => {
    const days = Array.from({ length: 7 }, (_, i) => ({ date: `2026-09-2${i + 1}`, sessions: i % 2, minutes: (i % 2) * 25 }));
    const api = mockFetch({
      "GET /api/v1/pomodoro/stats": () =>
        json({ range: "7d", timezone: "Asia/Kolkata", days, total_sessions: 3, total_minutes: 75, current_streak: 2, best_streak: 5 }),
    });
    renderWithProviders(<FocusStats />, { store: makeStore(signedInState()) });

    expect(await screen.findByText("Current streak (days)")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Focus minutes per day" });
    expect(within(table).getAllByRole("row")).toHaveLength(8); // header + 7 days
    const tz = new URL(api.calls[0]!.url).searchParams.get("tz");
    expect(tz).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone);
  });
});
