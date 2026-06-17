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
import FormField from "../components/FormField";
import Modal from "../components/Modal";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

export default function VlansPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [vlans, setVlans] = useState<Vlan[]>([]);
  const [ipRanges, setIpRanges] = useState<IpRange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [vlanOpen, setVlanOpen] = useState(false);
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [description, setDescription] = useState("");

  const [rangeOpen, setRangeOpen] = useState(false);
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

  function openAddVlan() {
    setError(null);
    setName("");
    setTag("");
    setDescription("");
    setVlanOpen(true);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createVlan({
        name,
        vlan_tag: tag ? Number(tag) : null,
        description: description || null,
      });
      setVlanOpen(false);
      toast.success(t("vlans.added"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm(t("vlans.confirmDelete"))) return;
    try {
      await deleteVlan(id);
      toast.success(t("vlans.deleted"));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  function openAddRange() {
    setError(null);
    setCidr("");
    setRangeVlanId("");
    setRangeDesc("");
    setRangeOpen(true);
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
      setRangeOpen(false);
      toast.success(t("ranges.added"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDeleteRange(id: string) {
    if (!window.confirm(t("ranges.confirmDelete"))) return;
    try {
      await deleteIpRange(id);
      toast.success(t("ranges.deleted"));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">{t("vlans.title")}</h2>
          <p className="text-sm text-slate-500">{t("vlans.subtitle")}</p>
        </div>
        {canWrite && (
          <button
            onClick={openAddVlan}
            className="whitespace-nowrap rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            {t("vlans.add")}
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">{t("vlans.col.name")}</th>
              <th className="px-4 py-2 font-medium">{t("vlans.col.tag")}</th>
              <th className="px-4 py-2 font-medium">{t("vlans.col.description")}</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={4}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : vlans.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                  {t("vlans.empty")}
                  {canWrite && (
                    <>
                      {" "}
                      <button
                        onClick={openAddVlan}
                        className="font-medium text-emerald-400 hover:text-emerald-300"
                      >
                        {t("vlans.addFirst")}
                      </button>
                    </>
                  )}
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
                        {t("common.delete")}
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-start justify-between gap-3 pt-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">{t("ranges.title")}</h2>
          <p className="text-sm text-slate-500">{t("ranges.subtitle")}</p>
        </div>
        {canWrite && (
          <button
            onClick={openAddRange}
            className="whitespace-nowrap rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            {t("ranges.add")}
          </button>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">{t("ranges.col.cidr")}</th>
              <th className="px-4 py-2 font-medium">{t("ranges.col.vlan")}</th>
              <th className="px-4 py-2 font-medium">{t("ranges.col.description")}</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={4}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : ipRanges.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                  {t("ranges.empty")}
                  {canWrite && (
                    <>
                      {" "}
                      <button
                        onClick={openAddRange}
                        className="font-medium text-emerald-400 hover:text-emerald-300"
                      >
                        {t("ranges.addFirst")}
                      </button>
                    </>
                  )}
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
                        {t("common.delete")}
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Modal open={vlanOpen} onClose={() => setVlanOpen(false)} title={t("vlans.add")}>
        <form onSubmit={onCreate} className="space-y-3">
          <FormField label={t("vlans.f.name")} hint={t("vlans.f.nameHint")}>
            <input
              className={inputClass}
              placeholder="DMZ"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </FormField>
          <FormField label={t("vlans.f.tag")} hint={t("vlans.f.tagHint")}>
            <input
              className={inputClass}
              type="number"
              min={1}
              max={4094}
              placeholder="10"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
            />
          </FormField>
          <FormField label={t("vlans.f.description")} hint={t("vlans.f.descriptionHint")}>
            <input
              className={inputClass}
              placeholder="Internet-facing servers"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              {t("vlans.add")}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={rangeOpen} onClose={() => setRangeOpen(false)} title={t("ranges.add")}>
        <form onSubmit={onCreateRange} className="space-y-3">
          <FormField label={t("ranges.f.cidr")} hint={t("ranges.f.cidrHint")}>
            <input
              className={inputClass}
              placeholder="10.0.0.0/24"
              value={cidr}
              onChange={(e) => setCidr(e.target.value)}
              required
            />
          </FormField>
          <FormField label={t("ranges.f.vlan")} hint={t("ranges.f.vlanHint")}>
            <select
              className={inputClass}
              value={rangeVlanId}
              onChange={(e) => setRangeVlanId(e.target.value)}
            >
              <option value="">{t("ranges.f.noVlan")}</option>
              {vlans.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t("ranges.f.description")} hint={t("ranges.f.descriptionHint")}>
            <input
              className={inputClass}
              placeholder="Server subnet"
              value={rangeDesc}
              onChange={(e) => setRangeDesc(e.target.value)}
            />
          </FormField>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              {t("ranges.add")}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
