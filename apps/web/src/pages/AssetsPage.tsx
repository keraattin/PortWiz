import { type FormEvent, useEffect, useState } from "react";
import {
  type Asset,
  type AssetImportReport,
  type AssetPushReport,
  type AssetSyncReport,
  type Criticality,
  type CurrentUser,
  type DataSensitivity,
  type Vlan,
  createAsset,
  deleteAsset,
  downloadAssetImportTemplate,
  fetchSettings,
  importAssets,
  listAssets,
  listUsers,
  listVlans,
  pushAssetsToNetbox,
  syncAssets,
} from "../api/client";
import { inputClass } from "../components/formStyles";
import { useErrorMessage } from "../i18n/useErrorMessage";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import FormField from "../components/FormField";
import InfoCallout from "../components/InfoCallout";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
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

// Rank so criticality sorts by severity, not alphabetically.
const CRIT_RANK: Record<string, number> = { low: 0, medium: 1, high: 2, critical: 3 };

export default function AssetsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [assets, setAssets] = useState<Asset[]>([]);
  const [vlans, setVlans] = useState<Vlan[]>([]);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [addOpen, setAddOpen] = useState(false);
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

  const [syncReport, setSyncReport] = useState<AssetSyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const [pushReport, setPushReport] = useState<AssetPushReport | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushing, setPushing] = useState(false);
  const [netboxOn, setNetboxOn] = useState(false);
  const { sort, toggleSort } = useSort();
  const { filters, setFilter } = useColumnFilters();
  const [search, setSearch] = useState("");

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
    // NetBox sync/push only work once NetBox is connected in Settings.
    fetchSettings()
      .then((s) => setNetboxOn(s.netbox_configured))
      .catch(() => {
        /* leave NetBox actions disabled if status can't be read */
      });
  }, []);

  const vlanName = (id: string | null) =>
    id ? (vlans.find((v) => v.id === id)?.name ?? "-") : "-";
  const ownerEmail = (id: string | null) =>
    id ? (users.find((u) => u.id === id)?.email ?? "-") : "-";

  const columns: Column<Asset>[] = [
    { key: "ip", label: t("assets.col.ip"), filter: "text", get: (a) => a.ip },
    { key: "hostname", label: t("assets.col.hostname"), filter: "text", get: (a) => a.hostname ?? "" },
    { key: "vlan", label: t("assets.col.vlan"), filter: "text", get: (a) => vlanName(a.vlan_id) },
    { key: "owner", label: t("assets.col.owner"), filter: "text", get: (a) => ownerEmail(a.owner_id) },
    {
      key: "criticality",
      label: t("assets.col.criticality"),
      filter: CRITICALITIES.map((c) => ({ value: c, label: t(`crit.${c}` as TKey) })),
      get: (a) => a.criticality,
      rank: CRIT_RANK,
    },
    {
      key: "sensitivity",
      label: t("assets.col.sensitivity"),
      filter: SENSITIVITIES.map((s) => ({ value: s, label: s.toUpperCase() })),
      get: (a) => a.data_sensitivity,
    },
  ];
  const processed = processRows(assets, columns, sort, filters, search);
  const assetsPage = usePagination(processed, 15);
  const onFilter = (key: string, v: string) => {
    setFilter(key, v);
    assetsPage.setPage(0);
  };

  function openAdd() {
    setError(null);
    setIp("");
    setHostname("");
    setVlanId("");
    setOwnerId("");
    setCriticality("medium");
    setSensitivity("none");
    setAddOpen(true);
  }

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
      setAddOpen(false);
      toast.success(t("assets.added"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm(t("assets.confirmDelete"))) return;
    try {
      await deleteAsset(id);
      toast.success(t("assets.deleted"));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
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

  async function onSync() {
    setSyncError(null);
    setSyncReport(null);
    setSyncing(true);
    try {
      const report = await syncAssets(onConflict);
      setSyncReport(report);
      await reload();
    } catch (err) {
      setSyncError(errorMessage(err));
    } finally {
      setSyncing(false);
    }
  }

  async function onPush() {
    setPushError(null);
    setPushReport(null);
    setPushing(true);
    try {
      setPushReport(await pushAssetsToNetbox());
    } catch (err) {
      setPushError(errorMessage(err));
    } finally {
      setPushing(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("assets.title")}
        subtitle={t("assets.subtitle")}
        actions={
          canWrite && (
            <Button onClick={openAdd} data-tour="add-asset" className="whitespace-nowrap">
              {t("assets.add")}
            </Button>
          )
        }
      />

      <InfoCallout>{t("inventory.assetExplain")}</InfoCallout>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {canWrite && (
      <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium text-slate-200">{t("assets.bulkImport")}</h3>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">{t("assets.bulkImportHint")}</span>
            <button
              type="button"
              onClick={() =>
                downloadAssetImportTemplate().catch((e) => toast.error(errorMessage(e)))
              }
              className="whitespace-nowrap text-xs font-medium text-emerald-400 hover:text-emerald-300"
            >
              {t("assets.downloadTemplate")}
            </button>
          </div>
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
            <option value="update">{t("assets.updateExisting")}</option>
            <option value="skip">{t("assets.skipExisting")}</option>
          </select>
          <Button type="submit" disabled={!importFile || importing}>
            {importing ? t("assets.importing") : t("assets.import")}
          </Button>
        </form>
        {importError && <p className="text-sm text-red-400">{importError}</p>}
        {importReport && (
          <div className="space-y-2 text-sm">
            <p className="text-slate-300">
              {importReport.total} {t("assets.rows")}:{" "}
              <span className="text-emerald-400">
                {importReport.created} {t("assets.created")}
              </span>
              ,{" "}
              <span className="text-sky-400">
                {importReport.updated} {t("assets.updated")}
              </span>
              ,{" "}
              <span className="text-slate-400">
                {importReport.skipped} {t("assets.skipped")}
              </span>
              ,{" "}
              <span className="text-red-400">
                {importReport.errors} {t("assets.errors")}
              </span>
            </p>
            {importReport.errors > 0 && (
              <ul className="space-y-1 text-xs text-red-400">
                {importReport.results
                  .filter((r) => r.status === "error")
                  .map((r) => (
                    <li key={r.row}>
                      {t("assets.row")} {r.row}
                      {r.ip ? ` (${r.ip})` : ""}: {r.error}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        )}

        <div className="space-y-2 border-t border-slate-800 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium text-slate-200">{t("assets.syncTitle")}</span>
            <span className="text-xs text-slate-500">{t("assets.syncHint")}</span>
          </div>
          {!netboxOn && <p className="text-xs text-amber-400">{t("assets.netboxOff")}</p>}
          <Button variant="outline" onClick={onSync} disabled={syncing || !netboxOn}>
            {syncing ? t("assets.syncing") : t("assets.syncTitle")}
          </Button>
          {syncError && <p className="text-sm text-red-400">{syncError}</p>}
          {syncReport && (
            <p className="text-sm text-slate-300">
              {syncReport.source}: {syncReport.total} {t("assets.hosts")}.{" "}
              <span className="text-emerald-400">
                {syncReport.created} {t("assets.created")}
              </span>
              ,{" "}
              <span className="text-sky-400">
                {syncReport.updated} {t("assets.updated")}
              </span>
              ,{" "}
              <span className="text-slate-400">
                {syncReport.skipped} {t("assets.skipped")}
              </span>
              ,{" "}
              <span className="text-red-400">
                {syncReport.errors} {t("assets.errors")}
              </span>
              .
            </p>
          )}

          <div className="space-y-2 border-t border-slate-800 pt-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-200">{t("assets.pushTitle")}</span>
              <span className="text-xs text-slate-500">{t("assets.pushHint")}</span>
            </div>
            <Button variant="outline" onClick={onPush} disabled={pushing || !netboxOn}>
              {pushing ? t("assets.pushing") : t("assets.pushTitle")}
            </Button>
            {pushError && <p className="text-sm text-red-400">{pushError}</p>}
            {pushReport && (
              <p className="text-sm text-slate-300">
                {pushReport.source}: {pushReport.total} {t("assets.discoveredUnit")}.{" "}
                <span className="text-emerald-400">
                  {pushReport.created} {t("assets.created")}
                </span>
                ,{" "}
                <span className="text-slate-400">
                  {pushReport.skipped} {t("assets.skipped")}
                </span>
                ,{" "}
                <span className="text-red-400">
                  {pushReport.errors} {t("assets.errors")}
                </span>
                .
              </p>
            )}
          </div>
        </div>
      </section>
      )}

      <div className="flex justify-end">
        <SearchInput value={search} onChange={setSearch} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <TableHead
            columns={columns}
            sort={sort}
            toggleSort={toggleSort}
            filters={filters}
            setFilter={onFilter}
            trailing
          />
          <tbody className="divide-y divide-slate-800">
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-slate-500" colSpan={7}>
                  {t("common.loading")}
                </td>
              </tr>
            ) : assets.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={7}>
                  {t("assets.empty")}
                  {canWrite && (
                    <>
                      {" "}
                      <button
                        onClick={openAdd}
                        className="font-medium text-emerald-400 hover:text-emerald-300"
                      >
                        {t("assets.addFirst")}
                      </button>{" "}
                      {t("assets.orImport")}
                    </>
                  )}
                </td>
              </tr>
            ) : processed.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={7}>
                  {t("common.noData")}
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
                      {t(`crit.${a.criticality}` as TKey)}
                    </span>
                  </td>
                  <td className="px-4 py-2 uppercase text-slate-400">{a.data_sensitivity}</td>
                  <td className="px-4 py-2 text-right">
                    {canWrite && (
                      <button
                        onClick={() => onDelete(a.id)}
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
      <Pagination
        page={assetsPage.page}
        pageCount={assetsPage.pageCount}
        total={assetsPage.total}
        onPage={assetsPage.setPage}
        pageSize={assetsPage.pageSize}
        onPageSize={assetsPage.setPageSize}
      />

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title={t("assets.add")}>
        <form onSubmit={onCreate} className="space-y-3">
          <FormField label={t("assets.f.ip")} hint={t("assets.f.ipHint")}>
            <input
              className={inputClass}
              placeholder="10.0.0.5"
              value={ip}
              onChange={(e) => setIp(e.target.value)}
              required
            />
          </FormField>
          <FormField label={t("assets.f.hostname")} hint={t("assets.f.hostnameHint")}>
            <input
              className={inputClass}
              placeholder="web-01"
              value={hostname}
              onChange={(e) => setHostname(e.target.value)}
            />
          </FormField>
          <FormField label={t("assets.f.vlan")} hint={t("assets.f.vlanHint")}>
            <select className={inputClass} value={vlanId} onChange={(e) => setVlanId(e.target.value)}>
              <option value="">{t("assets.f.noVlan")}</option>
              {vlans.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t("assets.f.owner")} hint={t("assets.f.ownerHint")}>
            <select className={inputClass} value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
              <option value="">{t("assets.f.noOwner")}</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t("assets.f.criticality")} hint={t("assets.f.criticalityHint")}>
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
          <FormField label={t("assets.f.sensitivity")} hint={t("assets.f.sensitivityHint")}>
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
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <Button type="submit">{t("assets.add")}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
