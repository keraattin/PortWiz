import { type ChangeEvent, type ChangeType, type PortSnapshot } from "../api/client";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// Mirrors the change-type badge colours used on the Changes page.
const CHANGE_BADGE: Record<ChangeType, string> = {
  opened: "bg-sky-900 text-sky-300",
  closed: "bg-slate-700 text-slate-300",
  service_changed: "bg-amber-900 text-amber-300",
  version_changed: "bg-orange-900 text-orange-200",
};

const CHANGE_DOT: Record<ChangeType, string> = {
  opened: "bg-sky-400",
  closed: "bg-slate-500",
  service_changed: "bg-amber-400",
  version_changed: "bg-orange-400",
};

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

function describe(snapshot: PortSnapshot, t: Translate): string {
  if (snapshot.state !== "open") return t("changes.closed");
  const detail = [snapshot.service, snapshot.version].filter(Boolean).join(" ");
  return detail ? t("changes.openWith", { detail }) : t("changes.open");
}

/** A vertical timeline of confirmed change events, newest first. `context`
 * picks the per-event identifier: the port (on a host's page) or the host (on a
 * port's page). Events are expected already ordered by detected_at descending. */
export default function ChangeTimeline({
  events,
  context = "port",
}: {
  events: ChangeEvent[];
  context?: "port" | "host";
}) {
  const { t } = useI18n();

  if (events.length === 0) {
    return <p className="py-6 text-center text-sm text-slate-600">{t("timeline.empty")}</p>;
  }

  return (
    <ol className="relative space-y-4 border-l border-slate-800 pl-5">
      {events.map((e) => (
        <li key={e.id} className="relative">
          <span
            className={`absolute -left-[1.42rem] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-slate-950 ${CHANGE_DOT[e.change_type]}`}
          />
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-xs ${CHANGE_BADGE[e.change_type]}`}>
              {t(`changeType.${e.change_type}` as TKey)}
            </span>
            <span className="font-mono text-xs text-slate-300">
              {context === "host" ? e.ip : `${e.port}/${e.protocol}`}
            </span>
            <span className="text-xs text-slate-500">
              {new Date(e.detected_at).toLocaleString()}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            {describe(e.before, t)} <span className="text-slate-600">→</span>{" "}
            {describe(e.after, t)}
          </p>
        </li>
      ))}
    </ol>
  );
}
