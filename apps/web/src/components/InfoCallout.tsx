import { type ReactNode } from "react";

// A calm, theme-safe info note: an info icon beside explanatory text. Used to
// orient non-technical users (e.g. what an Asset is versus a VLAN). Built on
// slate surfaces, which are mapped in both themes, with a sky accent icon, so
// it reads as a hint without the risky tinted-background tokens.
export default function InfoCallout({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-3 rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-300">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-0.5 h-5 w-5 shrink-0 text-sky-400"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </svg>
      <div>{children}</div>
    </div>
  );
}
