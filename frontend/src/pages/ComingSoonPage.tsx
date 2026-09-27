import { Construction } from "lucide-react";
import type { Module } from "./modules";

/** Placeholder for a module that a later phase builds; keeps navigation honest meanwhile. */
export function ComingSoonPage({ module }: { module: Module }) {
  const Icon = module.icon;
  return (
    <div className="mx-auto max-w-xl space-y-4 py-12 text-center">
      <Icon aria-hidden className="mx-auto size-10 text-accent" />
      <h1 className="text-2xl font-semibold">{module.title}</h1>
      <p className="text-text/70">{module.description}</p>
      <p className="inline-flex items-center gap-2 rounded-full bg-surface-2 px-3 py-1 text-sm text-text/70">
        <Construction aria-hidden className="size-4" /> Arrives in phase {module.phase}
      </p>
    </div>
  );
}
