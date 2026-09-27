import { vi } from "vitest";

type Handler = (request: Request) => Response | Promise<Response>;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function apiError(status: number, code: string, message = code, details = {}): Response {
  return json({ error: { code, message, details, request_id: "req-test" } }, status);
}

/**
 * Replace global fetch with routes like "POST /api/v1/auth/refresh". Each call is recorded
 * as a Request, so tests can assert on headers and order. Unmatched requests fail loudly.
 */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: Request[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(new URL(String(input), location.origin), init);
    calls.push(request.clone());
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const handler = routes[key];
    if (!handler) throw new Error(`Unexpected request in test: ${key}`);
    return handler(request);
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    calls,
    count: (key: string) =>
      calls.filter((call) => `${call.method} ${new URL(call.url).pathname}` === key).length,
  };
}
