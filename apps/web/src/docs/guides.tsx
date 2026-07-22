import { Fragment, type ReactNode } from "react";
import CveHowToBody from "../components/CveHowToBody";
import RoleMatrix from "../components/RoleMatrix";
import Callout from "../components/docs/Callout";
import CopyCode from "../components/docs/CopyCode";
import SeeAlso from "../components/docs/SeeAlso";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// A Docs guide: shown in the sidebar list and rendered as a page body. Add a new
// guide by appending to GUIDES and adding its i18n keys; the page and nav pick
// it up automatically. `toc` lists the section heading keys, in order, for the
// in-guide table of contents.
export interface Guide {
  id: string;
  titleKey: TKey;
  summaryKey: TKey;
  icon: string;
  Body: () => ReactNode;
  toc?: TKey[];
}

// A stable anchor for a section heading key, e.g. "docs.agents.coverage.h" ->
// "coverage". Shared by the section element id and the table-of-contents links.
export function sectionAnchor(headingKey: TKey): string {
  const parts = headingKey.split(".");
  return parts[parts.length - 2] ?? headingKey;
}

function Section({ heading, children }: { heading: TKey; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <section id={sectionAnchor(heading)} className="scroll-mt-4 space-y-2">
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

// Change severities, high to low, as the notification min-severity rule sees them.
const SEVERITY_LEGEND: { cls: string; label: TKey }[] = [
  { cls: "bg-red-900 text-red-300", label: "severity.high" },
  { cls: "bg-amber-900 text-amber-300", label: "severity.medium" },
  { cls: "bg-slate-700 text-slate-400", label: "severity.low" },
];

// Anatomy of an evidence package: the inputs on the left combine into one signed
// bundle on the right.
function DocPackage() {
  const { t } = useI18n();
  const parts: { icon: string; label: TKey }[] = [
    { icon: "📄", label: "docs.pkg.scan" },
    { icon: "🔀", label: "docs.pkg.diff" },
    { icon: "✅", label: "docs.pkg.task" },
    { icon: "🔗", label: "docs.pkg.audit" },
  ];
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 p-4 sm:flex-row sm:justify-center">
      <div className="grid gap-2">
        {parts.map((p) => (
          <div
            key={p.label}
            className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-300"
          >
            <span aria-hidden="true">{p.icon}</span>
            {t(p.label)}
          </div>
        ))}
      </div>
      <Arrow />
      <div className="rounded-lg border border-emerald-800 bg-emerald-950/40 px-4 py-3 text-center text-sm font-medium text-emerald-200">
        📦 {t("docs.pkg.out")}
      </div>
    </div>
  );
}

// The hash chain: each event carries the previous event's hash, so any edit
// breaks the chain and is detectable.
function DocHashChain() {
  const { t } = useI18n();
  const hashes = ["a1b2", "c3d4", "e5f6"];
  return (
    <div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {hashes.map((h, i) => (
          <Fragment key={h}>
            <div className="flex-1 rounded-lg border border-slate-800 bg-slate-950 p-3">
              <div className="text-xs font-medium text-slate-200">
                {t("docs.hash.event")} #{i + 1}
              </div>
              <div className="mt-1 font-mono text-[11px] text-slate-500">
                prev_hash: {i === 0 ? "-" : `${hashes[i - 1]}…`}
              </div>
              <div className="font-mono text-[11px] text-emerald-400">hash: {h}…</div>
            </div>
            {i < hashes.length - 1 && (
              <span className="self-center text-slate-600" aria-hidden="true">
                🔗
              </span>
            )}
          </Fragment>
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-500">{t("docs.hash.note")}</p>
    </div>
  );
}

// A required-interval timeline: green scan marks along the window, a red due
// marker at the end.
function DocTimeline() {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
      <div className="relative h-2 rounded-full bg-slate-800">
        {[10, 40, 70].map((pct) => (
          <span
            key={pct}
            style={{ left: `${pct}%` }}
            className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-500"
          />
        ))}
        <span className="absolute right-0 top-1/2 h-4 w-0.5 -translate-y-1/2 bg-red-500" />
      </div>
      <div className="mt-2 flex justify-between text-[11px]">
        <span className="text-slate-500">{t("docs.timeline.start")}</span>
        <span className="text-emerald-400">{t("docs.timeline.scans")}</span>
        <span className="text-red-400">{t("docs.timeline.due")}</span>
      </div>
    </div>
  );
}

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
        <Callout variant="tip">
          <P k="docs.gs.tip.p" />
        </Callout>
      </Section>
      <SeeAlso
        items={[
          { id: "scanning", title: "docs.scan.title" },
          { id: "agents", title: "docs.agents.title" },
        ]}
      />
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
      <SeeAlso
        items={[
          { id: "scanning", title: "docs.scan.title" },
          { id: "compliance", title: "docs.comp.title" },
        ]}
      />
    </div>
  );
}

function ScanningGuide() {
  return (
    <div className="space-y-6">
      <DocFlow
        steps={[
          { icon: "🗂️", label: "docs.life.profile" },
          { icon: "🛰️", label: "docs.life.agent" },
          { icon: "🔎", label: "docs.flow.scan" },
          { icon: "📥", label: "docs.life.result" },
          { icon: "🔀", label: "docs.flow.detect" },
        ]}
      />
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
      <SeeAlso
        items={[
          { id: "agents", title: "docs.agents.title" },
          { id: "evidence", title: "docs.ev.title" },
        ]}
      />
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
        <Callout variant="warning">
          <P k="docs.agents.coverage.p" />
        </Callout>
      </Section>
      <SeeAlso
        items={[
          { id: "scanning", title: "docs.scan.title" },
          { id: "getting-started", title: "docs.gs.title" },
        ]}
      />
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
        <DocPackage />
      </Section>
      <Section heading="docs.ev.audit.h">
        <P k="docs.ev.audit.p" />
        <DocHashChain />
      </Section>
      <SeeAlso
        items={[
          { id: "compliance", title: "docs.comp.title" },
          { id: "scanning", title: "docs.scan.title" },
        ]}
      />
    </div>
  );
}

function ComplianceGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.comp.cadence.h">
        <P k="docs.comp.cadence.p" />
        <DocTimeline />
        <DocLegend items={CADENCE_LEGEND} />
      </Section>
      <Section heading="docs.comp.asv.h">
        <Callout variant="warning">
          <P k="docs.comp.asv.p" />
        </Callout>
      </Section>
      <Section heading="docs.comp.integr.h">
        <P k="docs.comp.integr.p" />
      </Section>
      <Section heading="docs.comp.updates.h">
        <P k="docs.comp.updates.p" />
      </Section>
      <SeeAlso
        items={[
          { id: "evidence", title: "docs.ev.title" },
          { id: "cve", title: "docs.cve.title" },
        ]}
      />
    </div>
  );
}

function IntegrationsGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.int.where.h">
        <P k="docs.int.where.p" />
      </Section>
      <Section heading="docs.int.jira.h">
        <P k="docs.int.jira.p" />
      </Section>
      <Section heading="docs.int.email.h">
        <P k="docs.int.email.p" />
      </Section>
      <Section heading="docs.int.netbox.h">
        <P k="docs.int.netbox.p" />
      </Section>
      <Section heading="docs.int.ai.h">
        <P k="docs.int.ai.p" />
      </Section>
      <SeeAlso
        items={[
          { id: "notifications", title: "docs.notif.title" },
          { id: "evidence", title: "docs.ev.title" },
        ]}
      />
    </div>
  );
}

function NotificationsGuide() {
  return (
    <div className="space-y-6">
      <DocFlow
        steps={[
          { icon: "🔀", label: "docs.flow.detect" },
          { icon: "🎚️", label: "docs.notif.flow.rules" },
          { icon: "📨", label: "docs.notif.flow.channels" },
        ]}
      />
      <Section heading="docs.notif.overview.h">
        <P k="docs.notif.overview.p" />
      </Section>
      <Section heading="docs.notif.channels.h">
        <P k="docs.notif.channels.p" />
        <Steps
          items={[
            "docs.notif.channels.email",
            "docs.notif.channels.slack",
            "docs.notif.channels.teams",
          ]}
        />
        <Callout variant="tip">
          <P k="docs.notif.channels.test" />
        </Callout>
      </Section>
      <Section heading="docs.notif.rules.h">
        <P k="docs.notif.rules.p" />
        <DocLegend items={SEVERITY_LEGEND} />
        <P k="docs.notif.rules.scope" />
      </Section>
      <Section heading="docs.notif.optout.h">
        <P k="docs.notif.optout.p" />
      </Section>
      <Section heading="docs.notif.timing.h">
        <P k="docs.notif.timing.p" />
        <Callout variant="note">
          <P k="docs.notif.timing.quiet" />
        </Callout>
      </Section>
      <SeeAlso
        items={[
          { id: "integrations", title: "docs.int.title" },
          { id: "evidence", title: "docs.ev.title" },
        ]}
      />
    </div>
  );
}

