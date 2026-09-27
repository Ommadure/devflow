import { Pause, Play, RotateCcw } from "lucide-react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import {
  BREAK_SECONDS,
  FOCUS_SECONDS,
  FocusStats,
  browserTimeZone,
  formatClock,
  modeSelected,
  paused,
  remainingMs,
  reset,
  selectTimer,
  started,
  useGetSummaryQuery,
  useNow,
  type TimerMode,
} from "@/features/pomodoro";
import { cn } from "@/lib/utils/cn";

const MODES: Array<{ mode: TimerMode; label: string; seconds: number }> = [
  { mode: "focus", label: "Focus", seconds: FOCUS_SECONDS },
  { mode: "break", label: "Break", seconds: BREAK_SECONDS },
];

export function TimerPage() {
  const dispatch = useAppDispatch();
  const timer = useAppSelector(selectTimer);
  const running = timer.status === "running";
  const left = remainingMs(timer, useNow(running));
  const total = (timer.mode === "focus" ? FOCUS_SECONDS : BREAK_SECONDS) * 1000;
  const { data: summary } = useGetSummaryQuery(browserTimeZone());

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h1 className="text-2xl font-semibold">Focus timer</h1>

      <section aria-label="Timer" className="card space-y-6 text-center">
        <div role="group" aria-label="Mode" className="mx-auto flex w-fit gap-1 rounded-lg bg-background p-1">
          {MODES.map(({ mode, label, seconds }) => (
            <button key={mode} type="button" aria-pressed={timer.mode === mode}
              onClick={() => dispatch(modeSelected(mode))}
              className={cn("rounded-md px-4 py-1.5 text-sm",
                timer.mode === mode ? "bg-surface-2 text-text" : "text-text/60 hover:text-text")}>
              {label} {seconds / 60} min
            </button>
          ))}
        </div>

        {/* role="timer": announced when focused, not every second (aria-live is off). */}
        <p role="timer" aria-label={`${timer.mode === "focus" ? "Focus" : "Break"} time left`}
          className="font-mono text-7xl font-semibold tabular-nums">
          {formatClock(left)}
        </p>

        <div className="h-1.5 overflow-hidden rounded-full bg-border" aria-hidden>
          <div className={cn("h-full rounded-full", timer.mode === "focus" ? "bg-accent" : "bg-success")}
            style={{ width: `${100 - (left / total) * 100}%` }} />
        </div>

        <div className="flex justify-center gap-2">
          <button type="button" className="btn-primary min-w-32"
            onClick={() => dispatch(running ? paused() : started())}>
            {running ? <Pause aria-hidden className="size-4" /> : <Play aria-hidden className="size-4" />}
            {running ? "Pause" : timer.status === "paused" ? "Resume" : "Start"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => dispatch(reset())}
            disabled={timer.status === "idle"}>
            <RotateCcw aria-hidden className="size-4" /> Reset
          </button>
        </div>
      </section>

      <dl className="grid grid-cols-2 gap-4">
        <div className="card p-4 text-center">
          <dt className="text-sm text-text/60">Sessions today</dt>
          <dd className="text-3xl font-semibold">{summary?.focus_sessions_today ?? "–"}</dd>
        </div>
        <div className="card p-4 text-center">
          <dt className="text-sm text-text/60">All time</dt>
          <dd className="text-3xl font-semibold">{summary?.focus_sessions ?? "–"}</dd>
        </div>
      </dl>
      <p className="text-center text-xs text-text/50">
        The timer keeps running while you use other pages; the tab title shows what&apos;s left.
      </p>
      <FocusStats />
    </div>
  );
}
