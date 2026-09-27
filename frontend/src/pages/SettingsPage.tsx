import { useId, useState, type FormEvent } from "react";
import { useAppSelector } from "@/app/hooks";
import { Alert } from "@/components/ui/Alert";
import { ApiConnectionCard } from "@/components/ui/ApiConnectionCard";
import { Spinner } from "@/components/ui/Loaders";
import {
  ApiErrorMessage,
  PasswordField,
  PasswordStrength,
  meetsPasswordRules,
  useChangePasswordMutation,
} from "@/features/auth";
import { selectUser } from "@/lib/api/authSession";
import { toApiError } from "@/lib/api/errors";

export function SettingsPage() {
  const user = useAppSelector(selectUser);
  const emailId = useId();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section aria-labelledby="account-title" className="card space-y-4">
        <h2 id="account-title" className="text-lg font-semibold">
          Account
        </h2>
        <div>
          <label htmlFor={emailId} className="label">
            Email
          </label>
          <input id={emailId} type="email" value={user?.email ?? ""} readOnly className="input-field" />
        </div>
      </section>

      <ChangePasswordCard />
      <ApiConnectionCard />
    </div>
  );
}

function ChangePasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [changePassword, { isLoading, error, isSuccess, reset }] = useChangePasswordMutation();
  const strengthId = useId();

  const mismatch = confirm !== "" && confirm !== next;
  const canSubmit = current !== "" && meetsPasswordRules(next) && confirm === next;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || isLoading) return;
    const result = await changePassword({ current_password: current, new_password: next })
      .unwrap()
      .catch(() => null);
    if (result) {
      setCurrent("");
      setNext("");
      setConfirm("");
    }
  }

  return (
    <section aria-labelledby="password-title" className="card">
      <form onSubmit={onSubmit} noValidate className="space-y-4" onChange={() => isSuccess && reset()}>
        <h2 id="password-title" className="text-lg font-semibold">
          Change password
        </h2>
        {isSuccess && (
          <Alert tone="success">Password changed. You&apos;ve been signed out on every other device.</Alert>
        )}
        {error && <ApiErrorMessage error={toApiError(error)} />}
        <PasswordField
          label="Current password"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
        />
        <PasswordField
          label="New password"
          autoComplete="new-password"
          maxLength={128}
          value={next}
          onChange={(event) => setNext(event.target.value)}
          describedBy={strengthId}
        />
        <PasswordStrength password={next} id={strengthId} />
        <PasswordField
          label="Confirm new password"
          autoComplete="new-password"
          maxLength={128}
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          aria-invalid={mismatch}
        />
        {mismatch && <p className="text-xs text-danger">The new passwords don&apos;t match.</p>}
        <button type="submit" className="btn-primary" disabled={!canSubmit || isLoading}>
          {isLoading && <Spinner className="size-4" />}
          Change password
        </button>
      </form>
    </section>
  );
}
