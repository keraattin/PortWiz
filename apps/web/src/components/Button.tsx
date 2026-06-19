import { type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "outline" | "danger" | "ghost";
type Size = "md" | "sm";

const BASE =
  "inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-emerald-600 text-white hover:bg-emerald-500",
  outline: "border border-slate-700 text-slate-200 hover:bg-slate-800",
  danger: "bg-red-600 text-white hover:bg-red-500",
  ghost: "text-slate-300 hover:bg-slate-800",
};

const SIZES: Record<Size, string> = {
  md: "px-4 py-2 text-sm",
  sm: "px-3 py-1.5 text-sm",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

// One button surface so every primary/secondary action looks and behaves the
// same: consistent padding, weight, disabled affordance, and the app focus
// ring (from index.css). Defaults to type="button" so a button inside a form
// never submits by accident; pass type="submit" explicitly where wanted.
// className is appended, so callers can still add layout tweaks (e.g. w-full).
export default function Button({
  variant = "primary",
  size = "md",
  type = "button",
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
