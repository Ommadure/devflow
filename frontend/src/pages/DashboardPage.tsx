import { Link } from "react-router";
import { useAppSelector } from "@/app/hooks";
import { browserTimeZone, useGetSummaryQuery } from "@/features/pomodoro";
import { selectUser } from "@/lib/api/authSession";
import type { DashboardSummary } from "@/lib/api/types";
import { MODULES, type Module } from "./modules";

/** What each built module's tile counts; modules from later phases show their phase. */
function statFor(module: Module, summary: DashboardSummary | undefined): string | null {
  if (!summary) return null;
  switch (module.path) {
    case "/snippets":
      return `${summary.snippets} ${summary.snippets === 1 ? "snippet" : "snippets"}`;
    case "/notes":
      return `${summary.notes} ${summary.notes === 1 ? "note" : "notes"}`;
    case "/timer":
      return `${summary.focus_sessions_today} today · ${summary.focus_sessions} total`;
    default:
      return null;
  }
}

export function DashboardPage() {
  const user = useAppSelector(selectUser);
  const { data: summary } = useGetSummaryQuery(browserTimeZone());

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-1 text-sm text-text/70">Signed in as {user?.email}.</p>
      </header>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {MODULES.map((module, index) => {
          const { path, title, description, icon: Icon, phase } = module;
          const stat = statFor(module, summary);
          return (
            <li key={path} className="animate-fade-up" style={{ "--i": index } as React.CSSProperties}>
              <Link to={path} className="card flex h-full flex-col gap-3 transition-colors hover:border-accent/60">
                <Icon aria-hidden className="size-6 text-accent" />
                <span className="font-semibold">{title}</span>
                <span className="text-sm text-text/70">{description}</span>
                <span className="mt-auto w-fit rounded-full bg-surface-2 px-2 py-0.5 text-xs text-text/70">
                  {phase <= 3 ? (stat ?? "…") : phase <= 6 ? "Open" : `Arrives in phase ${phase}`}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
