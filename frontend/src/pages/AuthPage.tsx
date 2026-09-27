import { useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useAppSelector } from "@/app/hooks";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Loaders";
import {
  ApiErrorMessage,
  PasswordField,
  PasswordStrength,
  meetsPasswordRules,
  useLoginMutation,
  useRegisterMutation,
} from "@/features/auth";
import { selectAuthNotice } from "@/lib/api/authSession";
import { toApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils/cn";

type Mode = "sign-in" | "register";
const TABS: Array<{ mode: Mode; label: string }> = [
  { mode: "sign-in", label: "Sign in" },
  { mode: "register", label: "Create account" },
];

export function AuthPage() {
  const [mode, setMode] = useState<Mode>("sign-in");
  const notice = useAppSelector(selectAuthNotice);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const baseId = useId();

  // WAI-ARIA tabs: arrow keys move between tabs; Tab moves into the panel.
  function onTabKeyDown(event: KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = (index + (event.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length;
    setMode(TABS[next]!.mode);
    tabRefs.current[next]?.focus();
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">DevFlow</h1>
          <p className="mt-1 text-sm text-text/70">Snippets, notes and focus — in one place.</p>
        </header>

        {notice && <Alert tone="info">{notice}</Alert>}

        <div className="card space-y-6">
          <div role="tablist" aria-label="Account" className="grid grid-cols-2 gap-1 rounded-lg bg-background p-1">
            {TABS.map((tab, index) => {
              const selected = tab.mode === mode;
              return (
                <button
                  key={tab.mode}
                  ref={(el) => {
                    tabRefs.current[index] = el;
                  }}
                  type="button"
                  role="tab"
                  id={`${baseId}-tab-${tab.mode}`}
                  aria-selected={selected}
                  aria-controls={`${baseId}-panel`}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setMode(tab.mode)}
                  onKeyDown={(event) => onTabKeyDown(event, index)}
                  className={cn(
                    "rounded-md py-2 text-sm font-medium transition-colors",
                    selected ? "bg-surface-2 text-text" : "text-text/60 hover:text-text",
                  )}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div role="tabpanel" id={`${baseId}-panel`} aria-labelledby={`${baseId}-tab-${mode}`}>
            {/* key: switching tabs starts a fresh form (no leftover password or error). */}
            <AuthForm key={mode} mode={mode} />
          </div>
        </div>
      </div>
    </main>
  );
}

function AuthForm({ mode }: { mode: Mode }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [login, loginState] = useLoginMutation();
  const [register, registerState] = useRegisterMutation();
  const state = mode === "sign-in" ? loginState : registerState;
  const emailId = useId();
  const strengthId = useId();

  const canSubmit =
    email.trim() !== "" && (mode === "sign-in" ? password !== "" : meetsPasswordRules(password));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || state.isLoading) return;
    // On success the auth slice flips to "authenticated" and the app shell replaces this page.
    const action = mode === "sign-in" ? login : register;
    await action({ email, password }).unwrap().catch(() => undefined);
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {state.error && <ApiErrorMessage error={toApiError(state.error)} />}
      <div>
        <label htmlFor={emailId} className="label">
          Email
        </label>
        <input
          id={emailId}
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="input-field"
        />
      </div>
      <PasswordField
        label="Password"
        autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
        required
        maxLength={128}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        describedBy={mode === "register" ? strengthId : undefined}
      />
      {mode === "register" && <PasswordStrength password={password} id={strengthId} />}
      <button type="submit" className="btn-primary w-full" disabled={!canSubmit || state.isLoading}>
        {state.isLoading && <Spinner className="size-4" />}
        {mode === "sign-in" ? "Sign in" : "Create account"}
      </button>
      {mode === "sign-in" && (
        <p className="text-center text-xs text-text/60">
          Forgot your password? DevFlow doesn&apos;t send email, so there&apos;s no reset link.
        </p>
      )}
    </form>
  );
}
