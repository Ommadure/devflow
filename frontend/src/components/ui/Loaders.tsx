import { LoaderCircle } from "lucide-react";

function Spinner({ className = "size-6" }: { className?: string }) {
  return <LoaderCircle aria-hidden className={`${className} animate-spin text-accent`} />;
}

/** Inside a page area while a lazy page or its data loads. */
export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-3 p-12">
      <Spinner />
      <span className="text-sm text-text/70">{label}</span>
    </div>
  );
}

/** The whole screen, before we know whether anyone is signed in. */
export function FullPageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex min-h-screen items-center justify-center gap-3">
      <Spinner className="size-8" />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export { Spinner };
