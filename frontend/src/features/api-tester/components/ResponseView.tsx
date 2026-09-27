import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Loaders";
import { toApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils/cn";
import { useExplainErrorMutation, type ProxyRequest, type ProxyResponse } from "../api/apiTesterApi";
import { formatBytes, prettyBody } from "../lib/format";

function statusTone(status: number): string {
  if (status < 300) return "bg-success/15 text-success";
  if (status < 400) return "bg-accent/15 text-accent";
  if (status < 500) return "bg-warning/15 text-warning";
  return "bg-danger/15 text-danger";
}

export function ResponseView({ request, response }: { request: ProxyRequest; response: ProxyResponse }) {
  const [tab, setTab] = useState<"body" | "headers">("body");
  const [explain, explanation] = useExplainErrorMutation();
  const body = prettyBody(response.body, response.headers as Array<[string, string]>);

  return (
    <section aria-label="Response" className="card space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className={cn("rounded-md px-2 py-1 font-mono font-semibold", statusTone(response.status))}>
          {response.status} {response.status_text}
        </span>
        <span className="text-text/60">{response.elapsed_ms} ms</span>
        <span className="text-text/60">{formatBytes(response.size_bytes)}</span>
        {response.redirects.length > 0 && (
          <span className="text-text/60" title={response.redirects.join(" → ")}>
            {response.redirects.length} redirect{response.redirects.length > 1 ? "s" : ""} → {response.final_url}
          </span>
        )}
        {response.status >= 400 && (
          <button type="button" className="btn-secondary ml-auto py-1 text-xs" disabled={explanation.isLoading}
            onClick={() => void explain({
              method: request.method ?? "GET", url: response.final_url, status: response.status,
              status_text: response.status_text, response_headers: response.headers,
              response_body: response.body.slice(0, 10_000),
            })}>
            {explanation.isLoading ? <Spinner className="size-3.5" /> : <Sparkles aria-hidden className="size-3.5" />}
            Explain this error
          </button>
        )}
      </div>

      {response.body_truncated && (
        <Alert tone="info">The response was larger than 2 MB; only the first 2 MB is shown.</Alert>
      )}
      {explanation.error && <Alert tone="error">{toApiError(explanation.error).message}</Alert>}
      {explanation.data && (
        <div className="space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3 text-sm">
          <p className="text-xs text-text/60">AI explanation · confidence: {explanation.data.confidence}</p>
          <p className="font-medium">Likely causes</p>
          <ul className="list-disc pl-5">{explanation.data.likely_causes.map((c) => <li key={c}>{c}</li>)}</ul>
          <p className="font-medium">Try</p>
          <ul className="list-disc pl-5">{explanation.data.suggested_fixes.map((f) => <li key={f}>{f}</li>)}</ul>
        </div>
      )}

      <div role="tablist" aria-label="Response parts" className="flex gap-1 border-b border-border">
        {(["body", "headers"] as const).map((name) => (
          <button key={name} role="tab" type="button" aria-selected={tab === name} onClick={() => setTab(name)}
            className={cn("-mb-px border-b-2 px-3 py-1.5 text-sm capitalize",
              tab === name ? "border-accent text-text" : "border-transparent text-text/60 hover:text-text")}>
            {name}{name === "headers" && ` (${response.headers.length})`}
          </button>
        ))}
      </div>
      {tab === "body" ? (
        <pre aria-label="Response body" className="max-h-[32rem] overflow-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">
          {body.text || <span className="text-text/40">(empty body)</span>}
        </pre>
      ) : (
        <table className="w-full text-left text-xs">
          <tbody>
            {response.headers.map(([name, value], index) => (
              <tr key={`${name}-${index}`} className="border-b border-border/50 align-top">
                <th scope="row" className="py-1 pr-4 font-mono font-medium whitespace-nowrap">{name}</th>
                <td className="py-1 font-mono break-all text-text/80">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
