import { API_BASE, type SessionOut } from "./types";

export type RefreshOutcome =
  | { kind: "ok"; session: SessionOut }
  | { kind: "signed-out" } // the refresh cookie is missing, expired or revoked
  | { kind: "unavailable" }; // network or server trouble: don't throw the user out for it

let inflight: Promise<RefreshOutcome> | null = null;

/**
 * Trade the HttpOnly refresh cookie for a new access token — at most one request at a time.
 *
 * Refresh tokens rotate: each one works exactly once. If three requests hit 401 together and
 * each refreshed on its own, the second and third would present an already-used token, and
 * the server would treat that as theft and revoke the whole session. So every caller shares
 * one in-flight promise, and a Web Lock extends that to other tabs of the app.
 */
export function refreshSession(): Promise<RefreshOutcome> {
  inflight ??= withCrossTabLock(() => requestRefresh()).finally(() => {
    inflight = null;
  });
  return inflight;
}

async function requestRefresh(retried = false): Promise<RefreshOutcome> {
  let response: Response;
  try {
    // Same-origin POST: the browser attaches the cookie and an Origin header by itself.
    response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });
  } catch {
    return { kind: "unavailable" };
  }
  if (response.ok) return { kind: "ok", session: (await response.json()) as SessionOut };
  if (response.status === 401 && !retried && (await errorCode(response)) === "REFRESH_TOKEN_ROTATED") {
    // Another tab rotated the token a moment ago; the cookie jar already holds its successor.
    return requestRefresh(true);
  }
  if (response.status === 401 || response.status === 403) return { kind: "signed-out" };
  return { kind: "unavailable" };
}

async function errorCode(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { error?: { code?: string } };
    return body.error?.code ?? null;
  } catch {
    return null;
  }
}

function withCrossTabLock<T>(fn: () => Promise<T>): Promise<T> {
  // Web Locks (all modern browsers): a second tab waits for the first tab's refresh to
  // finish, then refreshes with the newer cookie instead of racing it.
  if (typeof navigator !== "undefined" && "locks" in navigator && navigator.locks) {
    return navigator.locks.request("devflow-refresh", fn);
  }
  return fn();
}

/** Tests only: forget a refresh left in flight by a previous test. */
export function resetRefreshStateForTests(): void {
  inflight = null;
}
