import { Link } from "react-router";
import { useAppSelector } from "@/app/hooks";
import { selectUser } from "@/lib/api/authSession";
import { MODULES } from "./modules";

export function DashboardPage() {
  const user = useAppSelector(selectUser);
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-1 text-sm text-text/70">Signed in as {user?.email}.</p>
      </header>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {MODULES.map(({ path, title, description, icon: Icon, phase }) => (
          <li key={path}>
            <Link to={path} className="card flex h-full flex-col gap-3 transition-colors hover:border-accent/60">
              <Icon aria-hidden className="size-6 text-accent" />
              <span className="font-semibold">{title}</span>
              <span className="text-sm text-text/70">{description}</span>
              <span className="mt-auto w-fit rounded-full bg-surface-2 px-2 py-0.5 text-xs text-text/60">
                Arrives in phase {phase}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
