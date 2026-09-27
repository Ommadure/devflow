import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { toastShown } from "@/lib/toasts";
import { useRecordSessionMutation } from "../api/pomodoroApi";
import { useNow } from "../hooks/useNow";
import { FOCUS_SECONDS, formatClock, phaseCompleted, remainingMs, selectTimer } from "../store/timerSlice";

/**
 * Mounted once, in the app layout — not in the Timer page — so a session still completes,
 * gets recorded and announced while you're reading notes on another page.
 */
export function TimerEngine() {
  const dispatch = useAppDispatch();
  const timer = useAppSelector(selectTimer);
  const running = timer.status === "running";
  const now = useNow(running);
  const left = remainingMs(timer, now);
  const [recordSession] = useRecordSessionMutation();

  useEffect(() => {
    if (!running || left > 0) return;
    const finished = timer.mode;
    dispatch(phaseCompleted()); // flips status, so this can't fire twice
    if (finished === "focus") {
      void recordSession({ duration_seconds: FOCUS_SECONDS });
      dispatch(toastShown({ tone: "success", message: "Focus session complete. Take a 5-minute break." }));
    } else {
      dispatch(toastShown({ tone: "info", message: "Break's over. Ready to focus?" }));
    }
  }, [running, left, timer.mode, dispatch, recordSession]);

  // The countdown in the tab title, so it's visible from other tabs.
  useEffect(() => {
    document.title = running ? `${formatClock(left)} · ${timer.mode === "focus" ? "Focus" : "Break"} — DevFlow` : "DevFlow";
  }, [running, left, timer.mode]);

  return null;
}
