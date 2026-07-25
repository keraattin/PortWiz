import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  type Asset,
  type CVEFinding,
  type ChangeEvent,
  type Criticality,
  type CurrentUser,
  type DataSensitivity,
  type OpenPort,
  type Vlan,
  deleteAsset,
  fetchCVEFindings,
  getAsset,
  listChanges,
  listOpenPorts,
  listUsers,
  listVlans,
  updateAsset,
} from "../api/client";
import ChangeTimeline from "../components/ChangeTimeline";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import FormField from "../components/FormField";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

const CRITICALITIES: Criticality[] = ["low", "medium", "high", "critical"];
const SENSITIVITIES: DataSensitivity[] = ["none", "pii", "cde", "ephi"];

const CRIT_BADGE: Record<Criticality, string> = {
  low: "bg-slate-700 text-slate-300",
  medium: "bg-sky-900 text-sky-300",
  high: "bg-amber-900 text-amber-300",
  critical: "bg-red-900 text-red-300",
};

const SEV_BADGE: Record<string, string> = {
  critical: "bg-red-900 text-red-300",
  high: "bg-orange-900 text-orange-200",
  medium: "bg-amber-900 text-amber-300",
  low: "bg-slate-700 text-slate-300",
  unknown: "bg-slate-700 text-slate-400",
};

