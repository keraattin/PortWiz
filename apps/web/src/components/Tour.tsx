import { type CSSProperties, useEffect, useLayoutEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// An interactive, dependency-free spotlight tour. Each step optionally points at
// a real element (found by a `data-tour` attribute), dims the rest of the screen
// and anchors a callout beside it; steps may first navigate to the page that
// holds the element. Steps with no target render a centered card. Robust to
// missing targets (falls back to centered), tall targets and edges (the callout
// is measured and clamped so its buttons are always on screen), and resize.
interface Step {
  key: string; // i18n suffix: tour.{key}.title / tour.{key}.body
  target?: string; // CSS selector to spotlight
  route?: string; // navigate here before locating the target
  placement?: "right" | "bottom";
}

const STEPS: Step[] = [
  { key: "welcome" },
  { key: "dashboard", route: "/", target: '[data-tour="getting-started"]', placement: "bottom" },
  { key: "inventory", target: '[data-tour="nav-inventory"]', placement: "right" },
  { key: "addAsset", route: "/assets", target: '[data-tour="add-asset"]', placement: "bottom" },
  { key: "addVlan", route: "/vlans", target: '[data-tour="add-vlan"]', placement: "bottom" },
  { key: "scanning", target: '[data-tour="nav-scanning"]', placement: "right" },
  { key: "enrollAgent", route: "/agents", target: '[data-tour="enroll-agent"]', placement: "bottom" },
  { key: "newScan", route: "/scans", target: '[data-tour="new-scan"]', placement: "bottom" },
  { key: "changes", target: '[data-tour="nav-changes"]', placement: "right" },
  { key: "changesReview", route: "/changes", target: '[data-tour="changes-info"]', placement: "bottom" },
  { key: "compliance", target: '[data-tour="nav-compliance"]', placement: "right" },
  { key: "evidence", route: "/compliance", target: '[data-tour="evidence"]', placement: "right" },
  { key: "settings", route: "/settings", target: '[data-tour="settings-tabs"]', placement: "bottom" },
  { key: "language", target: '[data-tour="language"]', placement: "bottom" },
  { key: "help", target: '[data-tour="help"]', placement: "bottom" },
  { key: "start", route: "/" },
];

const CALLOUT_W = 416; // matches w-[26rem]
const GAP = 12;
const EDGE = 8;

const CENTERED: CSSProperties = { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };

export default function Tour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [pos, setPos] = useState<CSSProperties>(CENTERED);

  useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  // Navigate to the step's page (if any), then locate its target, retrying while
  // the route/element mounts. No target -> centered card.
  useEffect(() => {
    if (!open) return;
    const s = STEPS[step];
    // Center immediately on step change so the callout never lingers over the
    // previous target while the new one is located. Unlock scrolling so the
    // target can be scrolled into view.
    setRect(null);
    document.documentElement.style.overflow = "";
    if (s.route) navigate(s.route);
    if (!s.target) {
      return;
    }
    let tries = 0;
    let raf = 0;
    const find = () => {
      const el = document.querySelector(s.target as string);
      if (el) {
        el.scrollIntoView({ block: "nearest", inline: "nearest" });
        // Lock the page so the spotlight can't drift behind a manual scroll,
        // then measure (post-lock, so a vanished scrollbar is already accounted
        // for).
        document.documentElement.style.overflow = "hidden";
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

  // Always restore scrolling when the tour is not shown.
  useEffect(() => {
    if (!open) document.documentElement.style.overflow = "";
    return () => {
      document.documentElement.style.overflow = "";
    };
  }, [open]);

  // Anchor the callout next to the target (beside sidebar items; on whichever of
  // above/below has more room for other targets) so it clearly points at the
  // element. Anchoring to a CSS edge (`top`/`bottom`) plus a `maxHeight` capped
  // to the available space means it never depends on the callout's own height
  // and can never overflow the viewport, while staying attached to the target.
  useLayoutEffect(() => {
    if (!open) return;
    const s = STEPS[step];
    if (!rect) {
      setPos(CENTERED);
      return;
    }
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Sidebar (and similar) items: sit just to the right, aligned to the top.
    if (s.placement === "right" && rect.right + GAP + CALLOUT_W <= vw - EDGE) {
      const top = Math.max(EDGE, Math.min(rect.top, vh - 240 - EDGE));
      setPos({ left: rect.right + GAP, top, maxHeight: vh - top - EDGE });
      return;
    }

    // Otherwise centre the callout horizontally under/over the target (clamped),
    // and place it below or above only when that side has comfortable room. When
    // neither side does, centre it vertically with a full-height cap. In every
    // case `maxHeight` matches the room available, so with the fixed header/footer
    // and scrolling body the buttons are always visible, even for long text.
    const roomBelow = vh - rect.bottom - GAP - EDGE;
    const roomAbove = rect.top - GAP - EDGE;
    const left = Math.max(
      EDGE,
      Math.min(rect.left + rect.width / 2 - CALLOUT_W / 2, vw - CALLOUT_W - EDGE),
    );
    const MIN_ROOM = 220;
    if (roomBelow >= MIN_ROOM && roomBelow >= roomAbove) {
      setPos({ left, top: rect.bottom + GAP, maxHeight: roomBelow });
    } else if (roomAbove >= MIN_ROOM) {
      setPos({ left, bottom: vh - rect.top + GAP, maxHeight: roomAbove });
    } else {
      setPos({ left, top: "50%", transform: "translateY(-50%)", maxHeight: vh - 2 * EDGE });
    }
  }, [open, step, rect]);

  // Keep aligned on resize/scroll; Escape exits.
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

  return (
    <div className="fixed inset-0 z-[70]">
      {/* Click-blocker so the app behind the tour isn't triggered by accident. */}
      <div className={`fixed inset-0 ${rect ? "" : "bg-black/60"}`} />
      {rect && (
        <div
          className="pointer-events-none fixed z-[71] rounded-lg border-2 border-emerald-400"
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
        className="pw-scale-in fixed z-[72] flex max-h-[calc(100vh-2rem)] w-[26rem] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-xl"
        style={pos}
        role="dialog"
        aria-modal="true"
        aria-label={t("tour.title")}
      >
        <div className="shrink-0 border-b border-slate-800 px-5 py-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-500">
              {t("tour.title")}
            </p>
            <span className="text-xs font-medium text-slate-500">
              {step + 1} / {total}
            </span>
          </div>
          <h2 className="mt-1 text-base font-semibold text-slate-100">
            {t(`tour.${s.key}.title` as TKey)}
          </h2>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <p className="text-sm leading-relaxed text-slate-300">
            {t(`tour.${s.key}.body` as TKey)}
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-3 border-t border-slate-800 px-5 py-3">
          {/* Progress dots on their own row so they never crowd the buttons. */}
          <div className="flex flex-wrap items-center justify-center gap-1.5" aria-hidden="true">
            {STEPS.map((st, i) => (
              <span
                key={st.key}
                className={`h-1.5 rounded-full ${
                  i === step ? "w-4 bg-emerald-400" : "w-1.5 bg-slate-700"
                }`}
              />
            ))}
          </div>
          {/* Buttons get a full row: Back on the left, Skip/Next on the right. */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex">
              {step > 0 && (
                <button
                  onClick={() => setStep((n) => n - 1)}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                >
                  {t("tour.back")}
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
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
    </div>
  );
}
