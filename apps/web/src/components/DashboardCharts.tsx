import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSlice, DashboardCharts as Charts } from "../api/client";
import { useI18n } from "../i18n/I18nContext";
import { useTheme } from "../theme/ThemeContext";

const AXIS = "#64748b"; // mid-gray, reads on both themes
const ACCENT = "#10b981";

// Grid lines and tooltip surface differ per theme; the vivid series colors below
// read fine on either background.
function useChartTheme() {
  const { theme } = useTheme();
  const light = theme === "light";
  return {
    grid: light ? "#e2e8f0" : "#1e293b",
    tooltip: {
      backgroundColor: light ? "#ffffff" : "#0f172a",
      border: `1px solid ${light ? "#cbd5e1" : "#334155"}`,
      borderRadius: 8,
      color: light ? "#0f172a" : "#e2e8f0",
      fontSize: 12,
    } as const,
  };
}

const CRIT_COLORS: Record<string, string> = {
  low: "#64748b",
  medium: "#0ea5e9",
  high: "#f59e0b",
  critical: "#ef4444",
};

function prettify(name: string): string {
  return name.replace(/_/g, " ");
}

function total(slices: ChartSlice[]): number {
  return slices.reduce((acc, s) => acc + s.value, 0);
}

function dayLabel(iso: string): string {
  return iso.slice(5); // MM-DD
}

function ChartCard({
  title,
  hint,
  empty,
  children,
}: {
  title: string;
  hint?: string;
  empty?: boolean;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="text-sm font-medium text-slate-300">{title}</h3>
      {hint && <p className="mt-0.5 text-xs text-slate-600">{hint}</p>}
      <div className="mt-3">
        {empty ? (
          <p className="py-12 text-center text-sm text-slate-600">{t("common.noData")}</p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

function Donut({
  data,
  colors,
}: {
  data: ChartSlice[];
  colors: Record<string, string>;
}) {
  const { tooltip } = useChartTheme();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={48}
          outerRadius={80}
          paddingAngle={2}
          stroke="none"
        >
          {data.map((s) => (
            <Cell key={s.name} fill={colors[s.name] ?? "#475569"} />
          ))}
        </Pie>
        <Tooltip contentStyle={tooltip} formatter={(v, n) => [v, prettify(String(n))]} />
        <Legend
          formatter={(value) => <span className="text-xs text-slate-400">{prettify(String(value))}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

function CountBars({ data }: { data: ChartSlice[] }) {
  const { grid, tooltip } = useChartTheme();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis
          dataKey="name"
          tickFormatter={prettify}
          tick={{ fill: AXIS, fontSize: 11 }}
          axisLine={{ stroke: grid }}
          tickLine={false}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: AXIS, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={tooltip}
          cursor={{ fill: `${grid}55` }}
          labelFormatter={(l) => prettify(String(l))}
        />
        <Bar dataKey="value" fill={ACCENT} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function DashboardCharts({ data }: { data: Charts }) {
  const { grid, tooltip } = useChartTheme();
  const { t } = useI18n();
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-200">{t("trends.title")}</h2>

      <ChartCard
        title={t("trends.changes30d")}
        hint={t("trends.changes30dHint")}
        empty={total(data.changes_by_day.map((p) => ({ name: p.date, value: p.count }))) === 0}
      >
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data.changes_by_day} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="changesFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={ACCENT} stopOpacity={0.35} />
                <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={dayLabel}
              minTickGap={24}
              tick={{ fill: AXIS, fontSize: 11 }}
              axisLine={{ stroke: grid }}
              tickLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: AXIS, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip contentStyle={tooltip} cursor={{ stroke: AXIS }} />
            <Area
              type="monotone"
              dataKey="count"
              stroke={ACCENT}
              strokeWidth={2}
              fill="url(#changesFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title={t("trends.assetsByCriticality")}
          empty={total(data.assets_by_criticality) === 0}
        >
          <Donut data={data.assets_by_criticality} colors={CRIT_COLORS} />
        </ChartCard>

        <ChartCard title={t("trends.runsByStatus")} empty={total(data.runs_by_status) === 0}>
          <CountBars data={data.runs_by_status} />
        </ChartCard>

        <ChartCard title={t("trends.changesByType")} empty={total(data.changes_by_type) === 0}>
          <CountBars data={data.changes_by_type} />
        </ChartCard>

        <ChartCard
          title={t("trends.topOpenPorts")}
          hint={t("trends.topOpenPortsHint")}
          empty={total(data.top_open_ports) === 0}
        >
          <CountBars data={data.top_open_ports} />
        </ChartCard>
      </div>
    </section>
  );
}
