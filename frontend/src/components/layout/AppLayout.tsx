import { LayoutDashboard, LogOut, Menu, Settings, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router";
import { useAppSelector } from "@/app/hooks";
import { AiUsageBadge } from "@/features/ai/shell";
import { useLogoutMutation } from "@/features/auth";
import { TimerEngine } from "@/features/pomodoro";
import { selectUser } from "@/lib/api/authSession";
import { cn } from "@/lib/utils/cn";
import { MODULES } from "@/pages/modules";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  ...MODULES.map((module) => ({ to: module.path, label: module.navLabel, icon: module.icon })),
  { to: "/settings", label: "Settings", icon: Settings },
];

/**
 * Fixed sidebar on desktop; on mobile, a drawer over an overlay. The closed drawer is
 * `hidden` (display: none), not just moved off-screen, so keyboard focus can't wander into
 * links nobody can see.
 */
export function AppLayout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  // Remember the page the drawer was opened on: navigating anywhere else closes it, derived
  // during render instead of reset in an effect (no extra render, no flash of open drawer).
  const [openedOn, setOpenedOn] = useState<string | null>(null);
  const drawerOpen = openedOn === pathname;
  const setDrawerOpen = (open: boolean) => setOpenedOn(open ? pathname : null);
  const user = useAppSelector(selectUser);
  const [logout, { isLoading: signingOut }] = useLogoutMutation();

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpenedOn(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className="min-h-screen lg:flex">
      <TimerEngine />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to main content
      </a>

      <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3 lg:hidden">
        <span className="text-lg font-bold">DevFlow</span>
        <button
          type="button"
          className="btn-ghost px-2"
          onClick={() => setDrawerOpen(true)}
          aria-expanded={drawerOpen}
          aria-controls="app-nav"
          aria-label="Open navigation"
        >
          <Menu aria-hidden className="size-5" />
        </button>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setDrawerOpen(false)} aria-hidden />
      )}

      <aside
        id="app-nav"
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 flex-col border-r border-border bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen",
          drawerOpen ? "animate-slide-in flex" : "hidden",
        )}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <span className="text-xl font-bold tracking-tight">DevFlow</span>
          <button
            type="button"
            className="btn-ghost px-2 lg:hidden"
            onClick={() => setDrawerOpen(false)}
            aria-label="Close navigation"
          >
            <X aria-hidden className="size-5" />
          </button>
        </div>

        <nav aria-label="Main" className="flex-1 overflow-y-auto px-3">
          <ul className="space-y-1">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                {/* NavLink sets aria-current="page" on the active link by itself. */}
                <NavLink
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                      isActive ? "bg-accent/15 text-text" : "text-text/70 hover:bg-surface-2 hover:text-text",
                    )
                  }
                >
                  <Icon aria-hidden className="size-4" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="space-y-2 border-t border-border p-4">
          <AiUsageBadge />
          <p className="truncate text-xs text-text/60" title={user?.email}>
            {user?.email}
          </p>
          <button type="button" className="btn-secondary w-full" onClick={() => void logout()} disabled={signingOut}>
            <LogOut aria-hidden className="size-4" /> Sign out
          </button>
        </div>
      </aside>

      <main id="main" tabIndex={-1} className="flex-1 p-4 outline-none sm:p-6 lg:p-8">
        {children}
      </main>
    </div>
  );
}
