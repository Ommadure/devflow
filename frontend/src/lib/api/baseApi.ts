import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import { toastShown } from "@/lib/toasts";
import { sessionStarted, signedOut, type AuthSessionState } from "./authSession";
import { refreshSession } from "./refresh";
import { API_BASE } from "./types";

const rawBaseQuery = fetchBaseQuery({
  // Absolute (same origin): browsers resolve "/api/v1" against the page anyway, but Node's
  // Request (used under Vitest) rejects relative URLs.
  baseUrl: new URL(API_BASE, window.location.origin).href,
  prepareHeaders(headers, { getState }) {
    // Read the token per request — it changes every time the session refreshes.
    const token = (getState() as { auth: AuthSessionState }).auth.accessToken;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  },
});

function urlOf(args: string | FetchArgs): string {
  return typeof args === "string" ? args : args.url;
}

/**
 * The base query every endpoint uses: attach the access token; on a 401, refresh the
 * session once and retry; if the refresh fails, sign out. Auth routes are exempt — a 401
 * from /auth/login means "wrong password", not "token expired".
 */
export const baseQueryWithReauth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> =
  async (args, api, extraOptions) => {
    let result = await rawBaseQuery(args, api, extraOptions);

    if (result.error?.status === 401 && !urlOf(args).startsWith("/auth/")) {
      const outcome = await refreshSession();
      if (outcome.kind === "ok") {
        api.dispatch(sessionStarted(outcome.session));
        result = await rawBaseQuery(args, api, extraOptions);
      } else if (outcome.kind === "signed-out") {
        api.dispatch(signedOut({ notice: "Your session has ended. Please sign in again." }));
        api.dispatch(baseApi.util.resetApiState());
      }
    }

    if (result.error?.status === 429) {
      const details = (result.error.data as { error?: { details?: { retry_after?: number } } })
        ?.error?.details;
      const seconds = details?.retry_after;
      api.dispatch(
        toastShown({
          tone: "error",
          message: seconds
            ? `Too many requests. Try again in ${seconds} s.`
            : "Too many requests. Try again shortly.",
        }),
      );
    }
    return result;
  };

/** The one RTK Query API. Features add endpoints with `baseApi.injectEndpoints`. */
export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithReauth,
  // Cache tags: a mutation "invalidates" a tag and every query "providing" it refetches.
  tagTypes: ["Me", "Snippet", "SnippetTags", "Note", "PomodoroSession", "Dashboard", "AiUsage", "GithubInsight"],
  endpoints: () => ({}),
});
