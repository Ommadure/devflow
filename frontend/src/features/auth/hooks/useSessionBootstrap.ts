import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { selectAuthStatus, sessionStarted, signedOut } from "@/lib/api/authSession";
import { refreshSession } from "@/lib/api/refresh";

/**
 * On startup, trade the refresh cookie (if any) for an access token. Until it answers, the
 * app shows a spinner instead of flashing the sign-in page at someone who is signed in.
 */
export function useSessionBootstrap(): void {
  const dispatch = useAppDispatch();
  const status = useAppSelector(selectAuthStatus);

  useEffect(() => {
    if (status !== "checking") return;
    let cancelled = false;
    // StrictMode runs this effect twice in development; refreshSession() is single-flight,
    // so both runs share one request.
    void refreshSession().then((outcome) => {
      if (cancelled) return;
      if (outcome.kind === "ok") dispatch(sessionStarted(outcome.session));
      else if (outcome.kind === "signed-out") dispatch(signedOut());
      else dispatch(signedOut({ notice: "Can't reach the server right now. Try signing in again." }));
    });
    return () => {
      cancelled = true;
    };
  }, [dispatch, status]);
}
