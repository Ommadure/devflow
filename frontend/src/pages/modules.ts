import { ChartColumn, Code, NotebookPen, Send, Timer, type LucideIcon } from "lucide-react";

/** The tools DevFlow offers, shared by the navigation, the dashboard and placeholders. */
export interface Module {
  path: string;
  title: string;
  navLabel: string;
  description: string;
  icon: LucideIcon;
  phase: number; // the build phase that delivers it (spec §15)
}

export const MODULES: Module[] = [
  {
    path: "/snippets",
    title: "Snippet Manager",
    navLabel: "Snippets",
    description: "Save, tag and search the code you reach for again and again.",
    icon: Code,
    phase: 3,
  },
  {
    path: "/notes",
    title: "Markdown Notes",
    navLabel: "Notes",
    description: "Notes with live preview and auto-save — and, later, answers from them.",
    icon: NotebookPen,
    phase: 3,
  },
  {
    path: "/timer",
    title: "Focus Timer",
    navLabel: "Timer",
    description: "25-minute focus sessions with breaks, tracked over time.",
    icon: Timer,
    phase: 3,
  },
  {
    path: "/github",
    title: "GitHub Analytics",
    navLabel: "GitHub Analytics",
    description: "A developer's profile, recent repositories and weekly insights.",
    icon: ChartColumn,
    phase: 6,
  },
  {
    path: "/api",
    title: "HTTP API Tester",
    navLabel: "API Tester",
    description: "Send requests to any public API and inspect the response.",
    icon: Send,
    phase: 6,
  },
];
