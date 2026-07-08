import { type ReactElement, type ReactNode, cloneElement, isValidElement, useId } from "react";

/** A labeled form control with optional helper text, for guided add/edit modals.
 *
 * The label (and hint) are wired to the control via a generated id, so clicking
 * the label focuses the field and screen readers announce both. Only a single
 * element that hasn't set its own id is enhanced; anything else renders as-is. */
export default function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const control =
    isValidElement(children) && (children.props as { id?: string }).id === undefined
      ? cloneElement(children as ReactElement<{ id?: string; "aria-describedby"?: string }>, {
          id,
          ...(hintId ? { "aria-describedby": hintId } : {}),
        })
      : children;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-300">
        {label}
      </label>
      {control}
      {hint && (
        <p id={hintId} className="text-xs text-slate-500">
          {hint}
        </p>
      )}
    </div>
  );
}
