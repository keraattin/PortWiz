import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type ComplianceFramework,
  type Observation,
  type ScanProfile,
  type ScanRun,
  type ScanRunStatus,
  type ScanType,
  createScanProfile,
  deleteScanProfile,
  listRunObservations,
  listScanProfiles,
  listScanRuns,
  runScanProfile,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Modal from "../components/Modal";
import Pagination, { usePagination } from "../components/Pagination";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

const SCAN_TYPES: ScanType[] = ["connect", "syn", "udp"];

const STATUS_BADGE: Record<ScanRunStatus, string> = {
  pending: "bg-slate-700 text-slate-300",
  running: "bg-sky-900 text-sky-300",
  completed: "bg-emerald-900 text-emerald-300",
  partial: "bg-amber-900 text-amber-300",
  failed: "bg-red-900 text-red-300",
};

function parseTargets(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

export default function ScansPage() {
  const { user } = useAuth();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [runs, setRuns] = useState<ScanRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<ScanRun | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const obsPage = usePagination(observations, 12);

  const [name, setName] = useState("");
  const [targets, setTargets] = useState("");
  const [ports, setPorts] = useState("top-1000");
  const [segment, setSegment] = useState("");
  const [framework, setFramework] = useState<ComplianceFramework | "">("");
  const [cron, setCron] = useState("");
  const [scanType, setScanType] = useState<ScanType>("connect");
  const [serviceDetection, setServiceDetection] = useState(true);

  async function reload() {
    try {
      const [p, r] = await Promise.all([listScanProfiles(), listScanRuns()]);
      setProfiles(p);
      setRuns(r);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const profileName = (id: string | null) =>
    id ? (profiles.find((p) => p.id === id)?.name ?? "(deleted)") : "(ad-hoc)";

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createScanProfile({
        name,
        targets: parseTargets(targets),
        ports,
        scan_type: scanType,
        service_detection: serviceDetection,
        segment: segment || null,
        compliance_framework: framework || null,
        cron: cron || null,
      });
      setName("");
      setTargets("");
      setPorts("top-1000");
      setSegment("");
      setFramework("");
      setCron("");
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onRun(profile: ScanProfile) {
    setError(null);
    try {
      await runScanProfile(profile.id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDeleteProfile(id: string) {
    if (!window.confirm("Delete this scan profile?")) return;
    setError(null);
    try {
      await deleteScanProfile(id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onViewRun(run: ScanRun) {
    setError(null);
    setSelectedRun(run);
    setObservations([]);
    obsPage.setPage(0);
    try {
      setObservations(await listRunObservations(run.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">Scan profiles</h2>
        <p className="text-sm text-slate-500">
          A profile defines what to scan (targets, ports) and, optionally, a cron
          schedule. Runs are picked up by an online agent; without one they stay
          pending.
        </p>
        {canWrite && (
        <form
          onSubmit={onCreate}
          className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-slate-900 p-4 sm:grid-cols-3 lg:grid-cols-5"
        >
          <input
            className={inputClass}
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className={`${inputClass} sm:col-span-2`}
            placeholder="Targets (IPs/CIDRs, comma or space separated)"
            value={targets}
            onChange={(e) => setTargets(e.target.value)}
            required
          />
          <input
            className={inputClass}
            placeholder="Ports (e.g. top-1000, 1-1000, 22,80)"
            value={ports}
            onChange={(e) => setPorts(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Segment (optional, e.g. vlan10)"
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
          />
          <select
            className={inputClass}
            value={framework}
            onChange={(e) => setFramework(e.target.value as ComplianceFramework | "")}
          >
            <option value="">No framework</option>
            <option value="pci">PCI-DSS</option>
            <option value="hipaa">HIPAA</option>
            <option value="soc2">SOC 2</option>
            <option value="iso27001">ISO 27001</option>
            <option value="nist">NIST</option>
          </select>
          <input
            className={inputClass}
            placeholder="Cron (optional, e.g. 0 2 * * *)"
            value={cron}
            onChange={(e) => setCron(e.target.value)}
          />
          <select
            className={inputClass}
            value={scanType}
            onChange={(e) => setScanType(e.target.value as ScanType)}
          >
            {SCAN_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={serviceDetection}
              onChange={(e) => setServiceDetection(e.target.checked)}
            />
            Service detection
          </label>
          <button
            type="submit"
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Add profile
          </button>
        </form>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Targets</th>
                <th className="px-4 py-2 font-medium">Ports</th>
                <th className="px-4 py-2 font-medium">Segment</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {profiles.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={6}>
                    No scan profiles yet.
                  </td>
                </tr>
              ) : (
                profiles.map((p) => (
                  <tr key={p.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{p.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-300">
                      {p.targets.join(", ")}
                    </td>
                    <td className="px-4 py-2 text-slate-300">{p.ports}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {p.segment ?? <span className="text-slate-600">any</span>}
                    </td>
                    <td className="px-4 py-2 text-slate-400">{p.scan_type}</td>
                    <td className="px-4 py-2 text-right">
                      {canWrite ? (
                        <>
                          <button
                            onClick={() => onRun(p)}
                            className="mr-3 text-xs font-medium text-emerald-400 hover:text-emerald-300"
                          >
                            Run now
                          </button>
                          <button
                            onClick={() => onDeleteProfile(p.id)}
                            className="text-xs text-red-400 hover:text-red-300"
                          >
                            Delete
                          </button>
                        </>
                      ) : (
                        <span className="text-xs text-slate-600">read-only</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200">Recent scan runs</h2>
          <button
            onClick={reload}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Refresh
          </button>
        </div>
        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Profile</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Started</th>
                <th className="px-4 py-2 font-medium">Finished</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {runs.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    No scan runs yet.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{profileName(r.scan_profile_id)}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[r.status]}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {r.finished_at ? new Date(r.finished_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => onViewRun(r)}
                        className="text-xs font-medium text-sky-400 hover:text-sky-300"
                      >
                        View results
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Modal
        open={selectedRun !== null}
        onClose={() => setSelectedRun(null)}
        title={
          selectedRun
            ? `Results for run ${selectedRun.id.slice(0, 8)} (${observations.length} open ports)`
            : ""
        }
        wide
      >
        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Host</th>
                <th className="px-4 py-2 font-medium">Port</th>
                <th className="px-4 py-2 font-medium">State</th>
                <th className="px-4 py-2 font-medium">Service</th>
                <th className="px-4 py-2 font-medium">Version</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {observations.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    No open ports recorded for this run.
                  </td>
                </tr>
              ) : (
                obsPage.slice.map((o) => (
                  <tr key={o.id} className="bg-slate-950">
                    <td className="px-4 py-2 font-mono text-slate-100">{o.ip}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {o.port}/{o.protocol}
                    </td>
                    <td className="px-4 py-2 text-emerald-400">{o.state}</td>
                    <td className="px-4 py-2 text-slate-300">{o.service ?? "-"}</td>
                    <td className="px-4 py-2 text-slate-400">
                      {[o.product, o.version].filter(Boolean).join(" ") || "-"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={obsPage.page}
          pageCount={obsPage.pageCount}
          total={obsPage.total}
          onPage={obsPage.setPage}
        />
      </Modal>
    </div>
  );
}
