import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type AuditEvent,
  type ChainVerification,
  type ComplianceStatusItem,
  type ScanProfile,
  downloadEvidenceJson,
  downloadEvidencePdf,
  fetchComplianceStatus,
  listAudit,
  listScanProfiles,
  verifyAudit,
} from "../api/client";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const PAGE_SIZE = 50;
const inputClass =
  "rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

const CADENCE_BADGE: Record<string, string> = {
  compliant: "bg-emerald-900 text-emerald-300",
  due_soon: "bg-amber-900 text-amber-300",
  overdue: "bg-red-900 text-red-300",
  never: "bg-slate-700 text-slate-400",
};

const FRAMEWORK_LABEL: Record<string, string> = {
  pci: "PCI-DSS",
  hipaa: "HIPAA",
  soc2: "SOC 2",
  iso27001: "ISO 27001",
  nist: "NIST",
};

export default function CompliancePage() {
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [cadence, setCadence] = useState<ComplianceStatusItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function verify() {
    setError(null);
    try {
      setChain(await verifyAudit());
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function loadAudit(reset: boolean) {
    setError(null);
    try {
      const startOffset = reset ? 0 : offset;
      const page = await listAudit({
        action: actionFilter || undefined,
        limit: PAGE_SIZE,
        offset: startOffset,
      });
      setTotal(page.total);
      setEvents(reset ? page.events : [...events, ...page.events]);
      setOffset(startOffset + page.events.length);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  useEffect(() => {
    void verify();
    void loadAudit(true);
    listScanProfiles()
      .then(setProfiles)
      .catch((e) => setError(errorMessage(e)));
    fetchComplianceStatus()
      .then(setCadence)
      .catch((e) => setError(errorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onFilter(e: FormEvent) {
    e.preventDefault();
    void loadAudit(true);
  }

  async function onDownload(fn: () => Promise<void>) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-8">
      {/* Scan cadence */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-200">Scan cadence</h2>
        <p className="text-sm text-slate-500">
          Whether each framework-tagged scan profile has been scanned within its
          required interval.
        </p>
        {cadence.length === 0 ? (
          <p className="text-sm text-slate-500">
            No scan profiles are tagged with a compliance framework yet. Tag one when
            creating a scan profile.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Profile</th>
                  <th className="px-4 py-2 font-medium">Framework</th>
                  <th className="px-4 py-2 font-medium">Required</th>
                  <th className="px-4 py-2 font-medium">Last scan</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">ASV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {cadence.map((c) => (
                  <tr key={c.profile_id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{c.profile_name}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {FRAMEWORK_LABEL[c.framework] ?? c.framework}
                    </td>
                    <td className="px-4 py-2 text-slate-400">every {c.cadence_days}d</td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {c.last_scan_at
                        ? `${new Date(c.last_scan_at).toLocaleDateString()} (${c.days_since}d ago)`
                        : "never"}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${CADENCE_BADGE[c.status] ?? CADENCE_BADGE.never}`}
                      >
                        {c.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {c.framework !== "pci" ? (
                        <span className="text-slate-600">-</span>
                      ) : c.asv_satisfied ? (
                        <span className="text-emerald-400">external (ASV)</span>
                      ) : (
                        <span className="text-amber-400">internal (not ASV)</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Chain integrity */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200">Audit chain integrity</h2>
          <button
            onClick={verify}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Verify
          </button>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          {chain === null ? (
            <span className="text-sm text-slate-400">Checking…</span>
          ) : chain.ok ? (
            <div className="flex items-center gap-3">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />
              <span className="text-sm text-emerald-400">
                Intact and tamper-evident
              </span>
              <span className="text-sm text-slate-500">
                ({chain.total} events, hash-chained)
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
              <span className="text-sm text-red-400">
                Broken at sequence {chain.broken_seq}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Evidence export */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-200">Evidence packages</h2>
        <p className="text-sm text-slate-500">
          Download a complete, auditor-ready package for a scan profile: exposure,
          confirmed changes, the audit-log slice, and the chain integrity check.
        </p>
        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Profile</th>
                <th className="px-4 py-2 font-medium">Targets</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {profiles.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={3}>
                    No scan profiles yet.
                  </td>
                </tr>
              ) : (
                profiles.map((p) => (
                  <tr key={p.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{p.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-400">
                      {p.targets.join(", ")}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => onDownload(() => downloadEvidenceJson(p.id, p.name))}
                        className="mr-3 text-xs font-medium text-sky-400 hover:text-sky-300"
                      >
                        Download JSON
                      </button>
                      <button
                        onClick={() => onDownload(() => downloadEvidencePdf(p.id, p.name))}
                        className="text-xs font-medium text-emerald-400 hover:text-emerald-300"
                      >
                        Download PDF
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Audit log */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200">Audit log</h2>
          <form onSubmit={onFilter} className="flex items-center gap-2">
            <input
              className={inputClass}
              placeholder="Filter by action (e.g. asset.created)"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
            />
            <button
              type="submit"
              className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Apply
            </button>
          </form>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Seq</th>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Actor</th>
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Target</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {events.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    No audit events.
                  </td>
                </tr>
              ) : (
                events.map((e) => (
                  <tr key={e.seq} className="bg-slate-950">
                    <td className="px-4 py-2 font-mono text-slate-500">{e.seq}</td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-slate-300">{e.actor_email ?? "system"}</td>
                    <td className="px-4 py-2 font-medium text-slate-100">{e.action}</td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {e.target_type ? `${e.target_type}:${(e.target_id ?? "").slice(0, 8)}` : "-"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            Showing {events.length} of {total}
          </span>
          {events.length < total && (
            <button
              onClick={() => loadAudit(false)}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:bg-slate-800"
            >
              Load more
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
