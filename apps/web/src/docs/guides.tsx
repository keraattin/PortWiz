import { type ReactNode } from "react";
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

function GettingStartedGuide() {
  return (
    <div className="space-y-6">
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
      </Section>
      <Section heading="docs.agents.deploy.h">
        <P k="docs.agents.deploy.p" />
      </Section>
      <Section heading="docs.agents.health.h">
        <P k="docs.agents.health.p" />
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
