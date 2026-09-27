import { useSyncExternalStore } from "react";

/**
 * The current time, re-rendering every 250 ms while `enabled`.
 *
 * A tiny external store (useSyncExternalStore) rather than useState + useEffect: the clock
 * is refreshed the moment a component subscribes, so a timer that starts after sitting
 * idle never renders with a stale "now".
 */
let now = Date.now();
const listeners = new Set<() => void>();
let interval: ReturnType<typeof setInterval> | undefined;

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  now = Date.now();
  interval ??= setInterval(() => {
    now = Date.now();
    listeners.forEach((notify) => notify());
  }, 250);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      clearInterval(interval);
      interval = undefined;
    }
  };
}

const idle = () => () => {};

export function useNow(enabled: boolean): number {
  return useSyncExternalStore(enabled ? subscribe : idle, () => now);
}
