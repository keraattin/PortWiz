import { type FormEvent, useEffect, useState } from "react";
import {
  type IpRange,
  type Vlan,
  type VlanImportReport,
  type VlanSyncReport,
  createIpRange,
  createVlan,
  deleteIpRange,
  deleteVlan,
  downloadVlanImportTemplate,
  fetchSettings,
  importVlans,
  listIpRanges,
  listVlans,
  syncVlans,
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
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nContext";

export default function VlansPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const errorMessage = useErrorMessage();
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

  const [importFile, setImportFile] = useState<File | null>(null);
  const [onConflict, setOnConflict] = useState<"update" | "skip">("update");
  const [importReport, setImportReport] = useState<VlanImportReport | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const [syncReport, setSyncReport] = useState<VlanSyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [netboxOn, setNetboxOn] = useState(false);

  const { sort: vlanSort, toggleSort: vlanToggle } = useSort();
  const { sort: rangeSort, toggleSort: rangeToggle } = useSort();
  const { filters: vlanFilters, setFilter: setVlanFilter } = useColumnFilters();
  const { filters: rangeFilters, setFilter: setRangeFilter } = useColumnFilters();

  async function onSync() {
    setSyncError(null);
    setSyncReport(null);
    setSyncing(true);
    try {
      setSyncReport(await syncVlans(onConflict));
      await reload();
    } catch (err) {
      setSyncError(errorMessage(err));
    } finally {
      setSyncing(false);
    }
  }

  async function onImport(e: FormEvent) {
    e.preventDefault();
    if (!importFile) return;
    setImportError(null);
    setImportReport(null);
    setImporting(true);
    try {
      const report = await importVlans(importFile, onConflict);
      setImportReport(report);
      await reload();
    } catch (err) {
      setImportError(errorMessage(err));
    } finally {
      setImporting(false);
    }
  }

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
    fetchSettings()
      .then((s) => setNetboxOn(s.netbox_configured))
      .catch(() => {
        /* leave NetBox sync disabled if status can't be read */
      });
  }, []);

  const vlanName = (id: string | null) =>
    id ? (vlans.find((v) => v.id === id)?.name ?? "-") : "-";

  const vlanColumns: Column<Vlan>[] = [
    { key: "name", label: t("vlans.col.name"), filter: "text", get: (v) => v.name },
    { key: "tag", label: t("vlans.col.tag"), filter: "text", get: (v) => v.vlan_tag },
    {
      key: "description",
      label: t("vlans.col.description"),
      filter: "text",
      get: (v) => v.description ?? "",
    },
  ];
  const vlanRows = processRows(vlans, vlanColumns, vlanSort, vlanFilters);
  const vlansPage = usePagination(vlanRows, 15);
  const onVlanFilter = (key: string, val: string) => {
    setVlanFilter(key, val);
    vlansPage.setPage(0);
  };

  const rangeColumns: Column<IpRange>[] = [
    { key: "cidr", label: t("ranges.col.cidr"), filter: "text", get: (r) => r.cidr },
    { key: "vlan", label: t("ranges.col.vlan"), filter: "text", get: (r) => vlanName(r.vlan_id) },
    {
      key: "description",
      label: t("ranges.col.description"),
      filter: "text",
      get: (r) => r.description ?? "",
    },
  ];
  const rangeRows = processRows(ipRanges, rangeColumns, rangeSort, rangeFilters);
  const rangesPage = usePagination(rangeRows, 15);
  const onRangeFilter = (key: string, val: string) => {
    setRangeFilter(key, val);
    rangesPage.setPage(0);
  };

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
      <PageHeader
        title={t("vlans.title")}
        subtitle={t("vlans.subtitle")}
        actions={
          canWrite && (
            <Button onClick={openAddVlan} className="whitespace-nowrap">
              {t("vlans.add")}
            </Button>
          )
        }
      />

      <InfoCallout>{t("inventory.vlanExplain")}</InfoCallout>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {canWrite && (
        <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-medium text-slate-200">{t("vlans.bulkImport")}</h3>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">{t("vlans.bulkImportHint")}</span>
              <button
                type="button"
                onClick={() =>
                  downloadVlanImportTemplate().catch((e) => toast.error(errorMessage(e)))
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
                        {r.name ? ` (${r.name})` : ""}: {r.error}
                      </li>
                    ))}
                </ul>
              )}
            </div>
          )}

          <div className="space-y-2 border-t border-slate-800 pt-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-200">{t("vlans.syncTitle")}</span>
              <span className="text-xs text-slate-500">{t("vlans.syncHint")}</span>
            </div>
            {!netboxOn && <p className="text-xs text-amber-400">{t("assets.netboxOff")}</p>}
            <Button variant="outline" onClick={onSync} disabled={syncing || !netboxOn}>
              {syncing ? t("vlans.syncing") : t("vlans.syncTitle")}
            </Button>
            {syncError && <p className="text-sm text-red-400">{syncError}</p>}
            {syncReport && (
              <p className="text-sm text-slate-300">
                {syncReport.source}: {syncReport.total} {t("vlans.unit")}.{" "}
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
          </div>
        </section>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <TableHead
            columns={vlanColumns}
            sort={vlanSort}
            toggleSort={vlanToggle}
            filters={vlanFilters}
            setFilter={onVlanFilter}
            trailing
          />
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
            ) : vlanRows.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                  {t("common.noData")}
                </td>
              </tr>
            ) : (
              vlansPage.slice.map((v) => (
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
      <Pagination
        page={vlansPage.page}
        pageCount={vlansPage.pageCount}
        total={vlansPage.total}
        onPage={vlansPage.setPage}
        pageSize={vlansPage.pageSize}
        onPageSize={vlansPage.setPageSize}
      />

      <div className="flex items-start justify-between gap-3 pt-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">{t("ranges.title")}</h2>
          <p className="text-sm text-slate-500">{t("ranges.subtitle")}</p>
        </div>
        {canWrite && (
          <Button onClick={openAddRange} className="whitespace-nowrap">
            {t("ranges.add")}
          </Button>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <TableHead
            columns={rangeColumns}
            sort={rangeSort}
            toggleSort={rangeToggle}
            filters={rangeFilters}
            setFilter={onRangeFilter}
            trailing
          />
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
            ) : rangeRows.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                  {t("common.noData")}
                </td>
              </tr>
            ) : (
              rangesPage.slice.map((r) => (
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
      <Pagination
        page={rangesPage.page}
        pageCount={rangesPage.pageCount}
        total={rangesPage.total}
        onPage={rangesPage.setPage}
        pageSize={rangesPage.pageSize}
        onPageSize={rangesPage.setPageSize}
      />

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
            <Button type="submit">{t("vlans.add")}</Button>
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
            <Button type="submit">{t("ranges.add")}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
