import { useState } from "react";
import { toApiError, type ApiError } from "@/lib/api/errors";
import { Alert } from "./Alert";
import { Spinner } from "./Loaders";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  /** Throw (or reject) to keep the dialog open and show the error. */
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
}

/** "Are you sure?" with its own loading and error state, for destructive actions. */
export function ConfirmDialog({ open, title, message, confirmLabel = "Delete", onConfirm, onClose }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  function close() {
    if (busy) return;
    setError(null);
    onClose();
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (caught) {
      setError(toApiError(caught as Parameters<typeof toApiError>[0]));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title={title} onClose={close}>
      <p className="text-sm text-text/80">{message}</p>
      {error && <Alert tone="error">{error.message}</Alert>}
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary" onClick={close} disabled={busy}>
          Cancel
        </button>
        <button
          type="button"
          className="btn bg-danger text-background hover:bg-danger/85"
          onClick={() => void confirm()}
          disabled={busy}
        >
          {busy && <Spinner className="size-4" />}
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
