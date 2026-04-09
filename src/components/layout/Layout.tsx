import { ReactNode, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  Github,
  Code2,
  StickyNote,
  Timer,
  Webhook,
  Activity,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { supabase } from "../../lib/supabase";
import { useAppSelector } from "../../hooks/redux";

interface LayoutProps {
  children: ReactNode;
}

const navItems = [
  { to: "/", icon: Activity, label: "Dashboard" },
  { to: "/github", icon: Github, label: "GitHub Analytics" },
  { to: "/snippets", icon: Code2, label: "Snippets" },
  { to: "/notes", icon: StickyNote, label: "Notes" },
  { to: "/timer", icon: Timer, label: "Timer" },
  { to: "/api", icon: Webhook, label: "API Tester" },
];

export function Layout({ children }: LayoutProps) {
  const user = useAppSelector((state) => state.auth.user);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <div className="flex h-screen bg-background text-text overflow-hidden">
      {/* Skip to main content link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-accent text-white px-4 py-2 rounded z-50"
      >
        Skip to main content
      </a>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={twMerge(
          clsx(
            "w-64 bg-surface border-r border-border flex flex-col fixed md:relative z-50 md:z-auto h-full md:h-auto transform transition-transform duration-300 ease-in-out",
            sidebarOpen
              ? "translate-x-0"
              : "-translate-x-full md:translate-x-0",
          ),
        )}
        aria-label="Main navigation"
      >
        <div className="p-6">
          <h1 className="text-2xl font-bold text-accent tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6" aria-hidden="true" />
            DevFlow
          </h1>
        </div>
        <nav
          className="flex-1 px-4 space-y-2 overflow-y-auto"
          role="navigation"
          aria-label="Application navigation"
        >
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setSidebarOpen(false)} // Close on mobile after navigation
              className={({ isActive }) =>
                twMerge(
                  clsx(
                    "flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 font-medium",
                    isActive
                      ? "bg-accent/10 text-accent"
                      : "text-gray-400 hover:text-text hover:bg-border/50",
                  ),
                )
              }
              aria-current={
                item.to === window.location.pathname ? "page" : undefined
              }
            >
              <item.icon className="w-5 h-5" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border flex flex-col gap-4">
          <div
            className="text-xs text-gray-400 truncate px-2"
            aria-label={`Logged in as ${user?.email}`}
          >
            {user?.email}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors px-2"
            aria-label="Sign out of the application"
          >
            <LogOut className="w-4 h-4" aria-hidden="true" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main
        id="main-content"
        className="flex-1 flex flex-col overflow-hidden relative"
        role="main"
      >
        {/* Mobile Header */}
        <div className="md:hidden p-4 bg-surface border-b border-border flex items-center justify-between">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 text-gray-400 hover:text-text transition-colors"
            aria-label="Open navigation menu"
            aria-expanded={sidebarOpen}
          >
            <Menu className="w-6 h-6" aria-hidden="true" />
          </button>
          <h1 className="text-xl font-bold text-accent">DevFlow</h1>
          <div className="w-10" aria-hidden="true" />{" "}
          {/* Spacer for centering */}
        </div>
        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="max-w-6xl mx-auto h-full">{children}</div>
        </div>
      </main>
    </div>
  );
}
