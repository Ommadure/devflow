import type { AppDispatch } from "@/app/store";
import { toastShown } from "@/lib/toasts";
import { sessionStarted, signedOut, type AuthSessionState } from "./authSession";
import { toApiError, type ApiError } from "./errors";
import { refreshSession } from "./refresh";
import { API_BASE } from "./types";

export interface SseEvent {
  event: string;
  data: unknown;
}

/**
 * Incremental Server-Sent Events parser. Network chunks don't respect line boundaries —
 * an event can arrive split anywhere, even inside a multi-byte character — so text is
 * buffered until a blank line completes an event.
 */
export class SseParser {
  private buffer = "";
  private readonly decoder = new TextDecoder();

  push(bytes: Uint8Array): SseEvent[] {
    // stream: true keeps a half-received UTF-8 character for the next chunk.
    this.buffer += this.decoder.decode(bytes, { stream: true }).replace(/\r\n?/g, "\n");
    const events: SseEvent[] = [];
    let boundary: number;
    while ((boundary = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const event = parseBlock(block);
      if (event) events.push(event);
    }
    return events;
  }
}

function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // a comment / keep-alive
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  const raw = data.join("\n");
  try {
    return { event, data: JSON.parse(raw) as unknown };
  } catch {
    return { event, data: raw };
  }
}

interface Store {
  getState: () => { auth: AuthSessionState };
  dispatch: AppDispatch;
}

/**
 * POST and read the response as an event stream.
 *
 * Why not EventSource: it can only GET and can't send an Authorization header. This uses
 * fetch + ReadableStream instead, with the same rules as the base query: attach the access
 * token, refresh once on 401. Errors before the stream starts (404, 429 quota) arrive as
 * normal JSON error responses and are thrown as ApiError.
 */
export async function postSse(
  store: Store,
  path: string,
  body: unknown,
  { signal, onEvent }: { signal: AbortSignal; onEvent: (event: SseEvent) => void },
): Promise<void> {
  const send = () =>
    fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${store.getState().auth.accessToken ?? ""}`,
      },
      body: JSON.stringify(body),
    });

  let response = await send();
  if (response.status === 401) {
    const outcome = await refreshSession();
    if (outcome.kind === "ok") {
      store.dispatch(sessionStarted(outcome.session));
      response = await send();
    } else if (outcome.kind === "signed-out") {
      store.dispatch(signedOut({ notice: "Your session has ended. Please sign in again." }));
    }
  }
  if (!response.ok || !response.body) {
    const error = await errorFrom(response);
    if (error.status === 429) store.dispatch(toastShown({ tone: "error", message: error.message }));
    throw error;
  }

  const reader = response.body.getReader();
  const parser = new SseParser();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    for (const event of parser.push(value)) onEvent(event);
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // not JSON (a proxy's error page): toApiError still gives a readable message
  }
  return toApiError(
    data === null
      ? { status: "PARSING_ERROR", originalStatus: response.status, data: "", error: "not JSON" }
      : { status: response.status, data },
  );
}
