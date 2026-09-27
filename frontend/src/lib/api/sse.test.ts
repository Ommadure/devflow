import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { apiError, json, mockFetch, sse, sseResponse } from "@/test/fetchMock";
import { session, signedInState } from "@/test/utils";
import { SseParser, postSse, type SseEvent } from "./sse";

const encode = (text: string) => new TextEncoder().encode(text);

describe("SseParser", () => {
  it("parses whole events", () => {
    expect(new SseParser().push(encode(sse("token", { text: "hi" }) + sse("done", {})))).toEqual([
      { event: "token", data: { text: "hi" } },
      { event: "done", data: {} },
    ]);
  });

  it("reassembles an event split mid-line across chunks", () => {
    const parser = new SseParser();
    const whole = sse("token", { text: "hello world" });
    const pieces = [whole.slice(0, 7), whole.slice(7, 20), whole.slice(20)];
    expect(parser.push(encode(pieces[0]!))).toEqual([]);
    expect(parser.push(encode(pieces[1]!))).toEqual([]);
    expect(parser.push(encode(pieces[2]!))).toEqual([{ event: "token", data: { text: "hello world" } }]);
  });

  it("keeps a multi-byte character split between chunks intact", () => {
    const bytes = encode(sse("token", { text: "café ✓" }));
    const cut = bytes.indexOf(0xc3) + 1; // inside the two bytes of "é"
    const parser = new SseParser();
    const events = [...parser.push(bytes.slice(0, cut)), ...parser.push(bytes.slice(cut))];
    expect(events).toEqual([{ event: "token", data: { text: "café ✓" } }]);
  });

  it("accepts CRLF line endings and ignores comments", () => {
    const parser = new SseParser();
    expect(parser.push(encode(': keep-alive\r\n\r\nevent: done\r\ndata: {"ok":true}\r\n\r\n'))).toEqual([
      { event: "done", data: { ok: true } },
    ]);
  });
});

describe("postSse", () => {
  it("sends the token and delivers events in order", async () => {
    const api = mockFetch({
      "POST /api/v1/notes/ask": () => sseResponse([sse("sources", []), sse("token", { text: "a" }), sse("done", {})]),
    });
    const events: SseEvent[] = [];
    await postSse(makeStore(signedInState("t1")), "/notes/ask", { question: "q" }, {
      signal: new AbortController().signal,
      onEvent: (e) => events.push(e),
    });
    expect(events.map((e) => e.event)).toEqual(["sources", "token", "done"]);
    expect(api.calls[0]!.headers.get("Authorization")).toBe("Bearer t1");
  });

  it("refreshes once on 401 and retries", async () => {
    let attempts = 0;
    mockFetch({
      "POST /api/v1/notes/ask": () => (++attempts === 1 ? apiError(401, "TOKEN_EXPIRED") : sseResponse([sse("done", {})])),
      "POST /api/v1/auth/refresh": () => json(session("t2")),
    });
    const store = makeStore(signedInState("t1"));
    await postSse(store, "/notes/ask", {}, { signal: new AbortController().signal, onEvent: () => {} });
    expect(attempts).toBe(2);
    expect(store.getState().auth.accessToken).toBe("t2");
  });

  it("throws the API error, and toasts a 429", async () => {
    mockFetch({
      "POST /api/v1/notes/ask": () => apiError(429, "QUOTA_EXCEEDED", "You've used all 50 AI requests for today."),
    });
    const store = makeStore(signedInState());
    await expect(
      postSse(store, "/notes/ask", {}, { signal: new AbortController().signal, onEvent: () => {} }),
    ).rejects.toMatchObject({ code: "QUOTA_EXCEEDED", status: 429 });
    expect(store.getState().toasts[0]!.message).toMatch(/50 AI requests/);
  });
});
