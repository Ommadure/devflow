import { X } from "lucide-react";
import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { selectToasts, toastDismissed, type Toast } from "@/lib/toasts";
import { cn } from "@/lib/utils/cn";

const AUTO_DISMISS_MS = 6000;

function ToastItem({ toast }: { toast: Toast }) {
  const dispatch = useAppDispatch();
  useEffect(() => {
    const timer = setTimeout(() => dispatch(toastDismissed(toast.id)), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [dispatch, toast.id]);

  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-lg border bg-surface px-4 py-3 text-sm shadow-lg",
        toast.tone === "error" && "border-danger/50",
        toast.tone === "success" && "border-success/50",
        toast.tone === "info" && "border-border",
      )}
    >
      <p className="flex-1">{toast.message}</p>
      <button
        type="button"
        onClick={() => dispatch(toastDismissed(toast.id))}
        className="text-text/60 hover:text-text"
        aria-label="Dismiss notification"
      >
        <X aria-hidden className="size-4" />
      </button>
    </li>
  );
}

/** Always mounted, so the live region exists before a toast arrives and gets announced. */
export function Toaster() {
  const toasts = useAppSelector(selectToasts);
  return (
    <div aria-live="polite" role="status" className="fixed right-4 bottom-4 z-50 w-80 max-w-[calc(100vw-2rem)]">
      <ul className="flex flex-col gap-2">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} />
        ))}
      </ul>
    </div>
  );
}
