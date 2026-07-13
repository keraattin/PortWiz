import { Fragment, type ReactNode } from "react";
import CveHowToBody from "../components/CveHowToBody";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// A Docs guide: shown in the sidebar list and rendered as a page body. Add a new
// guide by appending to GUIDES and adding its i18n keys; the page and nav pick
// it up automatically.
export interface Guide {
  id: string;
  titleKey: TKey;
  summaryKey: TKey;
  icon: string;
  Body: () => ReactNode;
}

function Section({ heading, children }: { heading: TKey; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <section className="space-y-2">
      <h3 className="text-base font-semibold text-slate-100">{t(heading)}</h3>
      <div className="space-y-2 text-sm leading-relaxed text-slate-300">{children}</div>
    </section>
  );
}

function P({ k }: { k: TKey }) {
  const { t } = useI18n();
  return <p>{t(k)}</p>;
}

function Steps({ items }: { items: TKey[] }) {
  const { t } = useI18n();
  return (
    <ol className="ml-5 list-decimal space-y-1 marker:text-slate-500">
      {items.map((k) => (
        <li key={k}>{t(k)}</li>
      ))}
    </ol>
  );
}

// A responsive arrow: points right on wide screens, down when the flow stacks.
function Arrow() {
  return (
    <span className="self-center text-slate-600" aria-hidden="true">
      <span className="sm:hidden">↓</span>
      <span className="hidden sm:inline">→</span>
    </span>
  );
}

// Left-to-right flow of labelled steps (stacks vertically on small screens).
function DocFlow({ steps }: { steps: { icon: string; label: TKey }[] }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      {steps.map((s, i) => (
        <Fragment key={s.label}>
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2.5">
            <span className="text-lg" aria-hidden="true">
              {s.icon}
            </span>
            <span className="text-xs font-medium text-slate-200">{t(s.label)}</span>
          </div>
          {i < steps.length - 1 && <Arrow />}
        </Fragment>
      ))}
    </div>
  );
}

// A row of coloured status badges, so a guide can show what the states look like.
function DocLegend({ items }: { items: { cls: string; label: TKey }[] }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((it) => (
        <span key={it.label} className={`rounded-full px-2 py-0.5 text-xs ${it.cls}`}>
          {t(it.label)}
        </span>
      ))}
    </div>
  );
}

// Neutral chips, e.g. the plain-language schedule presets.
function DocChips({ items }: { items: TKey[] }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((k) => (
        <span
          key={k}
          className="rounded-md border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-300"
        >
          {t(k)}
        </span>
      ))}
    </div>
  );
}

// Simple control-plane / per-segment-agents architecture sketch.
function DocArch() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 p-4 sm:flex-row sm:justify-center">
      <div className="rounded-lg border border-sky-800 bg-sky-950/40 px-4 py-3 text-sm font-medium text-sky-200">
        🛡️ {t("docs.arch.control")}
      </div>
      <Arrow />
      <div className="grid gap-2">
        {["DMZ", "Servers", "OT"].map((seg) => (
          <div
            key={seg}
            className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-300"
          >
            🛰️ {t("docs.arch.agent")} · {seg}
          </div>
        ))}
      </div>
    </div>
  );
}

// Badge classes reused from the Agents and Compliance pages so the docs match.
const AGENT_STATUS_LEGEND: { cls: string; label: TKey }[] = [
  { cls: "bg-emerald-900 text-emerald-300", label: "agents.status.online" },
  { cls: "bg-red-900 text-red-300", label: "agents.status.offline" },
  { cls: "bg-slate-700 text-slate-400", label: "agents.status.neverSeen" },
  { cls: "bg-slate-700 text-slate-400", label: "agents.status.disabled" },
];

const CADENCE_LEGEND: { cls: string; label: TKey }[] = [
  { cls: "bg-emerald-900 text-emerald-300", label: "cadence.compliant" },
  { cls: "bg-amber-900 text-amber-300", label: "cadence.due_soon" },
  { cls: "bg-red-900 text-red-300", label: "cadence.overdue" },
  { cls: "bg-slate-700 text-slate-400", label: "cadence.never" },
];

