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
import EmptyState from "../components/EmptyState";
import FormField from "../components/FormField";
import InfoCallout from "../components/InfoCallout";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Pagination, { usePagination } from "../components/Pagination";
import SearchInput from "../components/SearchInput";
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
  const [search, setSearch] = useState("");

  const [vlanOpen, setVlanOpen] = useState(false);
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [description, setDescription] = useState("");
  // Ranges entered alongside the VLAN, so a VLAN and its ranges are created in
  // one flow (they are treated as one unit throughout the page).
  const [vlanRanges, setVlanRanges] = useState("");

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
  // VLAN import can be disabled in Settings while NetBox stays connected.
  const [vlanImportOn, setVlanImportOn] = useState(false);

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
      .then((s) => {
        setNetboxOn(s.netbox_configured);
        setVlanImportOn(s.netbox_import_vlans);
      })
      .catch(() => {
        /* leave NetBox sync disabled if status can't be read */
      });
  }, []);

  // Group ranges under their VLAN so each VLAN is shown with its ranges; ranges
  // without a VLAN get their own section.
  const rangesByVlan: Record<string, IpRange[]> = {};
  for (const r of ipRanges) {
    if (r.vlan_id) (rangesByVlan[r.vlan_id] ??= []).push(r);
  }
  const unassignedRanges = ipRanges.filter((r) => !r.vlan_id);

  const q = search.trim().toLowerCase();
  const filteredVlans = vlans.filter(
    (v) => !q || v.name.toLowerCase().includes(q) || (v.description ?? "").toLowerCase().includes(q),
  );
  const vlansPage = usePagination(filteredVlans, 10);

  function openAddVlan() {
    setError(null);
    setName("");
    setTag("");
    setDescription("");
    setVlanRanges("");
    setVlanOpen(true);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const vlan = await createVlan({
        name,
        vlan_tag: tag ? Number(tag) : null,
        description: description || null,
      });
      // Attach any ranges entered in the same form to the new VLAN.
      const cidrs = vlanRanges
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const failed: string[] = [];
      for (const c of cidrs) {
        try {
          await createIpRange({ cidr: c, vlan_id: vlan.id, description: null });
        } catch {
          failed.push(c);
        }
      }
      setVlanOpen(false);
      await reload();
      if (failed.length) {
        toast.error(t("vlans.rangesFailed", { cidrs: failed.join(", ") }));
      } else {
        toast.success(t("vlans.added"));
      }
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

  function openAddRange(vlanId = "") {
    setError(null);
    setCidr("");
    setRangeVlanId(vlanId);
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

  const rangeRow = (r: IpRange) => (
    <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-2">
      <span className="font-mono text-sm text-slate-200">{r.cidr}</span>
      {r.description && <span className="text-xs text-slate-500">{r.description}</span>}
      {canWrite && (
        <button
          onClick={() => onDeleteRange(r.id)}
          className="ml-auto text-xs text-red-400 hover:text-red-300"
        >
          {t("common.delete")}
        </button>
      )}
    </li>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("vlans.title")}
        subtitle={t("vlans.subtitle")}
        docsGuide="scanning"
        actions={
          canWrite && (
            <Button onClick={openAddVlan} data-tour="add-vlan" className="whitespace-nowrap">
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
              {(importReport.ranges_created > 0 || importReport.ranges_skipped > 0) && (
                <p className="text-slate-300">
                  <span className="text-emerald-400">
                    {importReport.ranges_created} {t("vlans.rangesAdded")}
                  </span>
                  ,{" "}
                  <span className="text-slate-400">
                    {importReport.ranges_skipped} {t("assets.skipped")}
                  </span>
                </p>
              )}
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
            {netboxOn && !vlanImportOn && (
              <p className="text-xs text-amber-400">{t("vlans.importOff")}</p>
            )}
            <Button
              variant="outline"
              onClick={onSync}
              disabled={syncing || !netboxOn || !vlanImportOn}
            >
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

      {!loading && vlans.length === 0 ? (
        <EmptyState
          icon="🌐"
          title={t("vlans.empty")}
          body={t("vlans.emptyBody")}
          action={canWrite && <Button onClick={openAddVlan}>{t("vlans.add")}</Button>}
        />
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SearchInput value={search} onChange={setSearch} />
            {canWrite && (
              <Button variant="outline" onClick={() => openAddRange()} className="whitespace-nowrap">
                {t("ranges.add")}
              </Button>
            )}
          </div>

          {loading ? (
            <p className="py-6 text-center text-sm text-slate-500">{t("common.loading")}</p>
          ) : filteredVlans.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">{t("common.noData")}</p>
          ) : (
            <>
              {vlansPage.slice.map((v) => {
                const ranges = rangesByVlan[v.id] ?? [];
                return (
                  <div key={v.id} className="rounded-xl border border-slate-800 bg-slate-900">
                    <div className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <span className="font-medium text-slate-100">{v.name}</span>
                      {v.vlan_tag != null && (
                        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                          {t("vlans.col.tag")} {v.vlan_tag}
                        </span>
                      )}
                      {v.description && (
                        <span className="text-sm text-slate-500">{v.description}</span>
                      )}
                      {canWrite && (
                        <div className="ml-auto flex items-center gap-3">
                          <button
                            onClick={() => openAddRange(v.id)}
                            className="text-xs text-emerald-400 hover:text-emerald-300"
                          >
                            {t("vlans.addRange")}
                          </button>
                          <button
                            onClick={() => onDelete(v.id)}
                            className="text-xs text-red-400 hover:text-red-300"
                          >
                            {t("common.delete")}
                          </button>
                        </div>
                      )}
                    </div>
                    <ul className="divide-y divide-slate-800/60 border-t border-slate-800">
                      {ranges.length === 0 ? (
                        <li className="px-4 py-2 text-xs text-slate-600">{t("vlans.noRanges")}</li>
                      ) : (
                        ranges.map(rangeRow)
                      )}
                    </ul>
                  </div>
                );
              })}
              <Pagination
                page={vlansPage.page}
                pageCount={vlansPage.pageCount}
                total={vlansPage.total}
                onPage={vlansPage.setPage}
                pageSize={vlansPage.pageSize}
                onPageSize={vlansPage.setPageSize}
              />
            </>
          )}

          {unassignedRanges.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900">
              <div className="px-4 py-3 text-sm font-medium text-slate-300">
                {t("ranges.unassigned")}
              </div>
              <ul className="divide-y divide-slate-800/60 border-t border-slate-800">
                {unassignedRanges.map(rangeRow)}
              </ul>
            </div>
          )}
        </div>
      )}

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
          <FormField label={t("vlans.f.ranges")} hint={t("vlans.f.rangesHint")}>
            <textarea
              className={inputClass}
              rows={2}
              placeholder="10.0.0.0/24, 10.0.1.0/24"
              value={vlanRanges}
              onChange={(e) => setVlanRanges(e.target.value)}
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
