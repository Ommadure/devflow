import { useState } from 'react';
import { Modal } from './Modal';
import { AlertCircle, Loader2 } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'info';
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger'
}: ConfirmDialogProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      await onConfirm();
      onClose();
    } catch (error) {
      console.error('Action failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <div className="flex flex-col items-center text-center gap-4">
        <div className={`p-4 rounded-full ${variant === 'danger' ? 'bg-red-500/10 text-red-500' : 'bg-accent/10 text-accent'}`}>
          <AlertCircle className="w-8 h-8" />
        </div>
        <p className="text-gray-300 text-lg leading-relaxed">
          {message}
        </p>
        <div className="flex gap-3 w-full mt-6">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="btn-secondary flex-1 py-3 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className={`flex-1 py-3 rounded-lg font-bold text-white transition-colors flex items-center justify-center gap-2 disabled:opacity-50 ${variant === 'danger' ? 'bg-red-500 hover:bg-red-600' : 'bg-accent hover:bg-blue-600'}`}
          >
            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
