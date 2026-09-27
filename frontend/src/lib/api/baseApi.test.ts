import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { authApi } from "@/features/auth/api/authApi";
import { apiError, json, mockFetch } from "@/test/fetchMock";
import { USER, session, signedInState } from "@/test/utils";
import { baseApi } from "./baseApi";

// Distinct endpoints, so RTK Query doesn't merge the parallel requests into one.
const probeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    probe: build.query<{ ok: boolean }, number>({ query: (n) => `/probe/${n}` }),
  }),
});

/** A protected resource that only accepts the given token. */
function protectedBy(token: string, body: unknown = { ok: true }) {
  return (request: Request) =>
    request.headers.get("Authorization") === `Bearer ${token}`
      ? json(body)
      : apiError(401, "TOKEN_EXPIRED", "Your session has expired.");
}

describe("baseQueryWithReauth", () => {
  it("attaches the access token from the store", async () => {
    const api = mockFetch({ "GET /api/v1/me": () => json(USER) });
    const store = makeStore(signedInState("access-1"));

    await store.dispatch(authApi.endpoints.getMe.initiate());

    expect(api.calls[0]!.headers.get("Authorization")).toBe("Bearer access-1");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    const api = mockFetch({
      "GET /api/v1/me": protectedBy("access-2", USER),
      "POST /api/v1/auth/refresh": () => json(session("access-2")),
    });
    const store = makeStore(signedInState("access-1"));

    const result = await store.dispatch(authApi.endpoints.getMe.initiate());

    expect(result.data).toEqual(USER);
    expect(store.getState().auth.accessToken).toBe("access-2");
    expect(api.count("GET /api/v1/me")).toBe(2);
  });

  it("shares one refresh between concurrent 401s", async () => {
    // Refresh tokens are single-use: three separate refreshes would look like theft.
    const api = mockFetch({
      "GET /api/v1/probe/1": protectedBy("access-2"),
      "GET /api/v1/probe/2": protectedBy("access-2"),
      "GET /api/v1/probe/3": protectedBy("access-2"),
      "POST /api/v1/auth/refresh": () => json(session("access-2")),
    });
    const store = makeStore(signedInState("access-1"));

    const results = await Promise.all(
      [1, 2, 3].map((n) => store.dispatch(probeApi.endpoints.probe.initiate(n))),
    );

    expect(results.every((result) => result.data?.ok)).toBe(true);
    expect(api.count("POST /api/v1/auth/refresh")).toBe(1);
  });

  it("signs out when the refresh fails", async () => {
    mockFetch({
      "GET /api/v1/me": protectedBy("never"),
      "POST /api/v1/auth/refresh": () => apiError(401, "INVALID_REFRESH_TOKEN"),
    });
    const store = makeStore(signedInState("access-1"));

    await store.dispatch(authApi.endpoints.getMe.initiate());

    const { auth } = store.getState();
    expect(auth.status).toBe("anonymous");
    expect(auth.accessToken).toBeNull();
    expect(auth.notice).toMatch(/session has ended/);
  });

  it("stays signed in when the refresh can't reach the server", async () => {
    mockFetch({
      "GET /api/v1/me": protectedBy("never"),
      "POST /api/v1/auth/refresh": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    const store = makeStore(signedInState("access-1"));

    const result = await store.dispatch(authApi.endpoints.getMe.initiate());

    expect(result.error).toMatchObject({ status: 401 });
    expect(store.getState().auth.status).toBe("authenticated");
  });

  it("retries once when another tab just rotated the refresh token", async () => {
    let refreshes = 0;
    const api = mockFetch({
      "GET /api/v1/me": protectedBy("access-2", USER),
      "POST /api/v1/auth/refresh": () =>
        ++refreshes === 1 ? apiError(401, "REFRESH_TOKEN_ROTATED") : json(session("access-2")),
    });
    const store = makeStore(signedInState("access-1"));

    const result = await store.dispatch(authApi.endpoints.getMe.initiate());

    expect(result.data).toEqual(USER);
    expect(api.count("POST /api/v1/auth/refresh")).toBe(2);
  });

  it.each([403, 404, 500])("does not refresh on a %i", async (status) => {
    const api = mockFetch({ "GET /api/v1/me": () => apiError(status, "NOPE") });
    const store = makeStore(signedInState());

    await store.dispatch(authApi.endpoints.getMe.initiate());

    expect(api.count("POST /api/v1/auth/refresh")).toBe(0);
  });

  it("does not refresh when login itself says 401 (that's a wrong password)", async () => {
    const api = mockFetch({
      "POST /api/v1/auth/login": () => apiError(401, "INVALID_CREDENTIALS"),
    });
    const store = makeStore();

    await store.dispatch(authApi.endpoints.login.initiate({ email: "a@b.co", password: "x" }));

    expect(api.count("POST /api/v1/auth/refresh")).toBe(0);
  });

  it("shows a toast with the wait time on 429", async () => {
    mockFetch({
      "GET /api/v1/me": () =>
        apiError(429, "RATE_LIMITED", "Too many requests.", { retry_after: 42 }),
    });
    const store = makeStore(signedInState());

    await store.dispatch(authApi.endpoints.getMe.initiate());

    expect(store.getState().toasts.map((toast) => toast.message)).toEqual([
      "Too many requests. Try again in 42 s.",
    ]);
  });
});
