import { type FormEvent, useEffect, useState } from "react";
import {
  type IpRange,
  type IpRangePreviewItem,
  type IpRangeSyncReport,
  type Vlan,
  type VlanImportPreviewRow,
  type VlanImportReport,
  type VlanPreviewItem,
  type VlanSyncReport,
  applyIpRangeSync,
  applyVlanImport,
  applyVlanSync,
  bulkDeleteIpRanges,
  bulkDeleteVlans,
  bulkUpdateIpRanges,
  bulkUpdateVlans,
  createIpRange,
  createVlan,
  deleteIpRange,
  deleteVlan,
  downloadVlanImportTemplate,
  fetchSettings,
  listIpRanges,
  listVlans,
  previewIpRangeSync,
  previewVlanImport,
  previewVlanSync,
  updateVlan,
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
import SyncStagingModal from "../components/SyncStagingModal";
import { CHECKBOX_CLS, useTableSelection } from "../components/tableView";
import { useToast } from "../components/Toast";
import { useI18n } from "../i18n/I18nContext";

// Comma-separated tag text <-> string list.
const parseTags = (s: string): string[] =>
  s.split(",").map((t) => t.trim()).filter(Boolean);

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
  // VLANs and ranges are selected independently for bulk delete (different keys:
  // VLAN by name, range by CIDR).
  const vlanSel = useTableSelection();
  const rangeSel = useTableSelection();
  // Bulk-edit modal (empty field = leave unchanged).
  const [bulkEditOpen, setBulkEditOpen] = useState(false);
  const [bulkVlanDesc, setBulkVlanDesc] = useState("");
  const [bulkRangeVlan, setBulkRangeVlan] = useState("");
  const [bulkRangeDesc, setBulkRangeDesc] = useState("");

  const [vlanOpen, setVlanOpen] = useState(false);
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [description, setDescription] = useState("");
  const [tagsText, setTagsText] = useState("");
  // Per-VLAN edit modal: when set, the modal edits this VLAN instead of adding.
  const [editVlanId, setEditVlanId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editTag, setEditTag] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editTagsText, setEditTagsText] = useState("");
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
  // VLAN file-import staging.
  const [importStagingOpen, setImportStagingOpen] = useState(false);
  const [importPreview, setImportPreview] = useState<VlanImportPreviewRow[]>([]);
  const importPreviewSel = useTableSelection();
  const [importApplying, setImportApplying] = useState(false);
  const [importing, setImporting] = useState(false);

  const [syncReport, setSyncReport] = useState<VlanSyncReport | null>(null);
  const [rangeSyncReport, setRangeSyncReport] = useState<IpRangeSyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  // NetBox sync staging (preview then apply a chosen subset).
  const [vlanStagingOpen, setVlanStagingOpen] = useState(false);
  const [vlanPreview, setVlanPreview] = useState<VlanPreviewItem[]>([]);
  const [vlanStagingLoading, setVlanStagingLoading] = useState(false);
  const [vlanApplying, setVlanApplying] = useState(false);
  const vlanPreviewSel = useTableSelection();
  const [rangeStagingOpen, setRangeStagingOpen] = useState(false);
  const [rangePreview, setRangePreview] = useState<IpRangePreviewItem[]>([]);
  const [rangeStagingLoading, setRangeStagingLoading] = useState(false);
  const [rangeApplying, setRangeApplying] = useState(false);
  const rangePreviewSel = useTableSelection();
  const [netboxOn, setNetboxOn] = useState(false);
  // VLAN import can be disabled in Settings while NetBox stays connected.
  const [vlanImportOn, setVlanImportOn] = useState(false);

  async function openVlanStaging() {
    setSyncError(null);
    setSyncReport(null);
    vlanPreviewSel.clear();
    setVlanPreview([]);
    setVlanStagingLoading(true);
    setVlanStagingOpen(true);
    try {
      const items = await previewVlanSync();
      setVlanPreview(items);
      vlanPreviewSel.setMany(
        items.filter((v) => !v.exists).map((v) => v.name),
        true,
      );
    } catch (err) {
      setSyncError(errorMessage(err));
      setVlanStagingOpen(false);
    } finally {
      setVlanStagingLoading(false);
    }
  }

  async function onApplyVlanStaging() {
    const items = vlanPreview
      .filter((v) => vlanPreviewSel.selected.has(v.name))
      .map((v) => ({ name: v.name, vlan_tag: v.vlan_tag, description: v.description }));
    if (items.length === 0) return;
    setVlanApplying(true);
    try {
      setSyncReport(await applyVlanSync(items, onConflict));
      setVlanStagingOpen(false);
      vlanPreviewSel.clear();
      await reload();
    } catch (err) {
      setSyncError(errorMessage(err));
    } finally {
      setVlanApplying(false);
    }
  }

  async function openRangeStaging() {
    setSyncError(null);
    setRangeSyncReport(null);
    rangePreviewSel.clear();
    setRangePreview([]);
    setRangeStagingLoading(true);
    setRangeStagingOpen(true);
    try {
      const items = await previewIpRangeSync();
      setRangePreview(items);
      rangePreviewSel.setMany(
        items.filter((r) => !r.exists).map((r) => r.cidr),
        true,
      );
    } catch (err) {
      setSyncError(errorMessage(err));
      setRangeStagingOpen(false);
    } finally {
      setRangeStagingLoading(false);
    }
  }

  async function onApplyRangeStaging() {
    const items = rangePreview
      .filter((r) => rangePreviewSel.selected.has(r.cidr))
      .map((r) => ({ cidr: r.cidr, vlan_name: r.vlan_name, description: r.description }));
    if (items.length === 0) return;
    setRangeApplying(true);
    try {
      setRangeSyncReport(await applyIpRangeSync(items, onConflict));
      setRangeStagingOpen(false);
      rangePreviewSel.clear();
      await reload();
    } catch (err) {
      setSyncError(errorMessage(err));
    } finally {
      setRangeApplying(false);
    }
  }

  async function onImport(e: FormEvent) {
    e.preventDefault();
    if (!importFile) return;
    setImportError(null);
    setImportReport(null);
    importPreviewSel.clear();
    setImportPreview([]);
    setImporting(true);
    setImportStagingOpen(true);
    try {
      const rows = await previewVlanImport(importFile);
      setImportPreview(rows);
      importPreviewSel.setMany(
        rows.filter((r) => !r.error && r.name).map((r) => String(r.row)),
        true,
      );
    } catch (err) {
      setImportError(errorMessage(err));
      setImportStagingOpen(false);
    } finally {
      setImporting(false);
    }
  }

  async function onApplyImport() {
    const items = importPreview
      .filter((r) => importPreviewSel.selected.has(String(r.row)) && r.name)
      .map((r) => ({
        name: r.name as string,
        vlan_tag: r.vlan_tag,
        description: r.description,
        cidr: r.cidr,
      }));
    if (items.length === 0) return;
    setImportApplying(true);
    try {
      setImportReport(await applyVlanImport(items, onConflict));
      setImportStagingOpen(false);
      importPreviewSel.clear();
      await reload();
    } catch (err) {
      setImportError(errorMessage(err));
    } finally {
      setImportApplying(false);
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
    setTagsText("");
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
        tags: parseTags(tagsText),
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

  function openEditVlan(v: Vlan) {
    setError(null);
    setEditVlanId(v.id);
    setEditName(v.name);
    setEditTag(v.vlan_tag != null ? String(v.vlan_tag) : "");
    setEditDesc(v.description ?? "");
    setEditTagsText((v.tags ?? []).join(", "));
  }

  async function onEditVlan(e: FormEvent) {
    e.preventDefault();
    if (!editVlanId) return;
    setError(null);
    try {
      await updateVlan(editVlanId, {
        name: editName,
        vlan_tag: editTag ? Number(editTag) : null,
        description: editDesc || null,
        tags: parseTags(editTagsText),
      });
      setEditVlanId(null);
      toast.success(t("vlans.updated"));
      await reload();
    } catch (err) {
      setError(errorMessage(err));
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

  const selectedCount = vlanSel.selected.size + rangeSel.selected.size;

  // "Select all" spans every VLAN and range currently visible (across pages of
  // the filtered set), populating both independent selection sets at once.
  const visibleRangeIds = [
    ...filteredVlans.flatMap((v) => (rangesByVlan[v.id] ?? []).map((r) => r.id)),
    ...unassignedRanges.map((r) => r.id),
  ];
  const allSelectable = filteredVlans.length + visibleRangeIds.length;
  const allSelected =
    allSelectable > 0 &&
    filteredVlans.every((v) => vlanSel.selected.has(v.id)) &&
    visibleRangeIds.every((id) => rangeSel.selected.has(id));

  function selectAll(on: boolean) {
    vlanSel.setMany(
      filteredVlans.map((v) => v.id),
      on,
    );
    rangeSel.setMany(visibleRangeIds, on);
  }

  async function onBulkDelete() {
    const names = vlans.filter((v) => vlanSel.selected.has(v.id)).map((v) => v.name);
    const cidrs = ipRanges.filter((r) => rangeSel.selected.has(r.id)).map((r) => r.cidr);
    if (names.length + cidrs.length === 0) return;
    if (!window.confirm(t("table.confirmBulkDelete", { count: names.length + cidrs.length })))
      return;
    try {
      let deleted = 0;
      if (names.length) deleted += (await bulkDeleteVlans(names)).succeeded;
      if (cidrs.length) deleted += (await bulkDeleteIpRanges(cidrs)).succeeded;
      toast.success(t("table.bulkDeleteDone", { count: deleted }));
      vlanSel.clear();
      rangeSel.clear();
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  function openBulkEdit() {
    setBulkVlanDesc("");
    setBulkRangeVlan("");
    setBulkRangeDesc("");
    setBulkEditOpen(true);
  }

  async function onBulkEdit(e: FormEvent) {
    e.preventDefault();
    const vlanIds = vlans.filter((v) => vlanSel.selected.has(v.id)).map((v) => v.id);
    const rangeIds = ipRanges.filter((r) => rangeSel.selected.has(r.id)).map((r) => r.id);
    const rangeFields: { vlan_id?: string; description?: string } = {};
    if (bulkRangeVlan) rangeFields.vlan_id = bulkRangeVlan;
    if (bulkRangeDesc) rangeFields.description = bulkRangeDesc;
    try {
      let done = 0;
      if (vlanIds.length && bulkVlanDesc) {
        done += (await bulkUpdateVlans(vlanIds, { description: bulkVlanDesc })).succeeded;
      }
      if (rangeIds.length && Object.keys(rangeFields).length) {
        done += (await bulkUpdateIpRanges(rangeIds, rangeFields)).succeeded;
      }
      toast.success(t("table.bulkUpdateDone", { count: done }));
      setBulkEditOpen(false);
      vlanSel.clear();
      rangeSel.clear();
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  const rangeRow = (r: IpRange) => (
    <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-2">
      {canWrite && (
        <input
          type="checkbox"
          className={CHECKBOX_CLS}
          checked={rangeSel.selected.has(r.id)}
          onChange={() => rangeSel.toggle(r.id)}
        />
      )}
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
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={openVlanStaging}
                disabled={vlanStagingLoading || !netboxOn || !vlanImportOn}
              >
                {vlanStagingLoading ? t("vlans.syncing") : t("vlans.syncTitle")}
              </Button>
              <Button
                variant="outline"
                onClick={openRangeStaging}
                disabled={rangeStagingLoading || !netboxOn || !vlanImportOn}
              >
                {rangeStagingLoading ? t("vlans.syncing") : t("ranges.syncTitle")}
              </Button>
            </div>
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
            {rangeSyncReport && (
              <p className="text-sm text-slate-300">
                {rangeSyncReport.source}: {rangeSyncReport.total} {t("ranges.title")}.{" "}
                <span className="text-emerald-400">
                  {rangeSyncReport.created} {t("assets.created")}
                </span>
                ,{" "}
                <span className="text-sky-400">
                  {rangeSyncReport.updated} {t("assets.updated")}
                </span>
                ,{" "}
                <span className="text-slate-400">
                  {rangeSyncReport.skipped} {t("assets.skipped")}
                </span>
                ,{" "}
                <span className="text-red-400">
                  {rangeSyncReport.errors} {t("assets.errors")}
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
            <div className="flex flex-wrap items-center gap-3">
              <SearchInput value={search} onChange={setSearch} />
              {canWrite && allSelectable > 0 && (
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    className={CHECKBOX_CLS}
                    checked={allSelected}
                    onChange={(e) => selectAll(e.target.checked)}
                  />
                  {t("table.selectAll")}
                </label>
              )}
              {canWrite && selectedCount > 0 && (
                <>
                  <span className="text-sm text-slate-300">
                    {t("table.selected", { count: selectedCount })}
                  </span>
                  <button
                    onClick={openBulkEdit}
                    className="rounded-md bg-sky-900/50 px-3 py-1 text-xs font-medium text-sky-300 hover:bg-sky-900"
                  >
                    {t("table.editSelected")}
                  </button>
                  <button
                    onClick={onBulkDelete}
                    className="rounded-md bg-red-900/60 px-3 py-1 text-xs font-medium text-red-300 hover:bg-red-900"
                  >
                    {t("table.deleteSelected")}
                  </button>
                  <button
                    onClick={() => {
                      vlanSel.clear();
                      rangeSel.clear();
                    }}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    {t("table.clear")}
                  </button>
                </>
              )}
            </div>
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
                      {canWrite && (
                        <input
                          type="checkbox"
                          className={CHECKBOX_CLS}
                          checked={vlanSel.selected.has(v.id)}
                          onChange={() => vlanSel.toggle(v.id)}
                        />
                      )}
                      {canWrite ? (
                        <button
                          onClick={() => openEditVlan(v)}
                          className="font-medium text-slate-100 hover:text-emerald-300"
                          title={t("common.edit")}
                        >
                          {v.name}
                        </button>
                      ) : (
                        <span className="font-medium text-slate-100">{v.name}</span>
                      )}
                      {v.vlan_tag != null && (
                        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                          {t("vlans.col.tag")} {v.vlan_tag}
                        </span>
                      )}
                      {v.description && (
                        <span className="text-sm text-slate-500">{v.description}</span>
                      )}
                      {v.tags?.map((tg) => (
                        <span
                          key={tg}
                          className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400"
                        >
                          {tg}
                        </span>
                      ))}
                      {canWrite && (
                        <div className="ml-auto flex items-center gap-3">
                          <button
                            onClick={() => openEditVlan(v)}
                            className="text-xs text-sky-400 hover:text-sky-300"
                          >
                            {t("common.edit")}
                          </button>
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
          <FormField label={t("tags.label")} hint={t("tags.hint")}>
            <input
              className={inputClass}
              placeholder="prod, dmz"
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
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

      <Modal
        open={editVlanId !== null}
        onClose={() => setEditVlanId(null)}
        title={t("vlans.editTitle")}
      >
        <form onSubmit={onEditVlan} className="space-y-3">
          <FormField label={t("vlans.f.name")} hint={t("vlans.f.nameHint")}>
            <input
              className={inputClass}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              required
            />
          </FormField>
          <FormField label={t("vlans.f.tag")} hint={t("vlans.f.tagHint")}>
            <input
              className={inputClass}
              type="number"
              min={1}
              max={4094}
              value={editTag}
              onChange={(e) => setEditTag(e.target.value)}
            />
          </FormField>
          <FormField label={t("vlans.f.description")} hint={t("vlans.f.descriptionHint")}>
            <input
              className={inputClass}
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
            />
          </FormField>
          <FormField label={t("tags.label")} hint={t("tags.hint")}>
            <input
              className={inputClass}
              placeholder="prod, dmz"
              value={editTagsText}
              onChange={(e) => setEditTagsText(e.target.value)}
            />
          </FormField>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <Button type="submit">{t("common.save")}</Button>
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

      <Modal
        open={bulkEditOpen}
        onClose={() => setBulkEditOpen(false)}
        title={t("table.bulkEditTitle", { count: selectedCount })}
      >
        <form onSubmit={onBulkEdit} className="space-y-4">
          {vlanSel.selected.size > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-200">
                {t("vlans.title")} ({vlanSel.selected.size})
              </p>
              <FormField label={t("vlans.f.description")}>
                <input
                  className={inputClass}
                  placeholder={t("table.keepUnchanged")}
                  value={bulkVlanDesc}
                  onChange={(e) => setBulkVlanDesc(e.target.value)}
                />
              </FormField>
            </div>
          )}
          {rangeSel.selected.size > 0 && (
            <div className="space-y-2 border-t border-slate-800 pt-3">
              <p className="text-sm font-medium text-slate-200">
                {t("ranges.title")} ({rangeSel.selected.size})
              </p>
              <FormField label={t("ranges.f.vlan")}>
                <select
                  className={inputClass}
                  value={bulkRangeVlan}
                  onChange={(e) => setBulkRangeVlan(e.target.value)}
                >
                  <option value="">{t("table.keepUnchanged")}</option>
                  {vlans.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField label={t("ranges.f.description")}>
                <input
                  className={inputClass}
                  placeholder={t("table.keepUnchanged")}
                  value={bulkRangeDesc}
                  onChange={(e) => setBulkRangeDesc(e.target.value)}
                />
              </FormField>
            </div>
          )}
          <div className="flex justify-end">
            <Button type="submit">{t("table.apply")}</Button>
          </div>
        </form>
      </Modal>

      <SyncStagingModal
        open={vlanStagingOpen}
        onClose={() => setVlanStagingOpen(false)}
        title={t("vlans.syncStagingTitle")}
        loading={vlanStagingLoading}
        items={vlanPreview}
        rowKey={(v) => v.name}
        isExisting={(v) => v.exists}
        columns={[
          { key: "name", label: t("vlans.col.name"), get: (v) => v.name },
          { key: "tag", label: t("vlans.col.tag"), get: (v) => v.vlan_tag ?? "-" },
          { key: "description", label: t("vlans.col.description"), get: (v) => v.description ?? "-" },
        ]}
        selected={vlanPreviewSel.selected}
        onToggle={vlanPreviewSel.toggle}
        onToggleAll={(on) =>
          vlanPreviewSel.setMany(
            vlanPreview.map((v) => v.name),
            on,
          )
        }
        applying={vlanApplying}
        onApply={onApplyVlanStaging}
      />

      <SyncStagingModal
        open={rangeStagingOpen}
        onClose={() => setRangeStagingOpen(false)}
        title={t("ranges.syncStagingTitle")}
        loading={rangeStagingLoading}
        items={rangePreview}
        rowKey={(r) => r.cidr}
        isExisting={(r) => r.exists}
        columns={[
          { key: "cidr", label: t("ranges.col.cidr"), get: (r) => r.cidr },
          { key: "vlan", label: t("ranges.col.vlan"), get: (r) => r.vlan_name ?? "-" },
          { key: "description", label: t("ranges.col.description"), get: (r) => r.description ?? "-" },
        ]}
        selected={rangePreviewSel.selected}
        onToggle={rangePreviewSel.toggle}
        onToggleAll={(on) =>
          rangePreviewSel.setMany(
            rangePreview.map((r) => r.cidr),
            on,
          )
        }
        applying={rangeApplying}
        onApply={onApplyRangeStaging}
      />

      <SyncStagingModal
        open={importStagingOpen}
        onClose={() => setImportStagingOpen(false)}
        title={t("vlans.importStagingTitle")}
        loading={importing}
        items={importPreview}
        rowKey={(r) => String(r.row)}
        isExisting={(r) => r.exists}
        columns={[
          {
            key: "name",
            label: t("vlans.col.name"),
            get: (r) =>
              r.error ? <span className="text-red-400">{r.error}</span> : (r.name ?? "-"),
          },
          { key: "tag", label: t("vlans.col.tag"), get: (r) => r.vlan_tag ?? "-" },
          { key: "cidr", label: t("ranges.col.cidr"), get: (r) => r.cidr ?? "-" },
          {
            key: "description",
            label: t("vlans.col.description"),
            get: (r) => r.description ?? "-",
          },
        ]}
        selected={importPreviewSel.selected}
        onToggle={importPreviewSel.toggle}
        onToggleAll={(on) =>
          importPreviewSel.setMany(
            importPreview.map((r) => String(r.row)),
            on,
          )
        }
        applying={importApplying}
        onApply={onApplyImport}
      />
    </div>
  );
}
