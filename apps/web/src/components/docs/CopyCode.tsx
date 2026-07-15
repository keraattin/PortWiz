import { useState } from "react";
import { useI18n } from "../../i18n/I18nContext";

// A code block with a copy-to-clipboard button, for commands in the docs guides.
export default function CopyCode({ code }: { code: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (e.g. insecure origin); leave the code to select */
    }
  }

  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 pr-20 text-xs text-slate-300">
        <code>{code}</code>
      </pre>
      <button
        type="button"
        onClick={copy}
        className="absolute right-2 top-2 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-800"
      >
        {copied ? t("common.copied") : t("common.copy")}
      </button>
    </div>
  );
}
