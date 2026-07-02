// Localized "2 minutes ago" style formatting. The Lang codes are valid BCP-47
// subtags, so the browser's Intl handles localization for every locale for free.

const DIVISIONS: { amount: number; unit: Intl.RelativeTimeFormatUnit }[] = [
  { amount: 60, unit: "second" },
  { amount: 60, unit: "minute" },
  { amount: 24, unit: "hour" },
  { amount: 7, unit: "day" },
  { amount: 4.34524, unit: "week" },
  { amount: 12, unit: "month" },
  { amount: Number.POSITIVE_INFINITY, unit: "year" },
];

/** Relative time such as "3 minutes ago" / "in 2 days"; returns "-" for null. */
export function timeAgo(iso: string | null, lang: string): string {
  if (!iso) return "-";
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  let duration = (new Date(iso).getTime() - Date.now()) / 1000; // seconds; past is negative
  for (const { amount, unit } of DIVISIONS) {
    if (Math.abs(duration) < amount) {
      return rtf.format(Math.round(duration), unit);
    }
    duration /= amount;
  }
  return "-";
}

/** Absolute timestamp for a tooltip/title alongside the relative label. */
export function absoluteTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "-";
}
