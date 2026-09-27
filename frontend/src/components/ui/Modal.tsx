import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  size?: "md" | "lg";
}

/**
 * Built on the native <dialog> element: `showModal()` gives focus trapping, Escape to
 * close, an inert background and the top layer for free — the things hand-rolled modals
 * most often get wrong. The title labels the dialog for screen readers.
 */
export function Modal({ open, title, onClose, children, size = "md" }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      // Escape fires "cancel"; let the parent decide (it owns `open`).
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      // A click on the backdrop lands on the <dialog> itself, not its content.
      onClick={(event) => event.target === ref.current && onClose()}
      className={`m-auto w-[calc(100%-2rem)] rounded-xl border border-border bg-surface p-0 text-text backdrop:bg-black/60 ${
        size === "lg" ? "max-w-3xl" : "max-w-md"
      }`}
    >
      {open && (
        <div className="space-y-4 p-6">
          <div className="flex items-start justify-between gap-4">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            <button type="button" onClick={onClose} className="btn-ghost -m-2 p-2" aria-label="Close">
              <X aria-hidden className="size-4" />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}
