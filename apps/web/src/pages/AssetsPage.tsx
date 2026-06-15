import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type Asset,
  type AssetImportReport,
  type Criticality,
  type CurrentUser,
  type DataSensitivity,
  type Vlan,
  createAsset,
  deleteAsset,
  importAssets,
  listAssets,
  listUsers,
  listVlans,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Pagination, { usePagination } from "../components/Pagination";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

const CRITICALITIES: Criticality[] = ["low", "medium", "high", "critical"];
const SENSITIVITIES: DataSensitivity[] = ["none", "pii", "cde", "ephi"];

const CRIT_BADGE: Record<Criticality, string> = {
  low: "bg-slate-700 text-slate-300",
  medium: "bg-sky-900 text-sky-300",
  high: "bg-amber-900 text-amber-300",
  critical: "bg-red-900 text-red-300",
};

export default function AssetsPage() {
  const { user } = useAuth();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [assets, setAssets] = useState<Asset[]>([]);
  const [vlans, setVlans] = useState<Vlan[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ip, setIp] = useState("");
  const [hostname, setHostname] = useState("");
  const [vlanId, setVlanId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [criticality, setCriticality] = useState<Criticality>("medium");
  const [sensitivity, setSensitivity] = useState<DataSensitivity>("none");

  const [importFile, setImportFile] = useState<File | null>(null);
  const [onConflict, setOnConflict] = useState<"update" | "skip">("update");
  const [importReport, setImportReport] = useState<AssetImportReport | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const assetsPage = usePagination(assets, 15);

  async function reload() {
    setLoading(true);
    try {
      const [a, v, u] = await Promise.all([listAssets(), listVlans(), listUsers()]);
      setAssets(a);
      setVlans(v);
      setUsers(u);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const vlanName = (id: string | null) =>
    id ? (vlans.find((v) => v.id === id)?.name ?? "-") : "-";
  const ownerEmail = (id: string | null) =>
    id ? (users.find((u) => u.id === id)?.email ?? "-") : "-";

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createAsset({
        ip,
        hostname: hostname || null,
        vlan_id: vlanId || null,
        owner_id: ownerId || null,
        criticality,
        data_sensitivity: sensitivity,
      });
      setIp("");
      setHostname("");
      setVlanId("");
      setOwnerId("");
      setCriticality("medium");
      setSensitivity("none");
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm("Delete this asset?")) return;
    setError(null);
    try {
      await deleteAsset(id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onImport(e: FormEvent) {
    e.preventDefault();
    if (!importFile) return;
    setImportError(null);
    setImportReport(null);
    setImporting(true);
    try {
      const report = await importAssets(importFile, onConflict);
      setImportReport(report);
      await reload();
    } catch (err) {
      setImportError(errorMessage(err));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-200">Assets</h2>
        <p className="text-sm text-slate-500">
          The hosts PortWiz scans. Add them one at a time or import a CSV/Excel file;
          each carries an owner, criticality, and data-sensitivity for compliance.
        </p>
      </div>

      {canWrite && (
      <form
        onSubmit={onCreate}
        className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-slate-900 p-4 sm:grid-cols-3 lg:grid-cols-4"
      >
        <input
          className={inputClass}
          placeholder="IP address"
          value={ip}
          onChange={(e) => setIp(e.target.value)}
          required
        />
        <input
          className={inputClass}
          placeholder="Hostname"
          value={hostname}
          onChange={(e) => setHostname(e.target.value)}
        />
        <select className={inputClass} value={vlanId} onChange={(e) => setVlanId(e.target.value)}>
          <option value="">No VLAN</option>
          {vlans.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
        <select className={inputClass} value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
          <option value="">No owner</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.email}
            </option>
          ))}
        </select>
        <select
          className={inputClass}
          value={criticality}
          onChange={(e) => setCriticality(e.target.value as Criticality)}
        >
          {CRITICALITIES.map((c) => (
            <option key={c} value={c}>
              criticality: {c}
            </option>
          ))}
        </select>
        <select
          className={inputClass}
          value={sensitivity}
          onChange={(e) => setSensitivity(e.target.value as DataSensitivity)}
        >
          {SENSITIVITIES.map((s) => (
            <option key={s} value={s}>
              sensitivity: {s}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          Add asset
        </button>
      </form>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      {canWrite && (
      <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium text-slate-200">Bulk import</h3>
          <span className="text-xs text-slate-500">
            CSV or .xlsx with an "ip" column. Optional: hostname, vlan, owner,
            criticality, sensitivity, description.
          </span>
        </div>
        <form onSubmit={onImport} className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
            className="text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-slate-200 hover:file:bg-slate-700"
          />
          <select
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            value={onConflict}
            onChange={(e) => setOnConflict(e.target.value as "update" | "skip")}
          >
            <option value="update">Update existing</option>
            <option value="skip">Skip existing</option>
          </select>
          <button
            type="submit"
            disabled={!importFile || importing}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {importing ? "Importing…" : "Import"}
          </button>
        </form>
        {importError && <p className="text-sm text-red-400">{importError}</p>}
        {importReport && (
          <div className="space-y-2 text-sm">
            <p className="text-slate-300">
              {importReport.total} rows:{" "}
              <span className="text-emerald-400">{importReport.created} created</span>,{" "}
              <span className="text-sky-400">{importReport.updated} updated</span>,{" "}
              <span className="text-slate-400">{importReport.skipped} skipped</span>,{" "}
              <span className="text-red-400">{importReport.errors} errors</span>
            </p>
            {importReport.errors > 0 && (
              <ul className="space-y-1 text-xs text-red-400">
                {importReport.results
                  .filter((r) => r.status === "error")
                  .map((r) => (
                    <li key={r.row}>
                      Row {r.row}
                      {r.ip ? ` (${r.ip})` : ""}: {r.error}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        )}
      </section>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">IP</th>
              <th className="px-4 py-2 font-medium">Hostname</th>
              <th className="px-4 py-2 font-medium">VLAN</th>
              <th className="px-4 py-2 font-medium">Owner</th>
              <th className="px-4 py-2 font-medium">Criticality</th>
              <th className="px-4 py-2 font-medium">Sensitivity</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={7}>
                  Loading…
                </td>
              </tr>
            ) : assets.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={7}>
                  No assets yet.
                </td>
              </tr>
            ) : (
              assetsPage.slice.map((a) => (
                <tr key={a.id} className="bg-slate-950">
                  <td className="px-4 py-2 font-mono text-slate-100">{a.ip}</td>
                  <td className="px-4 py-2 text-slate-300">{a.hostname ?? "-"}</td>
                  <td className="px-4 py-2 text-slate-300">{vlanName(a.vlan_id)}</td>
                  <td className="px-4 py-2 text-slate-300">{ownerEmail(a.owner_id)}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${CRIT_BADGE[a.criticality]}`}>
                      {a.criticality}
                    </span>
                  </td>
                  <td className="px-4 py-2 uppercase text-slate-400">{a.data_sensitivity}</td>
                  <td className="px-4 py-2 text-right">
                    {canWrite && (
                      <button
                        onClick={() => onDelete(a.id)}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <Pagination
        page={assetsPage.page}
        pageCount={assetsPage.pageCount}
        total={assetsPage.total}
        onPage={assetsPage.setPage}
      />
    </div>
  );
}