const INSTALL_DOCKER_DEV = `cd deploy
cp .env.example .env
docker compose up --build`;

const INSTALL_DOCKER_PROD = `cd deploy
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build`;

const INSTALL_NATIVE = `# API (Python 3.11+), from apps/api
pip install -e .
alembic upgrade head
uvicorn portwiz_api.main:app --host 0.0.0.0 --port 8000

# Worker + beat (from apps/api, same env)
celery -A portwiz_api.workers.celery_app.celery_app worker --loglevel=info
celery -A portwiz_api.workers.celery_app.celery_app beat --loglevel=info --schedule=./celerybeat-schedule

# Web (Node 22), from apps/web
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0

# Scan agent (Go 1.23), from apps/agent
go build -trimpath -o portwiz-agent ./cmd/agent
PORTWIZ_API_URL=http://localhost:8000 PORTWIZ_AGENT_TOKEN=<token> ./portwiz-agent run`;

const INSTALL_AGENT_RUN = `docker run -d --name portwiz-agent --restart unless-stopped \\
  -e PORTWIZ_API_URL=https://portwiz.example.com \\
  -e PORTWIZ_AGENT_TOKEN=<token> \\
  ghcr.io/<your-org>/portwiz-agent`;

// Sizing tiers for the control plane, as a small responsive table.
function SpecTable() {
  const { t } = useI18n();
  const tiers: TKey[] = [
    "docs.install.specs.tierMin",
    "docs.install.specs.tierRec",
    "docs.install.specs.tierHigh",
  ];
  const rows: { label: TKey; vals: string[] }[] = [
    { label: "docs.install.specs.rowHosts", vals: ["≤ 500", "500-5,000", "5,000+"] },
    { label: "docs.install.specs.rowCpu", vals: ["2 vCPU", "4 vCPU", "8+ vCPU"] },
    { label: "docs.install.specs.rowRam", vals: ["4 GB", "8 GB", "16 GB+"] },
    { label: "docs.install.specs.rowDisk", vals: ["20 GB", "100 GB", "200 GB+"] },
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="border-b border-slate-800 p-2 text-left" aria-hidden="true" />
            {tiers.map((k) => (
              <th
                key={k}
                className="border-b border-slate-800 p-2 text-left font-medium text-slate-200"
              >
                {t(k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th
                scope="row"
                className="border-b border-slate-800 p-2 text-left font-normal text-slate-400"
              >
                {t(r.label)}
              </th>
              {r.vals.map((v, i) => (
                <td key={i} className="border-b border-slate-800 p-2 text-slate-300">
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InstallationGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.install.overview.h">
        <P k="docs.install.overview.p" />
        <DocArch />
      </Section>
      <Section heading="docs.install.specs.h">
        <P k="docs.install.specs.p" />
        <SpecTable />
        <P k="docs.install.specs.agents" />
        <P k="docs.install.specs.ai" />
      </Section>
      <Section heading="docs.install.docker.h">
        <P k="docs.install.docker.p" />
        <CopyCode code={INSTALL_DOCKER_DEV} />
        <P k="docs.install.docker.prod" />
        <CopyCode code={INSTALL_DOCKER_PROD} />
      </Section>
      <Section heading="docs.install.native.h">
        <P k="docs.install.native.p" />
        <CopyCode code={INSTALL_NATIVE} />
        <Callout variant="note">
          <P k="docs.install.native.note" />
        </Callout>
      </Section>
      <Section heading="docs.install.agents.h">
        <P k="docs.install.agents.p" />
        <CopyCode code={INSTALL_AGENT_RUN} />
      </Section>
      <SeeAlso
        items={[
          { id: "agents", title: "docs.agents.title" },
          { id: "notifications", title: "docs.notif.title" },
        ]}
      />
    </div>
  );
}

function RolesGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.roles.three.h">
        <P k="docs.roles.three.p" />
        <RoleMatrix />
      </Section>
      <Section heading="docs.roles.sod.h">
        <Callout variant="note">
          <P k="docs.roles.sod.p" />
        </Callout>
      </Section>
    </div>
  );
}

function TroubleshootingGuide() {
  return (
    <div className="space-y-6">
      <Section heading="docs.ts.scan.h">
        <P k="docs.ts.scan.p" />
      </Section>
      <Section heading="docs.ts.agent.h">
        <P k="docs.ts.agent.p" />
      </Section>
      <Section heading="docs.ts.cve.h">
        <P k="docs.ts.cve.p" />
      </Section>
      <Section heading="docs.ts.integr.h">
        <P k="docs.ts.integr.p" />
      </Section>
      <Section heading="docs.ts.update.h">
        <P k="docs.ts.update.p" />
      </Section>
      <SeeAlso
        items={[
          { id: "agents", title: "docs.agents.title" },
          { id: "integrations", title: "docs.int.title" },
        ]}
      />
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
    toc: ["docs.gs.what.h", "docs.gs.steps.h", "docs.gs.roles.h", "docs.gs.tip.h"],
  },
  {
    id: "installation",
    titleKey: "docs.install.title",
    summaryKey: "docs.install.summary",
    icon: "⚙️",
    Body: InstallationGuide,
    toc: [
      "docs.install.overview.h",
      "docs.install.specs.h",
      "docs.install.docker.h",
      "docs.install.native.h",
      "docs.install.agents.h",
    ],
  },
  {
    id: "scanning",
    titleKey: "docs.scan.title",
    summaryKey: "docs.scan.summary",
    icon: "🔎",
    Body: ScanningGuide,
    toc: ["docs.scan.inv.h", "docs.scan.prof.h", "docs.scan.sched.h", "docs.scan.seg.h"],
  },
  {
    id: "agents",
    titleKey: "docs.agents.title",
    summaryKey: "docs.agents.summary",
    icon: "🛰️",
    Body: AgentsGuide,
    toc: [
      "docs.agents.what.h",
      "docs.agents.deploy.h",
      "docs.agents.health.h",
      "docs.agents.coverage.h",
    ],
  },
  {
    id: "evidence",
    titleKey: "docs.ev.title",
    summaryKey: "docs.ev.summary",
    icon: "📦",
    Body: EvidenceGuide,
    toc: ["docs.ev.changes.h", "docs.ev.tasks.h", "docs.ev.export.h", "docs.ev.audit.h"],
  },
  {
    id: "compliance",
    titleKey: "docs.comp.title",
    summaryKey: "docs.comp.summary",
    icon: "✅",
    Body: ComplianceGuide,
    toc: [
      "docs.comp.cadence.h",
      "docs.comp.asv.h",
      "docs.comp.integr.h",
      "docs.comp.updates.h",
    ],
  },
  {
    id: "cve",
    titleKey: "docs.cve.title",
    summaryKey: "docs.cve.summary",
    icon: "🛡️",
    Body: CveGuide,
    toc: ["docs.cve.overview.h", "docs.cve.online.h", "docs.cve.offline.h", "docs.cve.checks.h"],
  },
  {
    id: "integrations",
    titleKey: "docs.int.title",
    summaryKey: "docs.int.summary",
    icon: "🔌",
    Body: IntegrationsGuide,
    toc: [
      "docs.int.where.h",
      "docs.int.jira.h",
      "docs.int.email.h",
      "docs.int.netbox.h",
      "docs.int.ai.h",
    ],
  },
  {
    id: "notifications",
    titleKey: "docs.notif.title",
    summaryKey: "docs.notif.summary",
    icon: "📨",
    Body: NotificationsGuide,
    toc: [
      "docs.notif.overview.h",
      "docs.notif.channels.h",
      "docs.notif.rules.h",
      "docs.notif.optout.h",
      "docs.notif.timing.h",
    ],
  },
  {
    id: "roles",
    titleKey: "docs.roles.title",
    summaryKey: "docs.roles.summary",
    icon: "🔑",
    Body: RolesGuide,
    toc: ["docs.roles.three.h", "docs.roles.sod.h"],
  },
  {
    id: "troubleshooting",
    titleKey: "docs.ts.title",
    summaryKey: "docs.ts.summary",
    icon: "🛠️",
    Body: TroubleshootingGuide,
    toc: [
      "docs.ts.scan.h",
      "docs.ts.agent.h",
      "docs.ts.cve.h",
      "docs.ts.integr.h",
      "docs.ts.update.h",
    ],
  },
];
