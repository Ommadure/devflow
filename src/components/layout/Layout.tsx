import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { Github, Code2, StickyNote, Timer, Webhook, Activity, LogOut } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { supabase } from '../../lib/supabase';
import { useAppSelector } from '../../hooks/redux';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const user = useAppSelector(state => state.auth.user);

  const navItems = [
    { to: '/', icon: Activity, label: 'Dashboard' },
    { to: '/github', icon: Github, label: 'GitHub Analytics' },
    { to: '/snippets', icon: Code2, label: 'Snippets' },
    { to: '/notes', icon: StickyNote, label: 'Notes' },
    { to: '/timer', icon: Timer, label: 'Timer' },
    { to: '/api', icon: Webhook, label: 'API Tester' },
  ];

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <div className="flex h-screen bg-background text-text overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-surface border-r border-border flex flex-col">
        <div className="p-6">
          <h1 className="text-2xl font-bold text-accent tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6" />
            DevFlow
          </h1>
        </div>
        <nav className="flex-1 px-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                twMerge(
                  clsx(
                    'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 font-medium',
                    isActive
                      ? 'bg-accent/10 text-accent'
                      : 'text-gray-400 hover:text-text hover:bg-border/50'
                  )
                )
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border flex flex-col gap-4">
          <div className="text-xs text-gray-400 truncate px-2">
            {user?.email}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors px-2"
          >
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-6xl mx-auto h-full">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
