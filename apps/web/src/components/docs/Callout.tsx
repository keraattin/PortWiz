import { type ReactNode } from "react";

type Variant = "tip" | "note" | "warning";

const STYLES: Record<Variant, { box: string; icon: string }> = {
  tip: { box: "border-emerald-800 bg-emerald-950/40 text-emerald-200", icon: "💡" },
  note: { box: "border-sky-800 bg-sky-950/40 text-sky-200", icon: "ℹ️" },
  warning: { box: "border-amber-800 bg-amber-950/40 text-amber-200", icon: "⚠️" },
};

// A coloured tip / note / warning box for the docs guides.
export default function Callout({
  variant = "note",
  children,
}: {
  variant?: Variant;
  children: ReactNode;
}) {
  const s = STYLES[variant];
  return (
    <div className={`flex gap-2 rounded-lg border px-3 py-2 text-xs leading-relaxed ${s.box}`}>
      <span aria-hidden="true">{s.icon}</span>
      <div>{children}</div>
    </div>
  );
}
