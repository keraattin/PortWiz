/** A small "?" affordance that reveals a one-line explanation on hover or
 * keyboard focus. Pure CSS (no library); works for jargon terms and column
 * headers. The trigger carries the text as its accessible name, and the bubble
 * is announced as a tooltip. */
export default function InfoDot({ text, className = "" }: { text: string; className?: string }) {
  return (
    <span className={`group relative inline-flex align-middle ${className}`}>
      <span
        tabIndex={0}
        role="img"
        aria-label={text}
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-slate-600 text-[10px] font-medium leading-none text-slate-400 hover:border-slate-400 hover:text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
      >
        ?
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-1 hidden w-56 -translate-x-1/2 whitespace-normal rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-normal normal-case leading-snug text-slate-200 shadow-lg group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}
