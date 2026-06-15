import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type IpRange,
  type Vlan,
  createIpRange,
  createVlan,
  deleteIpRange,
  deleteVlan,
  listIpRanges,
  listVlans,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export default function VlansPage() {
  const { user } = useAuth();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [vlans, setVlans] = useState<Vlan[]>([]);
  const [ipRanges, setIpRanges] = useState<IpRange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [description, setDescription] = useState("");

  const [cidr, setCidr] = useState("");
  const [rangeVlanId, setRangeVlanId] = useState("");
  const [rangeDesc, setRangeDesc] = useState("");

  async function reload() {
    setLoading(true);
    try {
      const [v, r] = await Promise.all([listVlans(), listIpRanges()]);
      setVlans(v);
      setIpRanges(r);
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

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createVlan({
        name,
        vlan_tag: tag ? Number(tag) : null,
        description: description || null,
      });
      setName("");
      setTag("");
      setDescription("");
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm("Delete this VLAN?")) return;
    setError(null);
    try {
      await deleteVlan(id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onCreateRange(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createIpRange({
        cidr,
        vlan_id: rangeVlanId || null,
        description: rangeDesc || null,
      });
      setCidr("");
      setRangeVlanId("");
      setRangeDesc("");
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDeleteRange(id: string) {
    if (!window.confirm("Delete this IP range?")) return;
    setError(null);
    try {
      await deleteIpRange(id);
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-200">VLANs</h2>
        <p className="text-sm text-slate-500">
          Group assets by network segment. Add a VLAN, then assign assets to it.
        </p>
      </div>

      {canWrite && (
      <form
        onSubmit={onCreate}
        className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-slate-900 p-4 sm:grid-cols-4"
      >
        <input
          className={inputClass}
          placeholder="Name (e.g. DMZ)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className={inputClass}
          placeholder="VLAN tag (1-4094)"
          type="number"
          min={1}
          max={4094}
          value={tag}
          onChange={(e) => setTag(e.target.value)}
        />
        <input
          className={inputClass}
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button
          type="submit"
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          Add VLAN
        </button>
      </form>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Tag</th>
              <th className="px-4 py-2 font-medium">Description</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={4}>
                  Loading…
                </td>
              </tr>
            ) : vlans.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={4}>
                  No VLANs yet.
                </td>
              </tr>
            ) : (
              vlans.map((v) => (
                <tr key={v.id} className="bg-slate-950">
                  <td className="px-4 py-2 text-slate-100">{v.name}</td>
                  <td className="px-4 py-2 text-slate-300">{v.vlan_tag ?? "-"}</td>
                  <td className="px-4 py-2 text-slate-400">{v.description ?? "-"}</td>
                  <td className="px-4 py-2 text-right">
                    {canWrite && (
                      <button
                        onClick={() => onDelete(v.id)}
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

      <div className="pt-2">
        <h2 className="text-lg font-semibold text-slate-200">IP ranges</h2>
        <p className="text-sm text-slate-500">
          CIDR blocks, optionally tied to a VLAN. They document the address space
          you expect to scan.
        </p>
      </div>

      {canWrite && (
        <form
          onSubmit={onCreateRange}
          className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-slate-900 p-4 sm:grid-cols-4"
        >
          <input
            className={inputClass}
            placeholder="CIDR (e.g. 10.0.0.0/24)"
            value={cidr}
            onChange={(e) => setCidr(e.target.value)}
            required
          />
          <select
            className={inputClass}
            value={rangeVlanId}
            onChange={(e) => setRangeVlanId(e.target.value)}
          >
            <option value="">No VLAN</option>
            {vlans.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <input
            className={inputClass}
            placeholder="Description"
            value={rangeDesc}
            onChange={(e) => setRangeDesc(e.target.value)}
          />
          <button
            type="submit"
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Add IP range
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">CIDR</th>
              <th className="px-4 py-2 font-medium">VLAN</th>
              <th className="px-4 py-2 font-medium">Description</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={4}>
                  Loading…
                </td>
              </tr>
            ) : ipRanges.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={4}>
                  No IP ranges yet.
                </td>
              </tr>
            ) : (
              ipRanges.map((r) => (
                <tr key={r.id} className="bg-slate-950">
                  <td className="px-4 py-2 font-mono text-slate-100">{r.cidr}</td>
                  <td className="px-4 py-2 text-slate-300">{vlanName(r.vlan_id)}</td>
                  <td className="px-4 py-2 text-slate-400">{r.description ?? "-"}</td>
                  <td className="px-4 py-2 text-right">
                    {canWrite && (
                      <button
                        onClick={() => onDeleteRange(r.id)}
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
    </div>
  );
}