export default function AssetDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const toast = useToast();
  const canWrite = user?.role === "admin" || user?.role === "operator";

  const [asset, setAsset] = useState<Asset | null>(null);
  const [vlans, setVlans] = useState<Vlan[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [ports, setPorts] = useState<OpenPort[]>([]);
  const [cves, setCves] = useState<CVEFinding[]>([]);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit form state, seeded from the loaded asset.
  const [ip, setIp] = useState("");
  const [hostname, setHostname] = useState("");
  const [vlanId, setVlanId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [criticality, setCriticality] = useState<Criticality>("medium");
  const [sensitivity, setSensitivity] = useState<DataSensitivity>("none");
  const [description, setDescription] = useState("");

  async function load() {
    setLoading(true);
    try {
      // The asset loads first so its IP can key the CVE lookup, then the rest
      // fans out in parallel.
      const a = await getAsset(id);
      const [v, u, p, c, ch] = await Promise.all([
        listVlans(),
        listUsers(),
        listOpenPorts({ asset_id: id }),
        fetchCVEFindings({ ip: a.ip }),
        listChanges({ ip: a.ip }),
      ]);
      setAsset(a);
      setVlans(v);
      setUsers(u);
      setPorts(p);
      setCves(c);
      setChanges(ch);
      setIp(a.ip);
      setHostname(a.hostname ?? "");
      setVlanId(a.vlan_id ?? "");
      setOwnerId(a.owner_id ?? "");
      setCriticality(a.criticality);
      setSensitivity(a.data_sensitivity);
      setDescription(a.description ?? "");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const vlanName = (vid: string | null) =>
    vid ? (vlans.find((v) => v.id === vid)?.name ?? "-") : "-";
  const ownerEmail = (oid: string | null) =>
    oid ? (users.find((u) => u.id === oid)?.email ?? "-") : "-";

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!asset) return;
    try {
      const updated = await updateAsset(asset.id, {
        ip,
        hostname: hostname || null,
        vlan_id: vlanId || null,
        owner_id: ownerId || null,
        criticality,
        data_sensitivity: sensitivity,
        description: description || null,
      });
      setAsset(updated);
      toast.success(t("assetDetail.saved"));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function onDelete() {
    if (!asset) return;
    if (!window.confirm(t("assets.confirmDelete"))) return;
    try {
      await deleteAsset(asset.id);
      toast.success(t("assets.deleted"));
      navigate("/assets");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  const back = (
    <Link to="/assets" className="text-sm text-slate-400 hover:text-slate-200">
      ← {t("assetDetail.back")}
    </Link>
  );

  if (loading) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-slate-500">{t("common.loading")}</p>
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="space-y-4">
        {back}
        <p className="text-sm text-red-400">{error ?? t("assetDetail.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {back}

      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold text-slate-100">{asset.ip}</h1>
          <span className={`rounded-full px-2 py-0.5 text-xs ${CRIT_BADGE[asset.criticality]}`}>
            {t(`crit.${asset.criticality}` as TKey)}
          </span>
          {asset.hostname && <span className="text-slate-400">{asset.hostname}</span>}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {asset.discovered ? t("assetDetail.discovered") : t("assetDetail.manual")}
          {" · "}
          {t("assetDetail.created")}: {new Date(asset.created_at).toLocaleString()}
          {" · "}
          {t("assetDetail.updated")}: {new Date(asset.updated_at).toLocaleString()}
        </p>
      </div>

      {canWrite ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <form onSubmit={onSave} className="space-y-3">
            <p className="text-sm font-medium text-slate-300">{t("assetDetail.editTitle")}</p>
            <FormField label={t("assets.f.ip")}>
              <input
                className={inputClass}
                value={ip}
                onChange={(e) => setIp(e.target.value)}
                required
              />
            </FormField>
            <FormField label={t("assets.f.hostname")}>
              <input
                className={inputClass}
                value={hostname}
                onChange={(e) => setHostname(e.target.value)}
              />
            </FormField>
            <FormField label={t("assets.f.vlan")}>
              <select className={inputClass} value={vlanId} onChange={(e) => setVlanId(e.target.value)}>
                <option value="">{t("assets.f.noVlan")}</option>
                {vlans.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label={t("assets.f.owner")}>
              <select
                className={inputClass}
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value)}
              >
                <option value="">{t("assets.f.noOwner")}</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.email}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label={t("assets.f.criticality")}>
              <select
                className={inputClass}
                value={criticality}
                onChange={(e) => setCriticality(e.target.value as Criticality)}
              >
                {CRITICALITIES.map((c) => (
                  <option key={c} value={c}>
                    {t(`crit.${c}` as TKey)}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label={t("assets.f.sensitivity")}>
              <select
                className={inputClass}
                value={sensitivity}
                onChange={(e) => setSensitivity(e.target.value as DataSensitivity)}
              >
                {SENSITIVITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label={t("assetDetail.descriptionLabel")} hint={t("assetDetail.descriptionHint")}>
              <textarea
                className={inputClass}
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </FormField>
            <div className="flex justify-end">
              <Button type="submit">{t("assetDetail.save")}</Button>
            </div>
          </form>

          <div className="mt-4 border-t border-slate-800 pt-4">
            <button
              type="button"
              onClick={() => void onDelete()}
              className="text-sm text-red-400 hover:text-red-300"
            >
              {t("assetDetail.delete")}
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <p className="mb-3 text-sm font-medium text-slate-300">{t("assetDetail.details")}</p>
          <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            {(
              [
                ["assets.col.hostname", asset.hostname ?? "-"],
                ["assets.col.vlan", vlanName(asset.vlan_id)],
                ["assets.col.owner", ownerEmail(asset.owner_id)],
                ["assets.col.sensitivity", asset.data_sensitivity.toUpperCase()],
              ] as [TKey, string][]
            ).map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 border-b border-slate-800/60 py-1">
                <dt className="text-slate-500">{t(label)}</dt>
                <dd className="text-right text-slate-200">{value}</dd>
              </div>
            ))}
          </dl>
          {asset.description && (
            <p className="mt-3 whitespace-pre-line border-t border-slate-800 pt-3 text-sm text-slate-300">
              {asset.description}
            </p>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-1 flex items-center justify-between gap-3">
          <p className="text-sm font-medium text-slate-300">{t("assetDetail.openPorts")}</p>
          <Link to="/ports" className="text-xs text-emerald-400 hover:text-emerald-300">
            {t("dashboard.viewAll")}
          </Link>
        </div>
        <p className="mb-3 text-xs text-slate-600">{t("assetDetail.openPortsHint")}</p>
        {ports.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-600">{t("assetDetail.noOpenPorts")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">{t("ports.col.port")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.protocol")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.service")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.version")}</th>
                  <th className="px-4 py-2 font-medium">{t("ports.col.seen")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {ports
                  .slice()
                  .sort((a, b) => a.port - b.port || a.protocol.localeCompare(b.protocol))
                  .map((p) => (
                    <tr key={`${p.port}-${p.protocol}`} className="bg-slate-950">
                      <td className="px-4 py-2 font-mono text-slate-100">
                        <Link to={`/ports/${p.port}`} className="text-emerald-400 hover:text-emerald-300">
                          {p.port}
                        </Link>
                      </td>
                      <td className="px-4 py-2 uppercase text-slate-400">{p.protocol}</td>
                      <td className="px-4 py-2 text-slate-300">
                        {p.service || <span className="text-slate-600">-</span>}
                      </td>
                      <td className="px-4 py-2 text-slate-400">
                        {p.version || <span className="text-slate-600">-</span>}
                      </td>
                      <td className="px-4 py-2 text-xs text-slate-500">
                        {p.last_seen_open_at ? new Date(p.last_seen_open_at).toLocaleString() : "-"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <p className="text-sm font-medium text-slate-300">{t("assetDetail.vulns")}</p>
        <p className="mb-3 text-xs text-slate-600">{t("assetDetail.vulnsHint")}</p>
        {cves.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-600">{t("assetDetail.noVulns")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">{t("ports.col.port")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.cve")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.cvss")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.severity")}</th>
                  <th className="px-4 py-2 font-medium">{t("cve.col.summary")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {cves
                  .slice()
                  .sort((a, b) => (b.cvss ?? 0) - (a.cvss ?? 0))
                  .map((c) => (
                    <tr key={c.id} className="bg-slate-950">
                      <td className="px-4 py-2 font-mono text-slate-300">{c.port}</td>
                      <td className="px-4 py-2">
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-emerald-400 hover:text-emerald-300"
                        >
                          {c.cve_id}
                        </a>
                      </td>
                      <td className="px-4 py-2 text-slate-300">{c.cvss ?? "-"}</td>
                      <td className="px-4 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${SEV_BADGE[c.severity] ?? ""}`}>
                          {c.severity}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-slate-400">{c.summary}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <p className="text-sm font-medium text-slate-300">{t("timeline.title")}</p>
        <p className="mb-3 text-xs text-slate-600">{t("timeline.hint")}</p>
        <ChangeTimeline events={changes} context="port" />
      </div>
    </div>
  );
}
