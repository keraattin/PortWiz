import { useEffect, useState } from "react";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// A dependency-free, stepped welcome tour. It orients a first-time user to the
// five-step flow (inventory -> scan -> review changes -> prove compliance)
// without fragile element-anchored coach-marks, so it survives any layout.
const STEP_KEYS = ["welcome", "inventory", "scanning", "changes", "compliance", "start"] as const;

export default function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const total = STEP_KEYS.length;
  const key = STEP_KEYS[step];
  const isLast = step === total - 1;

  return (
    <div
      className="pw-fade-in fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("tour.title")}
    >
      <div className="pw-scale-in w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 shadow-xl">
        <div className="border-b border-slate-800 px-6 py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-emerald-500">
            {t("tour.title")}
          </p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">
            {t(`tour.${key}.title` as TKey)}
          </h2>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm leading-relaxed text-slate-300">{t(`tour.${key}.body` as TKey)}</p>
        </div>
        <div className="flex items-center justify-between border-t border-slate-800 px-6 py-4">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {STEP_KEYS.map((k, i) => (
              <span
                key={k}
                className={`h-1.5 rounded-full transition-all ${
                  i === step ? "w-4 bg-emerald-400" : "w-1.5 bg-slate-700"
                }`}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={() => setStep((s) => s - 1)}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
              >
                {t("tour.back")}
              </button>
            )}
            {!isLast ? (
              <>
                <button
                  onClick={onClose}
                  className="rounded-lg px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200"
                >
                  {t("tour.skip")}
                </button>
                <button
                  onClick={() => setStep((s) => s + 1)}
                  className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
                >
                  {t("tour.next")}
                </button>
              </>
            ) : (
              <button
                onClick={onClose}
                className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
              >
                {t("tour.finish")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
