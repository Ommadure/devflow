import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutosave } from "./useAutosave";

const same = (a: string, b: string) => a === b;

/** A save whose completion the test controls. */
function controlledSave() {
  const calls: Array<{ value: string; resolve: () => void; reject: () => void }> = [];
  const save = vi.fn(
    (value: string) =>
      new Promise<void>((resolve, reject) => {
        calls.push({ value, resolve, reject });
      }),
  );
  return { save, calls };
}

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("useAutosave", () => {
  it("saves once, a second after typing stops", async () => {
    const { save, calls } = controlledSave();
    const { result } = renderHook(() => useAutosave<string>("", save, { isEqual: same }));

    act(() => {
      result.current.change("h");
      result.current.change("he");
      result.current.change("hello");
    });
    expect(result.current.status).toBe("pending");
    await act(() => vi.advanceTimersByTimeAsync(999));
    expect(save).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(calls.map((c) => c.value)).toEqual(["hello"]);
    expect(result.current.status).toBe("saving");

    await act(async () => calls[0]!.resolve());
    expect(result.current.status).toBe("saved");
  });

  it("never runs two saves at once, and ends with the newest text", async () => {
    const { save, calls } = controlledSave();
    const { result } = renderHook(() => useAutosave<string>("", save, { isEqual: same }));

    act(() => result.current.change("first"));
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(calls).toHaveLength(1);

    // Keep typing while "first" is still on its way.
    act(() => result.current.change("first, then more"));
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(calls).toHaveLength(1); // waits for the save in flight

    await act(async () => calls[0]!.resolve());
    expect(calls.map((c) => c.value)).toEqual(["first", "first, then more"]);
    await act(async () => calls[1]!.resolve());
    expect(result.current.status).toBe("saved");
  });

  it("saves what's pending when the editor closes", async () => {
    const { save, calls } = controlledSave();
    const { result, unmount } = renderHook(() => useAutosave<string>("", save, { isEqual: same }));

    act(() => result.current.change("typed just before switching notes"));
    unmount();
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(calls.map((c) => c.value)).toEqual(["typed just before switching notes"]);
  });

  it("reports a failed save and doesn't retry on its own", async () => {
    const { save, calls } = controlledSave();
    const { result } = renderHook(() => useAutosave<string>("", save, { isEqual: same }));

    act(() => result.current.change("x"));
    await act(() => vi.advanceTimersByTimeAsync(1000));
    await act(async () => calls[0]!.reject());
    expect(result.current.status).toBe("error");

    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(calls).toHaveLength(1);

    // "Retry" (flush) tries again.
    act(() => void result.current.flush());
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(calls).toHaveLength(2);
  });

  it("does nothing when the text is back to what was saved", async () => {
    const { save } = controlledSave();
    const { result } = renderHook(() => useAutosave<string>("same", save, { isEqual: same }));
    act(() => {
      result.current.change("changed");
      result.current.change("same");
    });
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(save).not.toHaveBeenCalled();
  });
});
