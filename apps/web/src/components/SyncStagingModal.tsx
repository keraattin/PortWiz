import { type ReactNode } from "react";
import Button from "./Button";
import Modal from "./Modal";
import { CHECKBOX_CLS } from "./tableView";
import { useI18n } from "../i18n/I18nContext";

export interface StagingColumn<T> {
  key: string;
  label: string;
  get: (item: T) => ReactNode;
}

/** A reusable "preview a sync, pick rows, apply" modal: a selectable table of
 * source records with a New/Exists badge and an import button. Bulk-attribute
 * controls (if any) are the caller's concern and passed as `children`. */
export default function SyncStagingModal<T>({
  open,
  onClose,
  title,
  loading,
  items,
  rowKey,
  isExisting,
  columns,
  selected,
  onToggle,
  onToggleAll,
  applying,
  onApply,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  loading: boolean;
  items: T[];
  rowKey: (item: T) => string;
  isExisting: (item: T) => boolean;
  columns: StagingColumn<T>[];
  selected: Set<string>;
  onToggle: (key: string) => void;
  onToggleAll: (on: boolean) => void;
  applying: boolean;
  onApply: () => void;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const allChecked = items.length > 0 && items.every((it) => selected.has(rowKey(it)));
  return (
    <Modal open={open} onClose={onClose} title={title} wide>
      {loading ? (
        <p className="py-6 text-center text-sm text-slate-500">{t("common.loading")}</p>
      ) : (
        <div className="space-y-3">
          {children}
          {items.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">{t("table.stagingNothing")}</p>
          ) : (
            <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-800">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-900 text-slate-400">
                  <tr>
                    <th className="px-4 py-2">
                      <input
                        type="checkbox"
                        className={CHECKBOX_CLS}
                        checked={allChecked}
                        onChange={(e) => onToggleAll(e.target.checked)}
                      />
                    </th>
                    {columns.map((c) => (
                      <th key={c.key} className="px-4 py-2 font-medium">
                        {c.label}
                      </th>
                    ))}
                    <th className="px-4 py-2 font-medium">{t("table.stagingStatus")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {items.map((it) => {
                    const key = rowKey(it);
                    return (
                      <tr key={key} className="bg-slate-950">
                        <td className="px-4 py-2">
                          <input
                            type="checkbox"
                            className={CHECKBOX_CLS}
                            checked={selected.has(key)}
                            onChange={() => onToggle(key)}
                          />
                        </td>
                        {columns.map((c) => (
                          <td key={c.key} className="px-4 py-2 text-slate-300">
                            {c.get(it)}
                          </td>
                        ))}
                        <td className="px-4 py-2">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs ${
                              isExisting(it)
                                ? "bg-slate-700 text-slate-300"
                                : "bg-emerald-900 text-emerald-300"
                            }`}
                          >
                            {isExisting(it) ? t("table.stagingExists") : t("table.stagingNew")}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center justify-end gap-3">
            <span className="text-xs text-slate-500">
              {t("table.selected", { count: selected.size })}
            </span>
            <Button onClick={onApply} disabled={applying || selected.size === 0}>
              {applying ? t("common.saving") : t("table.stagingImport")}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
