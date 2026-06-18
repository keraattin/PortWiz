import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

// What each role can do, summarized from the app's RBAC. "manage" = read+write,
// "view" = read-only, "none" = no access.
type Level = "manage" | "view" | "none";

const ROWS: { key: TKey; admin: Level; operator: Level; auditor: Level }[] = [
  { key: "roleMatrix.row.operate", admin: "manage", operator: "manage", auditor: "view" },
  { key: "roleMatrix.row.compliance", admin: "view", operator: "view", auditor: "view" },
  { key: "roleMatrix.row.agents", admin: "manage", operator: "none", auditor: "view" },
  { key: "roleMatrix.row.adminArea", admin: "manage", operator: "none", auditor: "view" },
];

function Cell({ level }: { level: Level }) {
  const { t } = useI18n();
  if (level === "none") return <span className="text-slate-600">—</span>;
  return (
    <span className={level === "manage" ? "text-emerald-400" : "text-slate-400"}>
      {t(level === "manage" ? "roleMatrix.manage" : "roleMatrix.view")}
    </span>
  );
}

export default function RoleMatrix() {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
        {t("roleMatrix.title")}
      </p>
      <table className="w-full text-left text-xs">
        <thead className="text-slate-500">
          <tr>
            <th className="py-1 pr-2 font-medium">{t("roleMatrix.area")}</th>
            <th className="px-2 py-1 font-medium">{t("role.admin")}</th>
            <th className="px-2 py-1 font-medium">{t("role.operator")}</th>
            <th className="px-2 py-1 font-medium">{t("role.auditor")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {ROWS.map((r) => (
            <tr key={r.key}>
              <td className="py-1 pr-2 text-slate-300">{t(r.key)}</td>
              <td className="px-2 py-1">
                <Cell level={r.admin} />
              </td>
              <td className="px-2 py-1">
                <Cell level={r.operator} />
              </td>
              <td className="px-2 py-1">
                <Cell level={r.auditor} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
