import { Flame, Trophy } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import { browserTimeZone, useGetStatsQuery } from "../api/pomodoroApi";

const dayLabel = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const dateLabel = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });

/** Daily focus minutes as bars, plus streaks. SVG, no chart library: one bar per day. */
export function FocusStats() {
  const [range, setRange] = useState<"7d" | "30d">("7d");
  const { data } = useGetStatsQuery({ range, tz: browserTimeZone() });
  if (!data) return null;

  const max = Math.max(25, ...data.days.map((d) => d.minutes));
  const width = 100 / data.days.length;
  return (
    <section aria-labelledby="focus-stats-title" className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 id="focus-stats-title" className="font-semibold">Focus over time</h2>
        <div role="group" aria-label="Range" className="flex gap-1 rounded-lg bg-background p-1">
          {(["7d", "30d"] as const).map((option) => (
            <button key={option} type="button" aria-pressed={range === option} onClick={() => setRange(option)}
              className={cn("rounded-md px-2 py-0.5 text-xs", range === option ? "bg-surface-2" : "text-text/60")}>
              {option === "7d" ? "7 days" : "30 days"}
            </button>
          ))}
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg bg-background p-2">
          <dd className="flex items-center justify-center gap-1 text-xl font-semibold"><Flame aria-hidden className="size-4 text-warning" />{data.current_streak}</dd>
          <dt className="text-xs text-text/50">Current streak (days)</dt>
        </div>
        <div className="rounded-lg bg-background p-2">
          <dd className="flex items-center justify-center gap-1 text-xl font-semibold"><Trophy aria-hidden className="size-4 text-accent" />{data.best_streak}</dd>
          <dt className="text-xs text-text/50">Best streak</dt>
        </div>
        <div className="rounded-lg bg-background p-2">
          <dd className="text-xl font-semibold">{data.total_minutes}</dd>
          <dt className="text-xs text-text/50">Minutes, {range}</dt>
        </div>
      </dl>

      <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="h-32 w-full" aria-hidden>
        {data.days.map((day, i) => {
          const height = (day.minutes / max) * 38;
          return (
            <rect key={day.date} x={i * width + width * 0.15} width={width * 0.7} y={40 - height} height={height}
              rx={0.6} className={day.minutes ? "fill-accent" : "fill-border"}>
              <title>{`${dateLabel.format(new Date(`${day.date}T00:00:00`))}: ${day.minutes} min`}</title>
            </rect>
          );
        })}
      </svg>
      {range === "7d" && (
        <div className="grid grid-cols-7 text-center text-xs text-text/50" aria-hidden>
          {data.days.map((d) => <span key={d.date}>{dayLabel.format(new Date(`${d.date}T00:00:00`))}</span>)}
        </div>
      )}
      {/* The same numbers for screen readers: a chart is a picture, a table is data. */}
      <table className="sr-only">
        <caption>Focus minutes per day</caption>
        <thead><tr><th scope="col">Day</th><th scope="col">Minutes</th><th scope="col">Sessions</th></tr></thead>
        <tbody>
          {data.days.map((d) => (
            <tr key={d.date}><td>{d.date}</td><td>{d.minutes}</td><td>{d.sessions}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
