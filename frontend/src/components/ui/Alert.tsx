import { CircleAlert, CircleCheck, Info } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils/cn";

const TONES = {
  error: { icon: CircleAlert, className: "border-danger/40 bg-danger/10 text-danger" },
  success: { icon: CircleCheck, className: "border-success/40 bg-success/10 text-success" },
  info: { icon: Info, className: "border-accent/40 bg-accent/10 text-text" },
} as const;

/**
 * An inline message. Errors use role="alert" so screen readers announce them immediately;
 * the others are polite status updates.
 */
export function Alert({ tone, children }: { tone: keyof typeof TONES; children: ReactNode }) {
  const { icon: Icon, className } = TONES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-sm", className)}
    >
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
}
