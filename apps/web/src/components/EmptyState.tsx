import { type ReactNode } from "react";

// A guiding empty-state card: an icon, a title, a short explanation and an
// optional action (a primary button, a "How to" link, ...). Used when a list
// has no data yet, to point a new user at the next step.
export default function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: string;
  title: string;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center">
      {icon && (
        <div className="mb-3 text-4xl" aria-hidden="true">
          {icon}
        </div>
      )}
      <p className="text-lg font-medium text-slate-200">{title}</p>
      {body && <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">{body}</p>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
