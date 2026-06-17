import type { Lang } from "../i18n/I18nContext";

// Small inline SVG flags. Emoji flags are not rendered on Windows (they fall
// back to letter pairs), and SVGs cannot live inside a native <select>, so we
// draw them here and use a custom dropdown. viewBox is 20x15 (4:3) for all.
const FLAGS: Record<Lang, React.ReactNode> = {
  en: (
    <>
      <rect width="20" height="15" fill="#012169" />
      <path d="M0 0 L20 15 M20 0 L0 15" stroke="#fff" strokeWidth="3" />
      <path d="M0 0 L20 15 M20 0 L0 15" stroke="#C8102E" strokeWidth="1.5" />
      <rect x="8" width="4" height="15" fill="#fff" />
      <rect y="5.5" width="20" height="4" fill="#fff" />
      <rect x="9" width="2" height="15" fill="#C8102E" />
      <rect y="6.5" width="20" height="2" fill="#C8102E" />
    </>
  ),
  tr: (
    <>
      <rect width="20" height="15" fill="#E30A17" />
      <circle cx="7.5" cy="7.5" r="3.4" fill="#fff" />
      <circle cx="8.6" cy="7.5" r="2.7" fill="#E30A17" />
      <polygon
        points="12.5,5.7 12.91,6.93 14.21,6.94 13.17,7.72 13.56,8.96 12.5,8.2 11.44,8.96 11.83,7.72 10.79,6.94 12.09,6.93"
        fill="#fff"
      />
    </>
  ),
  de: (
    <>
      <rect width="20" height="5" fill="#000" />
      <rect y="5" width="20" height="5" fill="#D00" />
      <rect y="10" width="20" height="5" fill="#FFCE00" />
    </>
  ),
  fr: (
    <>
      <rect width="20" height="15" fill="#fff" />
      <rect width="6.67" height="15" fill="#0055A4" />
      <rect x="13.33" width="6.67" height="15" fill="#EF4135" />
    </>
  ),
  pt: (
    <>
      <rect width="20" height="15" fill="#DA291C" />
      <rect width="8" height="15" fill="#046A38" />
      <circle cx="8" cy="7.5" r="2.6" fill="#FFE000" />
      <circle cx="8" cy="7.5" r="1.5" fill="#DA291C" />
    </>
  ),
  es: (
    <>
      <rect width="20" height="15" fill="#AA151B" />
      <rect y="3.75" width="20" height="7.5" fill="#F1BF00" />
    </>
  ),
};

export default function Flag({ code, className }: { code: Lang; className?: string }) {
  return (
    <svg
      viewBox="0 0 20 15"
      className={className ?? "h-3.5 w-5 shrink-0 rounded-[2px]"}
      role="presentation"
      aria-hidden="true"
    >
      {FLAGS[code]}
    </svg>
  );
}