function GettingStartedGuide() {
  return (
    <div className="space-y-6">
      <DocFlow
        steps={[
          { icon: "🗂️", label: "docs.flow.inventory" },
          { icon: "🔎", label: "docs.flow.scan" },
          { icon: "🔀", label: "docs.flow.detect" },
          { icon: "📦", label: "docs.flow.evidence" },
        ]}
      />
      <Section heading="docs.gs.what.h">
        <P k="docs.gs.what.p" />
      </Section>
      <Section heading="docs.gs.steps.h">
        <Steps
          items={["docs.gs.steps.1", "docs.gs.steps.2", "docs.gs.steps.3", "docs.gs.steps.4"]}
        />
      </Section>
      <Section heading="docs.gs.roles.h">
        <P k="docs.gs.roles.p" />
      </Section>
      <Section heading="docs.gs.tip.h">
        <P k="docs.gs.tip.p" />
      </Section>
    </div>
  );
}

function CveGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.cve.overview.h">
        <P k="docs.cve.overview.p" />
      </Section>
      <Section heading="docs.cve.online.h">
        <P k="docs.cve.online.p" />
      </Section>
      <Section heading="docs.cve.offline.h">
        <CveHowToBody />
      </Section>
      <Section heading="docs.cve.checks.h">
        <P k="docs.cve.checks.p" />
      </Section>
    </div>
  );
}

function ScanningGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.scan.inv.h">
        <P k="docs.scan.inv.p" />
      </Section>
      <Section heading="docs.scan.prof.h">
        <P k="docs.scan.prof.p" />
      </Section>
      <Section heading="docs.scan.sched.h">
        <P k="docs.scan.sched.p" />
        <DocChips
          items={[
            "scans.schedule.daily",
            "scans.schedule.weekly",
            "scans.schedule.monthly",
            "scans.schedule.quarterly",
          ]}
        />
      </Section>
      <Section heading="docs.scan.seg.h">
        <P k="docs.scan.seg.p" />
      </Section>
    </div>
  );
}

function AgentsGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.agents.what.h">
        <P k="docs.agents.what.p" />
        <DocArch />
      </Section>
      <Section heading="docs.agents.deploy.h">
        <P k="docs.agents.deploy.p" />
      </Section>
      <Section heading="docs.agents.health.h">
        <P k="docs.agents.health.p" />
        <DocLegend items={AGENT_STATUS_LEGEND} />
      </Section>
      <Section heading="docs.agents.coverage.h">
        <P k="docs.agents.coverage.p" />
      </Section>
    </div>
  );
}

function EvidenceGuide() {
  return (
    <div className="space-y-6">
      <DocFlow
        steps={[
          { icon: "🔎", label: "docs.flow.scan" },
          { icon: "🔀", label: "docs.flow.detect" },
          { icon: "📨", label: "docs.flow.notify" },
          { icon: "📦", label: "docs.flow.evidence" },
        ]}
      />
      <Section heading="docs.ev.changes.h">
        <P k="docs.ev.changes.p" />
      </Section>
      <Section heading="docs.ev.tasks.h">
        <P k="docs.ev.tasks.p" />
      </Section>
      <Section heading="docs.ev.export.h">
        <P k="docs.ev.export.p" />
      </Section>
      <Section heading="docs.ev.audit.h">
        <P k="docs.ev.audit.p" />
      </Section>
    </div>
  );
}

function ComplianceGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.comp.cadence.h">
        <P k="docs.comp.cadence.p" />
        <DocLegend items={CADENCE_LEGEND} />
      </Section>
      <Section heading="docs.comp.asv.h">
        <P k="docs.comp.asv.p" />
      </Section>
      <Section heading="docs.comp.integr.h">
        <P k="docs.comp.integr.p" />
      </Section>
      <Section heading="docs.comp.updates.h">
        <P k="docs.comp.updates.p" />
      </Section>
    </div>
  );
}

export const GUIDES: Guide[] = [
  {
    id: "getting-started",
    titleKey: "docs.gs.title",
    summaryKey: "docs.gs.summary",
    icon: "🚀",
    Body: GettingStartedGuide,
  },
  {
    id: "scanning",
    titleKey: "docs.scan.title",
    summaryKey: "docs.scan.summary",
    icon: "🔎",
    Body: ScanningGuide,
  },
  {
    id: "agents",
    titleKey: "docs.agents.title",
    summaryKey: "docs.agents.summary",
    icon: "🛰️",
    Body: AgentsGuide,
  },
  {
    id: "evidence",
    titleKey: "docs.ev.title",
    summaryKey: "docs.ev.summary",
    icon: "📦",
    Body: EvidenceGuide,
  },
  {
    id: "compliance",
    titleKey: "docs.comp.title",
    summaryKey: "docs.comp.summary",
    icon: "✅",
    Body: ComplianceGuide,
  },
  {
    id: "cve",
    titleKey: "docs.cve.title",
    summaryKey: "docs.cve.summary",
    icon: "🛡️",
    Body: CveGuide,
  },
];
