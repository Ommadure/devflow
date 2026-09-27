import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "react-redux";
import type { AppStore } from "@/app/store";
import { baseApi } from "./baseApi";
import type { ApiError } from "./errors";
import { postSse, type SseEvent } from "./sse";

export type StreamStatus = "idle" | "streaming" | "done" | "stopped" | "error";

export interface StreamState<S> {
  status: StreamStatus;
  text: string;
  sources: S[];
  error: { code: string; message: string } | null;
}

const initial = { status: "idle", text: "", sources: [], error: null } as const;

/**
 * Run a streamed AI request: `token` events append to `text`, `sources` arrive first,
 * `done`/`error` end it. `stop()` aborts the fetch, which closes the connection — the
 * server notices and stops the model (and its billing) too.
 */
export function useStream<S = unknown>() {
  const store = useStore() as AppStore;
  const [state, setState] = useState<StreamState<S>>({ ...initial, sources: [] });
  const controller = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
    setState((s) => (s.status === "streaming" ? { ...s, status: "stopped" } : s));
  }, []);

  const start = useCallback(
    async (path: string, body: unknown) => {
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;
      setState({ status: "streaming", text: "", sources: [], error: null });

      const onEvent = ({ event, data }: SseEvent) => {
        if (event === "token") {
          const piece = (data as { text: string }).text;
          setState((s) => ({ ...s, text: s.text + piece }));
        } else if (event === "sources") {
          setState((s) => ({ ...s, sources: data as S[] }));
        } else if (event === "done") {
          setState((s) => ({ ...s, status: "done" }));
        } else if (event === "error") {
          setState((s) => ({ ...s, status: "error", error: data as { code: string; message: string } }));
        }
      };

      try {
        await postSse(store, path, body, { signal: abort.signal, onEvent });
      } catch (caught) {
        if (abort.signal.aborted) return; // stopped on purpose
        const error = caught as ApiError;
        setState((s) => ({ ...s, status: "error", error: { code: error.code, message: error.message } }));
      } finally {
        // Every AI request changes today's count, success or not.
        store.dispatch(baseApi.util.invalidateTags(["AiUsage"]));
      }
    },
    [store],
  );

  // Leaving the page mid-answer stops the request.
  useEffect(() => () => controller.current?.abort(), []);

  return { ...state, start, stop };
}
