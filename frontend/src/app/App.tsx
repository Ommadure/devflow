import { AppLayout } from "@/components/layout/AppLayout";
import { FullPageLoader } from "@/components/ui/Loaders";
import { Toaster } from "@/components/ui/Toaster";
import { useSessionBootstrap } from "@/features/auth";
import { selectAuthStatus } from "@/lib/api/authSession";
import { AuthPage } from "@/pages/AuthPage";
import { useAppSelector } from "./hooks";
import { AppRoutes } from "./routes";

/**
 * The auth gate. Signed out, only the sign-in page exists — no route is mounted, so no
 * page can fire a request without a session. Signed in, the layout wraps the routes.
 */
export function App() {
  useSessionBootstrap();
  const status = useAppSelector(selectAuthStatus);

  return (
    <>
      {status === "checking" ? (
        <FullPageLoader label="Loading DevFlow…" />
      ) : status === "anonymous" ? (
        <AuthPage />
      ) : (
        <AppLayout>
          <AppRoutes />
        </AppLayout>
      )}
      <Toaster />
    </>
  );
}
