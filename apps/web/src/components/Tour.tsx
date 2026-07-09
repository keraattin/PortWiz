import { type CSSProperties, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// An interactive, dependency-free spotlight tour. Each step optionally points at
// a real element (found by a `data-tour` attribute), dims the rest of the screen
// and anchors a callout beside it; steps may first navigate to the page that
// holds the element. Steps with no target render a centered card. Robust to
// missing targets (falls back to centered) and to resize/scroll.
interface Step {
  key: string; // i18n suffix: tour.{key}.title / tour.{key}.body
  target?: string; // CSS selector to spotlight
  route?: string; // navigate here before locating the target
  placement?: "right" | "bottom";
}

const STEPS: Step[] = [
  { key: "welcome" },
  { key: "inventory", target: '[data-tour="nav-inventory"]', placement: "right" },
  { key: "addAsset", route: "/assets", target: '[data-tour="add-asset"]', placement: "bottom" },
  { key: "scanning", target: '[data-tour="nav-scanning"]', placement: "right" },
  { key: "changes", target: '[data-tour="nav-changes"]', placement: "right" },
  { key: "compliance", target: '[data-tour="nav-compliance"]', placement: "right" },
  { key: "help", target: '[data-tour="help"]', placement: "bottom" },
  { key: "start", route: "/" },
];

const CALLOUT_W = 320; // matches w-80
const CALLOUT_H = 210; // estimate, for vertical clamping only

export default function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  // Navigate to the step's page (if any), then locate its target, retrying while
  // the route/element mounts. No target -> centered card.
  useEffect(() => {
    if (!open) return;
    const s = STEPS[step];
    if (s.route) navigate(s.route);
    if (!s.target) {
      setRect(null);
      return;
    }
    let tries = 0;
    let raf = 0;
    const find = () => {
      const el = document.querySelector(s.target as string);
      if (el) {
        el.scrollIntoView({ block: "nearest", inline: "nearest" });
        setRect(el.getBoundingClientRect());
      } else if (tries++ < 40) {
        raf = requestAnimationFrame(find);
      } else {
        setRect(null); // give up gracefully
      }
    };
    find();
    return () => cancelAnimationFrame(raf);
  }, [open, step, navigate]);

  // Keep the spotlight aligned on resize/scroll, and allow Escape to exit.
  useEffect(() => {
    if (!open) return;
    const s = STEPS[step];
    const update = () => {
      if (!s.target) return;
      const el = document.querySelector(s.target);
      if (el) setRect(el.getBoundingClientRect());
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, step, onClose]);

  if (!open) return null;

  const s = STEPS[step];
  const total = STEPS.length;
  const isLast = step === total - 1;

  let calloutStyle: CSSProperties;
  if (!rect) {
    calloutStyle = { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
  } else if (s.placement === "bottom") {
    const left = Math.min(Math.max(rect.left, 8), window.innerWidth - CALLOUT_W - 8);
    calloutStyle = { top: rect.bottom + 12, left };
  } else {
    const left = Math.min(rect.right + 12, window.innerWidth - CALLOUT_W - 8);
    const top = Math.min(Math.max(rect.top, 8), window.innerHeight - CALLOUT_H - 8);
    calloutStyle = { top, left };
  }

  return (
    <div className="fixed inset-0 z-[70]">
      {/* Click-blocker so the app behind the tour isn't triggered by accident. */}
      <div className={`fixed inset-0 ${rect ? "" : "bg-black/60"}`} />
      {rect && (
        <div
          className="pointer-events-none fixed z-[71] rounded-lg border-2 border-emerald-400 transition-all"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
            boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.6)",
          }}
        />
      )}
      <div
        className="pw-scale-in fixed z-[72] w-80 max-w-[calc(100vw-1rem)] rounded-2xl border border-slate-800 bg-slate-900 shadow-xl"
        style={calloutStyle}
        role="dialog"
        aria-modal="true"
        aria-label={t("tour.title")}
      >
        <div className="border-b border-slate-800 px-5 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-emerald-500">
            {t("tour.title")}
          </p>
          <h2 className="mt-1 text-base font-semibold text-slate-100">
            {t(`tour.${s.key}.title` as TKey)}
          </h2>
        </div>
        <div className="px-5 py-4">
          <p className="text-sm leading-relaxed text-slate-300">
            {t(`tour.${s.key}.body` as TKey)}
          </p>
        </div>
        <div className="flex items-center justify-between border-t border-slate-800 px-5 py-3">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {STEPS.map((st, i) => (
              <span
                key={st.key}
                className={`h-1.5 rounded-full transition-all ${
                  i === step ? "w-4 bg-emerald-400" : "w-1.5 bg-slate-700"
                }`}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={() => setStep((n) => n - 1)}
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
                  onClick={() => setStep((n) => n + 1)}
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
