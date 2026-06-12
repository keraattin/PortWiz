import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type Asset,
  type Criticality,
  type CurrentUser,
  type DataSensitivity,
  type Vlan,
  createAsset,
  deleteAsset,
  listAssets,
  listUsers,
  listVlans,
} from "../api/client";

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

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-200">Assets</h2>

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

      {error && <p className="text-sm text-red-400">{error}</p>}

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
              assets.map((a) => (
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
                    <button
                      onClick={() => onDelete(a.id)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
