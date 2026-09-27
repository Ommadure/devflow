import { Check, Circle } from "lucide-react";
import { PASSWORD_RULES, STRENGTH_LABELS, passwordStrength } from "../lib/passwordRules";
import { cn } from "@/lib/utils/cn";

const SEGMENT_COLOURS = ["bg-danger", "bg-danger", "bg-warning", "bg-warning", "bg-success", "bg-success"];

/** Six-segment meter plus the live checklist of required rules. */
export function PasswordStrength({ password, id }: { password: string; id: string }) {
  const score = passwordStrength(password);
  return (
    <div id={id} className="space-y-2">
      <div className="flex gap-1" aria-hidden>
        {SEGMENT_COLOURS.map((colour, index) => (
          <span
            key={index}
            className={cn("h-1.5 flex-1 rounded-full", index < score ? colour : "bg-border")}
          />
        ))}
      </div>
      <p className="text-xs text-text/70">
        Strength: <span className="font-medium text-text">{STRENGTH_LABELS[score]}</span>
      </p>
      <ul className="grid grid-cols-2 gap-1 text-xs" aria-label="Password requirements">
        {PASSWORD_RULES.map((rule) => {
          const met = rule.test(password);
          return (
            <li key={rule.id} className={cn("flex items-center gap-1.5", met ? "text-success" : "text-text/60")}>
              {met ? <Check aria-hidden className="size-3.5" /> : <Circle aria-hidden className="size-3.5" />}
              {rule.label}
              <span className="sr-only">{met ? "(met)" : "(not met)"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
