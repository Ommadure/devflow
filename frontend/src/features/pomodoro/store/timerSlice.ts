import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export const FOCUS_SECONDS = 25 * 60;
export const BREAK_SECONDS = 5 * 60;

export type TimerMode = "focus" | "break";

export interface TimerState {
  mode: TimerMode;
  status: "idle" | "running" | "paused";
  /** While running: the wall-clock time (ms) it ends. Browsers throttle timers in
   *  background tabs, so counting down one tick at a time would drift; a deadline can't. */
  endsAt: number | null;
  /** While idle or paused: what's left. */
  remainingMs: number;
}

const durationMs = (mode: TimerMode) => (mode === "focus" ? FOCUS_SECONDS : BREAK_SECONDS) * 1000;

const initialState: TimerState = {
  mode: "focus",
  status: "idle",
  endsAt: null,
  remainingMs: durationMs("focus"),
};

// Reducers stay pure: the current time comes in as the payload (easy to test, too).
const withNow = (now: number = Date.now()) => ({ payload: now });

export const timer = createSlice({
  name: "timer",
  initialState,
  reducers: {
    started: {
      reducer(state, action: PayloadAction<number>) {
        if (state.status === "running") return;
        state.status = "running";
        state.endsAt = action.payload + state.remainingMs;
      },
      prepare: withNow,
    },
    paused: {
      reducer(state, action: PayloadAction<number>) {
        if (state.status !== "running" || state.endsAt === null) return;
        state.remainingMs = Math.max(0, state.endsAt - action.payload);
        state.endsAt = null;
        state.status = "paused";
      },
      prepare: withNow,
    },
    reset(state) {
      state.status = "idle";
      state.endsAt = null;
      state.remainingMs = durationMs(state.mode);
    },
    modeSelected(state, action: PayloadAction<TimerMode>) {
      state.mode = action.payload;
      state.status = "idle";
      state.endsAt = null;
      state.remainingMs = durationMs(action.payload);
    },
    /** Focus → break → focus. The next phase waits for the user to press Start. */
    phaseCompleted(state) {
      state.mode = state.mode === "focus" ? "break" : "focus";
      state.status = "idle";
      state.endsAt = null;
      state.remainingMs = durationMs(state.mode);
    },
  },
  selectors: {
    selectTimer: (state) => state,
  },
});

export const { started, paused, reset, modeSelected, phaseCompleted } = timer.actions;
export const { selectTimer } = timer.selectors;

export function remainingMs(state: TimerState, now: number): number {
  return state.status === "running" && state.endsAt !== null
    ? Math.max(0, state.endsAt - now)
    : state.remainingMs;
}

/** 90_500 ms → "01:31" (rounds up: the display never reaches 00:00 before the end). */
export function formatClock(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const minutes = Math.floor(total / 60);
  return `${String(minutes).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}
