import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";
import { PageLoader } from "@/components/ui/Loaders";
import { MODULES } from "@/pages/modules";

// Every page is its own chunk: the first load doesn't pay for pages nobody opened.
const DashboardPage = lazy(() => import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const SnippetsPage = lazy(() => import("@/pages/SnippetsPage").then((m) => ({ default: m.SnippetsPage })));
const NotesPage = lazy(() => import("@/pages/NotesPage").then((m) => ({ default: m.NotesPage })));
const TimerPage = lazy(() => import("@/pages/TimerPage").then((m) => ({ default: m.TimerPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const ComingSoonPage = lazy(() =>
  import("@/pages/ComingSoonPage").then((m) => ({ default: m.ComingSoonPage })),
);

export function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/snippets" element={<SnippetsPage />} />
        <Route path="/notes" element={<NotesPage />} />
        <Route path="/timer" element={<TimerPage />} />
        {MODULES.filter((module) => module.phase > 3).map((module) => (
          <Route key={module.path} path={module.path} element={<ComingSoonPage module={module} />} />
        ))}
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
