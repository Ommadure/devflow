import { describe, expect, it } from "vitest";
import {
  FOCUS_SECONDS,
  formatClock,
  modeSelected,
  paused,
  phaseCompleted,
  remainingMs,
  reset,
  started,
  timer,
} from "./timerSlice";

const reduce = timer.reducer;
const MIN = 60_000;

describe("timer slice", () => {
  it("counts down from a deadline, so a throttled tab can't drift", () => {
    const state = reduce(undefined, started(1_000_000));
    expect(state.status).toBe("running");
    expect(remainingMs(state, 1_000_000 + 10 * MIN)).toBe(15 * MIN);
    expect(remainingMs(state, 1_000_000 + 30 * MIN)).toBe(0); // never negative
  });

  it("pauses with the time left and resumes from it", () => {
    let state = reduce(undefined, started(0));
    state = reduce(state, paused(5 * MIN));
    expect(state).toMatchObject({ status: "paused", remainingMs: 20 * MIN, endsAt: null });
    expect(remainingMs(state, 60 * MIN)).toBe(20 * MIN); // time stands still while paused
    state = reduce(state, started(100 * MIN));
    expect(remainingMs(state, 110 * MIN)).toBe(10 * MIN);
  });

  it("cycles focus → break → focus and waits to be started", () => {
    let state = reduce(reduce(undefined, started(0)), phaseCompleted());
    expect(state).toMatchObject({ mode: "break", status: "idle", remainingMs: 5 * MIN });
    state = reduce(state, phaseCompleted());
    expect(state).toMatchObject({ mode: "focus", remainingMs: FOCUS_SECONDS * 1000 });
  });

  it("resets and switches modes", () => {
    let state = reduce(reduce(undefined, started(0)), paused(MIN));
    state = reduce(state, reset());
    expect(state).toMatchObject({ status: "idle", remainingMs: 25 * MIN });
    state = reduce(state, modeSelected("break"));
    expect(state).toMatchObject({ mode: "break", remainingMs: 5 * MIN });
  });

  it("ignores a second start and a pause while idle", () => {
    const running = reduce(undefined, started(0));
    expect(reduce(running, started(MIN))).toEqual(running);
    const idle = reduce(undefined, reset());
    expect(reduce(idle, paused(MIN))).toEqual(idle);
  });

  it.each([
    [25 * MIN, "25:00"],
    [90_500, "01:31"], // rounds up, so 00:00 only shows at the very end
    [999, "00:01"],
    [0, "00:00"],
  ])("formats %i ms as %s", (ms, text) => {
    expect(formatClock(ms)).toBe(text);
  });
});
