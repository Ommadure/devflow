import { useCallback, useEffect, useRef, useState } from "react";

export type SaveStatus = "saved" | "pending" | "saving" | "error";

/**
 * Save `draft` `delayMs` after the last change, one request at a time.
 *
 * - Debounced: typing a sentence is one save, not forty.
 * - Serialised: while a save is in flight, newer edits wait for it, so an older request
 *   can never land after a newer one and overwrite it.
 * - Flushed on unmount (switching notes, leaving the page), so nothing typed is lost.
 */
export function useAutosave<T>(
  initial: T,
  save: (value: T) => Promise<unknown>,
  { delayMs = 1000, isEqual }: { delayMs?: number; isEqual: (a: T, b: T) => boolean },
) {
  const [status, setStatus] = useState<SaveStatus>("saved");
  const draft = useRef(initial);
  const saved = useRef(initial);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const inFlight = useRef<Promise<void> | null>(null);

  const flush = useCallback(async (): Promise<void> => {
    clearTimeout(timer.current);
    // One request at a time: wait for the save in flight, then save whatever is newest.
    // (An edit made meanwhile has scheduled its own flush, so nothing is left behind.)
    while (inFlight.current) await inFlight.current;
    const value = draft.current;
    if (isEqual(value, saved.current)) return;
    setStatus("saving");
    inFlight.current = (async () => {
      try {
        await save(value);
        saved.current = value;
        setStatus(isEqual(draft.current, value) ? "saved" : "pending");
      } catch {
        setStatus("error"); // the next edit (or "Retry") tries again; no retry loop
      } finally {
        inFlight.current = null;
      }
    })();
    await inFlight.current;
  }, [isEqual, save]);

  const change = useCallback(
    (value: T) => {
      draft.current = value;
      setStatus("pending");
      clearTimeout(timer.current);
      timer.current = setTimeout(() => void flush(), delayMs);
    },
    [delayMs, flush],
  );

  useEffect(() => () => void flush(), [flush]);

  return { status, change, flush };
}
