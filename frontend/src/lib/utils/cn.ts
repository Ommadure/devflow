/**
 * Join class names, skipping falsy ones: cn("btn", isActive && "btn-active").
 * (No clsx / tailwind-merge dependency: we never pass conflicting Tailwind classes.)
 */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
