import { type ReactNode } from "react";

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

// The title block at the top of a page: a strong heading, an optional
// descriptive subtitle, and an optional right-aligned actions slot (an add
// button, a filter group, ...). Page titles are text-xl so they sit a clear
// notch above the text-lg section headers used inside cards, giving each
// screen an unambiguous primary heading.
export default function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className={`flex ${subtitle ? "items-start" : "items-center"} justify-between gap-3`}>
      <div className="min-w-0">
        <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
