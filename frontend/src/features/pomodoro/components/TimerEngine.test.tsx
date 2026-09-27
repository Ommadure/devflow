import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, signedInState } from "@/test/utils";
import { TimerEngine } from "./TimerEngine";

function finishedTimer(mode: "focus" | "break") {
  return makeStore({
    ...signedInState(),
    timer: { mode, status: "running", endsAt: Date.now() - 1, remainingMs: 0 },
  });
}

describe("TimerEngine", () => {
  it("records a finished focus session, announces it and switches to a break", async () => {
    const api = mockFetch({
      "POST /api/v1/pomodoro/sessions": () =>
        json({ id: "s1", completed_at: new Date().toISOString(), duration_seconds: 1500 }, 201),
    });
    const store = finishedTimer("focus");
    renderWithProviders(<TimerEngine />, { store });

    await expect.poll(() => api.count("POST /api/v1/pomodoro/sessions")).toBe(1);
    expect(await api.calls[0]!.json()).toEqual({ duration_seconds: 1500 });
    expect(store.getState().timer).toMatchObject({ mode: "break", status: "idle" });
    expect(store.getState().toasts[0]!.message).toMatch(/Focus session complete/);
  });

  it("does not record a finished break", async () => {
    const api = mockFetch({});
    const store = finishedTimer("break");
    renderWithProviders(<TimerEngine />, { store });

    await expect.poll(() => store.getState().timer.mode).toBe("focus");
    expect(api.calls).toHaveLength(0);
  });

  it("shows the countdown in the tab title while running", () => {
    const store = makeStore({
      ...signedInState(),
      timer: { mode: "focus", status: "running", endsAt: Date.now() + 90_000, remainingMs: 0 },
    });
    renderWithProviders(<TimerEngine />, { store });
    expect(document.title).toMatch(/^01:3\d · Focus — DevFlow$/);
  });
});
