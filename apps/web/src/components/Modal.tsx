import { type ReactNode, useEffect } from "react";
import { useI18n } from "../i18n/I18nContext";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  wide?: boolean;
}

export default function Modal({ open, onClose, title, children, wide }: ModalProps) {
  const { t } = useI18n();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="pw-fade-in fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:p-8"
      onClick={onClose}
      role="presentation"
    >
      <div
        className={`pw-scale-in w-full ${wide ? "max-w-4xl" : "max-w-lg"} rounded-2xl border border-slate-800 bg-slate-900 shadow-xl`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
          <h3 className="font-medium text-slate-100">{title}</h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
            aria-label={t("common.close")}
          >
            ✕
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}
