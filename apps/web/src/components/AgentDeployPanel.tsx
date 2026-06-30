import { useState } from "react";
import { useI18n } from "../i18n/I18nContext";

interface AgentDeployPanelProps {
  name: string;
  token: string;
  pollSeconds: number;
}

// Docker container names and the agent id must be shell-safe for a copy-paste
// command, so derive a slug from the (free-form) agent name.
function slug(name: string): string {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "agent"
  );
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

/**
 * Guided deploy instructions shown once, right after a token is revealed
 * (enrollment or rotation). Builds a ready-to-run docker command wired with the
 * server URL, the new token and the agent id.
 */
export default function AgentDeployPanel({ name, token, pollSeconds }: AgentDeployPanelProps) {
  const { t } = useI18n();
  // The agent connects straight to the API. In production a single origin
  // reverse-proxies /api, so the browser origin is the right default; the admin
  // can correct it to whatever address the remote agent can actually reach.
  const [apiUrl, setApiUrl] = useState(() => window.location.origin);
  const [copied, setCopied] = useState(false);

  const id = slug(name);
  const command =
    `docker run -d --restart unless-stopped --name portwiz-agent-${id} ` +
    `-e PORTWIZ_API_URL=${apiUrl} ` +
    `-e PORTWIZ_AGENT_TOKEN=${token} ` +
    `-e PORTWIZ_AGENT_ID=${id} ` +
    `portwiz/agent:latest`;

  return (
    <div className="space-y-3 border-t border-emerald-900/60 pt-3">
      <p className="text-sm font-medium text-emerald-200">{t("agents.deploy.title")}</p>
      <p className="text-xs text-emerald-300/80">{t("agents.deploy.intro")}</p>

      <div>
        <label className="block text-xs text-slate-400">{t("agents.deploy.apiUrl")}</label>
        <input
          className={inputClass}
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          spellCheck={false}
        />
        <p className="mt-1 text-xs text-slate-500">{t("agents.deploy.apiUrlHint")}</p>
      </div>

      <div>
        <label className="block text-xs text-slate-400">{t("agents.deploy.command")}</label>
        <div className="flex items-start gap-2">
          <code className="flex-1 overflow-x-auto whitespace-pre rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
            {command}
          </code>
          <button
            onClick={() => {
              void navigator.clipboard?.writeText(command);
              setCopied(true);
            }}
            className="whitespace-nowrap rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            {copied ? t("agents.copied") : t("agents.copy")}
          </button>
        </div>
      </div>

      <ol className="list-decimal space-y-1 pl-5 text-xs text-slate-400">
        <li>{t("agents.deploy.step1")}</li>
        <li>{t("agents.deploy.step2")}</li>
        <li>{t("agents.deploy.step3")}</li>
      </ol>
      <p className="text-xs text-slate-500">{t("agents.deploy.poll", { seconds: pollSeconds })}</p>
    </div>
  );
}
