import { Plug, RefreshCw } from "lucide-react";
import { useGetMeQuery } from "@/features/auth";
import { toApiError } from "@/lib/api/errors";
import { Alert } from "./Alert";
import { Spinner } from "./Loaders";

/** Calls GET /api/v1/me and shows what came back: proof the whole auth chain works. */
export function ApiConnectionCard() {
  const { data, error, isFetching, refetch } = useGetMeQuery();
  const apiError = error ? toApiError(error) : null;

  return (
    <section aria-labelledby="api-connection-title" className="card space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 id="api-connection-title" className="flex items-center gap-2 text-lg font-semibold">
          <Plug aria-hidden className="size-5 text-accent" /> API connection
        </h2>
        <button type="button" className="btn-secondary" onClick={() => void refetch()} disabled={isFetching}>
          <RefreshCw aria-hidden className={isFetching ? "size-4 animate-spin" : "size-4"} />
          Re-check
        </button>
      </div>

      <div aria-live="polite">
        {isFetching && !data && !apiError ? (
          <p className="flex items-center gap-2 text-sm text-text/70">
            <Spinner className="size-4" /> Checking…
          </p>
        ) : apiError ? (
          <Alert tone="error">
            <p className="font-medium">
              {apiError.code}: {apiError.message}
            </p>
            {apiError.requestId && (
              <p className="mt-1 font-mono text-xs">Request ID: {apiError.requestId}</p>
            )}
            {apiError.code === "NETWORK_ERROR" && (
              <p className="mt-1 text-xs text-text/70">
                Is the API running? Start it with <code className="font-mono">docker compose up -d</code>.
              </p>
            )}
          </Alert>
        ) : data ? (
          <Alert tone="success">
            <p className="font-medium">Connected</p>
            <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-xs text-text/80">
              <dt>User ID</dt>
              <dd className="font-mono break-all">{data.id}</dd>
              <dt>Email</dt>
              <dd>{data.email}</dd>
            </dl>
          </Alert>
        ) : null}
      </div>
    </section>
  );
}
