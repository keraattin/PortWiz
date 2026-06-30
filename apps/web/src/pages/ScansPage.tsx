import { type FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  type Asset,
  type ComplianceFramework,
  type IpRange,
  type Observation,
  type ScanProfile,
  type ScanRun,
  type ScanRunStatus,
  type ScanType,
  type Vlan,
  createScanProfile,
  deleteScanProfile,
  fetchSettings,
  listAssets,
  listIpRanges,
  listRunObservations,
  listScanProfiles,
  listScanRuns,
  listVlans,
  runScanProfile,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import FormField from "../components/FormField";
import Modal from "../components/Modal";
import Pagination, { usePagination } from "../components/Pagination";
import { type Column, TableHead, processRows, useColumnFilters } from "../components/tableView";
import { useSort } from "../components/useSort";
import { useToast } from "../components/Toast";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong";
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

const SCAN_TYPES: ScanType[] = ["connect", "syn", "udp"];

// Friendly scan frequency, compiled to a cron expression so non-technical users
// never have to write cron. "advanced" reveals a raw cron field.
const SCHEDULES = ["off", "hourly", "sixHours", "daily", "weekly", "monthly", "advanced"] as const;
type Schedule = (typeof SCHEDULES)[number];
const SCHEDULE_CRON: Record<Exclude<Schedule, "advanced">, string> = {
  off: "",
  hourly: "0 * * * *",
  sixHours: "0 */6 * * *",
  daily: "0 2 * * *",
  weekly: "0 2 * * 1",
  monthly: "0 2 1 * *",
};

// Common port selections so users rarely need the raw "ports" syntax.
const PORT_PRESETS = ["top1000", "full", "web", "custom"] as const;
type PortPreset = (typeof PORT_PRESETS)[number];
const PRESET_PORTS: Record<Exclude<PortPreset, "custom">, string> = {
  top1000: "top-1000",
  full: "1-65535",
  web: "80,443,8080,8443",
};

// Map a raw default port spec back to a preset (or "custom" with the raw value).
function presetFor(ports: string): { preset: PortPreset; custom: string } {
  for (const p of ["top1000", "full", "web"] as const) {
    if (PRESET_PORTS[p] === ports) return { preset: p, custom: "" };
  }
  return { preset: "custom", custom: ports };
}

const STATUS_BADGE: Record<ScanRunStatus, string> = {
  pending: "bg-slate-700 text-slate-300",
  running: "bg-sky-900 text-sky-300",
  completed: "bg-emerald-900 text-emerald-300",
  partial: "bg-amber-900 text-amber-300",
  failed: "bg-red-900 text-red-300",
};

const RUN_STATUSES: ScanRunStatus[] = ["pending", "running", "completed", "partial", "failed"];

function parseTargets(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

export default function ScansPage() {
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useI18n();
  const canWrite = user?.role === "admin" || user?.role === "operator";
  const [profiles, setProfiles] = useState<ScanProfile[]>([]);
  const [runs, setRuns] = useState<ScanRun[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [vlans, setVlans] = useState<Vlan[]>([]);
  const [ranges, setRanges] = useState<IpRange[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<ScanRun | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const obsPage = usePagination(observations, 12);

  const { sort: profileSort, toggleSort: profileToggle } = useSort();
  const { filters: profileFilters, setFilter: setProfileFilter } = useColumnFilters();
  const profileColumns: Column<ScanProfile>[] = [
    { key: "name", label: t("scans.col.name"), filter: "text", get: (p) => p.name },
    {
      key: "targets",
      label: t("scans.col.targets"),
      filter: "text",
      get: (p) => p.targets.join(", "),
    },
    { key: "ports", label: t("scans.col.ports"), filter: "text", get: (p) => p.ports },
    { key: "segment", label: t("scans.col.segment"), filter: "text", get: (p) => p.segment ?? "" },
    { key: "type", label: t("scans.col.type"), filter: "text", get: (p) => p.scan_type },
  ];
  const processedProfiles = processRows(profiles, profileColumns, profileSort, profileFilters);
  const profilesPage = usePagination(processedProfiles, 15);
  const onProfileFilter = (key: string, v: string) => {
    setProfileFilter(key, v);
    profilesPage.setPage(0);
  };

  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [targets, setTargets] = useState("");
  const [portsPreset, setPortsPreset] = useState<PortPreset>("top1000");
  const [ports, setPorts] = useState("");
  const [segment, setSegment] = useState("");
  const [framework, setFramework] = useState<ComplianceFramework | "">("");
  const [schedule, setSchedule] = useState<Schedule>("off");
  const [cron, setCron] = useState("");
  const [scanType, setScanType] = useState<ScanType>("connect");
  const [serviceDetection, setServiceDetection] = useState(true);
  // Admin-configured defaults that pre-fill a new scan form.
  const [scanDefaults, setScanDefaults] = useState({
    ports: "top-1000",
    scanType: "connect" as ScanType,
    serviceDetection: true,
  });

  // The cron actually submitted: a preset, the raw field (advanced), or none.
  const effectiveCron = schedule === "advanced" ? cron.trim() : SCHEDULE_CRON[schedule];
  const effectivePorts =
    portsPreset === "custom" ? ports.trim() || "top-1000" : PRESET_PORTS[portsPreset];

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
    // Inventory powers the "add from inventory" target picker.
    Promise.all([listAssets(), listVlans(), listIpRanges()])
      .then(([a, v, r]) => {
        setAssets(a);
        setVlans(v);
        setRanges(r);
      })
      .catch(() => {
        /* picker just stays empty if inventory can't be loaded */
      });
    fetchSettings()
      .then((s) =>
        setScanDefaults({
          ports: s.default_scan_ports,
          scanType: s.default_scan_type as ScanType,
          serviceDetection: s.default_service_detection,
        }),
      )
      .catch(() => {
        /* fall back to the built-in defaults */
      });
  }, []);

  function addTarget(value: string) {
    if (!value) return;
    const sep = value.indexOf(":");
    const kind = value.slice(0, sep);
    const ref = value.slice(sep + 1);
    let toAdd: string[] = [];
    if (kind === "asset" || kind === "range") toAdd = [ref];
    else if (kind === "vlan") toAdd = ranges.filter((r) => r.vlan_id === ref).map((r) => r.cidr);
    const merged = parseTargets(targets);
    for (const item of toAdd) if (!merged.includes(item)) merged.push(item);
    setTargets(merged.join(", "));
  }

  const profileName = (id: string | null) =>
    id ? (profiles.find((p) => p.id === id)?.name ?? t("scans.deletedProfile")) : t("scans.adhoc");

  const { sort: runsSort, toggleSort: runsToggle } = useSort();
  const { filters: runsFilters, setFilter: setRunsFilter } = useColumnFilters();
  const runsColumns: Column<ScanRun>[] = [
    {
      key: "profile",
      label: t("scans.col.profile"),
      filter: "text",
      get: (r) => profileName(r.scan_profile_id),
    },
    {
      key: "status",
      label: t("scans.col.status"),
      filter: RUN_STATUSES.map((s) => ({ value: s, label: t(`runStatus.${s}` as TKey) })),
      get: (r) => r.status,
    },
    { key: "started", label: t("scans.col.started"), get: (r) => r.started_at },
    { key: "finished", label: t("scans.col.finished"), get: (r) => r.finished_at },
  ];
  const processedRuns = processRows(runs, runsColumns, runsSort, runsFilters);
  const runsPage = usePagination(processedRuns, 15);
  const onRunsFilter = (key: string, v: string) => {
    setRunsFilter(key, v);
    runsPage.setPage(0);
  };

  function openAdd() {
    setError(null);
    setName("");
    setTargets("");
    const dp = presetFor(scanDefaults.ports);
    setPortsPreset(dp.preset);
    setPorts(dp.custom);
    setSegment("");
    setFramework("");
    setSchedule("off");
    setCron("");
    setScanType(scanDefaults.scanType);
    setServiceDetection(scanDefaults.serviceDetection);
    setAddOpen(true);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createScanProfile({
        name,
        targets: parseTargets(targets),
        ports: effectivePorts,
        scan_type: scanType,
        service_detection: serviceDetection,
        segment: segment || null,
        compliance_framework: framework || null,
        cron: effectiveCron || null,
      });
      setAddOpen(false);
      toast.success(t("scans.added"));
      await reload();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function onRun(profile: ScanProfile) {
    try {
      await runScanProfile(profile.id);
      toast.success(t("scans.queued", { name: profile.name }));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function onDeleteProfile(id: string) {
    if (!window.confirm(t("scans.confirmDelete"))) return;
    try {
      await deleteScanProfile(id);
      toast.success(t("scans.deleted"));
      await reload();
    } catch (e) {
      toast.error(errorMessage(e));
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
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">{t("scans.profilesTitle")}</h2>
            <p className="text-sm text-slate-500">{t("scans.profilesSubtitle")}</p>
          </div>
          {canWrite && (
            <Button onClick={openAdd} className="whitespace-nowrap">
              {t("scans.add")}
            </Button>
          )}
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <TableHead
              columns={profileColumns}
              sort={profileSort}
              toggleSort={profileToggle}
              filters={profileFilters}
              setFilter={onProfileFilter}
              trailing
            />
            <tbody className="divide-y divide-slate-800">
              {profiles.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                    {t("scans.empty")}
                    {canWrite && (
                      <>
                        {" "}
                        <button
                          onClick={openAdd}
                          className="font-medium text-emerald-400 hover:text-emerald-300"
                        >
                          {t("scans.createFirst")}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ) : processedProfiles.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={6}>
                    {t("common.noData")}
                  </td>
                </tr>
              ) : (
                profilesPage.slice.map((p) => (
                  <tr key={p.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{p.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-300">
                      {p.targets.join(", ")}
                    </td>
                    <td className="px-4 py-2 text-slate-300">{p.ports}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {p.segment ?? <span className="text-slate-600">{t("scans.any")}</span>}
                    </td>
                    <td className="px-4 py-2 text-slate-400">{p.scan_type}</td>
                    <td className="px-4 py-2 text-right">
                      {canWrite ? (
                        <>
                          <button
                            onClick={() => onRun(p)}
                            className="mr-3 text-xs font-medium text-emerald-400 hover:text-emerald-300"
                          >
                            {t("scans.runNow")}
                          </button>
                          <button
                            onClick={() => onDeleteProfile(p.id)}
                            className="text-xs text-red-400 hover:text-red-300"
                          >
                            {t("common.delete")}
                          </button>
                        </>
                      ) : (
                        <span className="text-xs text-slate-600">{t("scans.readOnly")}</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={profilesPage.page}
          pageCount={profilesPage.pageCount}
          total={profilesPage.total}
          onPage={profilesPage.setPage}
        />
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200">{t("scans.runsTitle")}</h2>
          <button
            onClick={reload}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            {t("scans.refresh")}
          </button>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <TableHead
              columns={runsColumns}
              sort={runsSort}
              toggleSort={runsToggle}
              filters={runsFilters}
              setFilter={onRunsFilter}
              trailing
            />
            <tbody className="divide-y divide-slate-800">
              {runs.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    {t("scans.runsEmpty")}
                  </td>
                </tr>
              ) : processedRuns.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                    {t("common.noData")}
                  </td>
                </tr>
              ) : (
                runsPage.slice.map((r) => (
                  <tr key={r.id} className="bg-slate-950">
                    <td className="px-4 py-2 text-slate-100">{profileName(r.scan_profile_id)}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[r.status]}`}>
                        {t(`runStatus.${r.status}` as TKey)}
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
                        {t("scans.viewResults")}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={runsPage.page}
          pageCount={runsPage.pageCount}
          total={runsPage.total}
          onPage={runsPage.setPage}
        />
      </section>

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title={t("scans.addTitle")} wide>
        <form onSubmit={onCreate} className="space-y-3">
          <FormField label={t("scans.f.name")} hint={t("scans.f.nameHint")}>
            <input
              className={inputClass}
              placeholder="DMZ weekly"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </FormField>
          <FormField label={t("scans.f.targets")} hint={t("scans.f.targetsHint")}>
            <div className="space-y-2">
              <input
                className={inputClass}
                placeholder="10.0.0.0/24, 192.168.1.5"
                value={targets}
                onChange={(e) => setTargets(e.target.value)}
                required
              />
              {(assets.length > 0 || vlans.length > 0 || ranges.length > 0) && (
                <select
                  className={inputClass}
                  value=""
                  onChange={(e) => addTarget(e.target.value)}
                >
                  <option value="">{t("scans.f.addFromInventory")}</option>
                  {assets.length > 0 && (
                    <optgroup label={t("nav.assets")}>
                      {assets.map((a) => (
                        <option key={a.id} value={`asset:${a.ip}`}>
                          {a.ip}
                          {a.hostname ? ` (${a.hostname})` : ""}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {vlans.length > 0 && (
                    <optgroup label={t("nav.vlans")}>
                      {vlans.map((v) => (
                        <option key={v.id} value={`vlan:${v.id}`}>
                          {v.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {ranges.length > 0 && (
                    <optgroup label={t("ranges.title")}>
                      {ranges.map((r) => (
                        <option key={r.id} value={`range:${r.cidr}`}>
                          {r.cidr}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              )}
            </div>
          </FormField>
          <FormField
            label={t("scans.f.ports")}
            hint={portsPreset === "custom" ? t("scans.f.portsHint") : undefined}
          >
            <div className="space-y-2">
              <select
                className={inputClass}
                value={portsPreset}
                onChange={(e) => setPortsPreset(e.target.value as PortPreset)}
              >
                {PORT_PRESETS.map((p) => (
                  <option key={p} value={p}>
                    {t(`scans.ports.${p}` as TKey)}
                  </option>
                ))}
              </select>
              {portsPreset === "custom" && (
                <input
                  className={inputClass}
                  placeholder="top-1000"
                  value={ports}
                  onChange={(e) => setPorts(e.target.value)}
                />
              )}
            </div>
          </FormField>
          <FormField label={t("scans.f.segment")} hint={t("scans.f.segmentHint")}>
            <input
              className={inputClass}
              placeholder="vlan10"
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
            />
          </FormField>
          <FormField label={t("scans.f.framework")} hint={t("scans.f.frameworkHint")}>
            <select
              className={inputClass}
              value={framework}
              onChange={(e) => setFramework(e.target.value as ComplianceFramework | "")}
            >
              <option value="">{t("scans.f.noFramework")}</option>
              <option value="pci">PCI-DSS</option>
              <option value="hipaa">HIPAA</option>
              <option value="soc2">SOC 2</option>
              <option value="iso27001">ISO 27001</option>
              <option value="nist">NIST</option>
            </select>
          </FormField>
          <FormField label={t("scans.f.schedule")} hint={t("scans.f.scheduleHint")}>
            <select
              className={inputClass}
              value={schedule}
              onChange={(e) => setSchedule(e.target.value as Schedule)}
            >
              {SCHEDULES.map((s) => (
                <option key={s} value={s}>
                  {t(`scans.schedule.${s}` as TKey)}
                </option>
              ))}
            </select>
          </FormField>
          {schedule === "advanced" && (
            <FormField label={t("scans.f.cron")} hint={t("scans.f.cronHint")}>
              <input
                className={inputClass}
                placeholder="0 2 * * *"
                value={cron}
                onChange={(e) => setCron(e.target.value)}
              />
            </FormField>
          )}
          <FormField label={t("scans.f.scanType")} hint={t("scans.f.scanTypeHint")}>
            <select
              className={inputClass}
              value={scanType}
              onChange={(e) => setScanType(e.target.value as ScanType)}
            >
              {SCAN_TYPES.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </FormField>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={serviceDetection}
              onChange={(e) => setServiceDetection(e.target.checked)}
            />
            {t("scans.f.serviceDetection")}
          </label>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end">
            <Button type="submit">{t("scans.addTitle")}</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={selectedRun !== null}
        onClose={() => setSelectedRun(null)}
        title={
          selectedRun
            ? t("scans.resultsTitle", {
                id: selectedRun.id.slice(0, 8),
                count: observations.length,
              })
            : ""
        }
        wide
      >
        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">{t("scans.col.host")}</th>
                <th className="px-4 py-2 font-medium">{t("scans.col.port")}</th>
                <th className="px-4 py-2 font-medium">{t("scans.col.state")}</th>
                <th className="px-4 py-2 font-medium">{t("scans.col.service")}</th>
                <th className="px-4 py-2 font-medium">{t("scans.col.version")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {observations.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-slate-500" colSpan={5}>
                    {t("scans.noOpenPorts")}
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
