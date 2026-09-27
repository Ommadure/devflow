import { RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Loaders";
import { toApiError } from "@/lib/api/errors";
import { useGenerateInsightMutation, useListInsightsQuery, type Insight } from "../api/githubApi";

const week = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });

function InsightItem({ insight }: { insight: Insight }) {
  const stats = insight.stats as Record<string, number>;
  return (
    <article className="space-y-2 rounded-lg border border-border p-3">
      <p className="text-xs text-text/50">Week of {week.format(new Date(`${insight.week_start}T00:00:00`))}</p>
      <h3 className="font-semibold">{insight.summary.headline}</h3>
      <ul className="list-disc pl-5 text-sm text-text/80">
        {insight.summary.highlights.map((h) => <li key={h}>{h}</li>)}
      </ul>
      <p className="text-sm"><span className="text-text/50">Next week: </span>{insight.summary.suggestions.join(" ")}</p>
      <p className="font-mono text-xs text-text/50">
        {stats.commits ?? 0} commits · {stats.pull_requests_opened ?? 0} PRs opened ·{" "}
        {stats.active_days ?? 0} active days
      </p>
    </article>
  );
}

export function InsightsCard({ githubUsername }: { githubUsername: string | null }) {
  const { data: insights = [], isLoading } = useListInsightsQuery(undefined, { skip: !githubUsername });
  const [generate, generation] = useGenerateInsightMutation();

  return (
    <section aria-labelledby="insights-title" className="card space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 id="insights-title" className="flex items-center gap-2 text-lg font-semibold">
          <Sparkles aria-hidden className="size-5 text-accent" /> Weekly insights
        </h2>
        {githubUsername && (
          <button type="button" className="btn-secondary" disabled={generation.isLoading} onClick={() => void generate()}>
            {generation.isLoading ? <Spinner className="size-4" /> : <RefreshCw aria-hidden className="size-4" />}
            Generate now
          </button>
        )}
      </div>
      {!githubUsername ? (
        <p className="text-sm text-text/60">
          Set your GitHub username in <Link to="/settings" className="text-accent underline">Settings</Link> to
          get a recap of your week every Monday morning.
        </p>
      ) : (
        <>
          {generation.error && <Alert tone="error">{toApiError(generation.error).message}</Alert>}
          {isLoading ? null : insights.length === 0 ? (
            <p className="text-sm text-text/60">
              No insights yet for @{githubUsername}. They&apos;re generated every Monday, or press Generate now.
            </p>
          ) : (
            <div className="space-y-3">{insights.map((i) => <InsightItem key={i.week_start} insight={i} />)}</div>
          )}
        </>
      )}
    </section>
  );
}
