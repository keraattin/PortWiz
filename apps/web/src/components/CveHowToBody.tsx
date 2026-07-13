import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// Visual three-step flow for importing an offline NVD feed.
const STEPS: { n: number; icon: string; title: TKey; body: TKey }[] = [
  { n: 1, icon: "⬇️", title: "cve.howto.s1", body: "cve.howto.s1d" },
  { n: 2, icon: "🔀", title: "cve.howto.s2", body: "cve.howto.s2d" },
  { n: 3, icon: "📥", title: "cve.howto.s3", body: "cve.howto.s3d" },
];

// A concrete way to produce feed files on a connected machine. Kept literal (it
// is a shell command, not translated prose).
const FEED_CMD = `base="https://services.nvd.nist.gov/rest/json/cves/2.0"
for start in $(seq 0 2000 20000); do
  curl -s "$base?resultsPerPage=2000&startIndex=$start" -o "nvd-$start.json"
  sleep 6   # no API key: stay under 5 requests / 30s
done`;

// Shared content for importing an offline NVD feed. Rendered both in the CVE
// settings "How to" modal and in the in-app Docs CVE guide.
export default function CveHowToBody() {
  const { t } = useI18n();
  return (
    <div className="space-y-5 text-sm text-slate-300">
      <p>{t("cve.howto.intro")}</p>

      <div className="grid items-stretch gap-3 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <div key={s.n} className="relative rounded-xl border border-slate-800 bg-slate-950 p-4">
            <div className="mb-2 flex items-center gap-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-900 text-xs font-semibold text-sky-200">
                {s.n}
              </span>
              <span className="text-lg" aria-hidden="true">
                {s.icon}
              </span>
              <span className="font-medium text-slate-100">{t(s.title)}</span>
            </div>
            <p className="text-xs leading-relaxed text-slate-400">{t(s.body)}</p>
            {i < STEPS.length - 1 && (
              <span
                aria-hidden="true"
                className="absolute -right-3 top-1/2 hidden -translate-y-1/2 text-slate-600 sm:block"
              >
                →
              </span>
            )}
          </div>
        ))}
      </div>

      <div>
        <p className="mb-1 text-xs text-slate-400">{t("cve.howto.codeCap")}</p>
        <pre className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300">
          <code>{FEED_CMD}</code>
        </pre>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs leading-relaxed text-slate-400">
        <p className="mb-1 font-medium text-slate-300">{t("cve.howto.matchTitle")}</p>
        {t("cve.howto.match")}
      </div>
    </div>
  );
}
