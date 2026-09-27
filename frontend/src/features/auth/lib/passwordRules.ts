/** The same rules the backend enforces (spec §8.3), shown live while typing. */
export const PASSWORD_RULES = [
  { id: "length", label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { id: "upper", label: "An uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { id: "lower", label: "A lowercase letter", test: (p: string) => /[a-z]/.test(p) },
  { id: "number", label: "A number", test: (p: string) => /\d/.test(p) },
] as const;

export const PASSWORD_MAX_LENGTH = 128;

export function meetsPasswordRules(password: string): boolean {
  return password.length <= PASSWORD_MAX_LENGTH && PASSWORD_RULES.every((rule) => rule.test(password));
}

export const STRENGTH_LABELS = ["Too weak", "Very weak", "Weak", "Fair", "Good", "Strong", "Very strong"];

/**
 * 0–6: one point per required rule, plus one for a symbol and one for 12+ characters.
 * A hint for the user, not a security control — the rules above are the requirement.
 */
export function passwordStrength(password: string): number {
  if (!password) return 0;
  const extras = [/[^A-Za-z0-9]/.test(password), password.length >= 12];
  return [...PASSWORD_RULES.map((rule) => rule.test(password)), ...extras].filter(Boolean).length;
}
