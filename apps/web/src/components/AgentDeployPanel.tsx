import { useState } from "react";
import { useI18n } from "../i18n/I18nContext";
import { inputClass } from "./formStyles";

interface AgentDeployPanelProps {
  name: string;
  // Absent for an existing agent (only its hash is stored): the command shows a
  // token placeholder and the caller is expected to offer a rotate action.
  token?: string;
  pollSeconds: number;
}

const TOKEN_PLACEHOLDER = "<PORTWIZ_AGENT_TOKEN>";

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
  const [copied, setCopied] = useState<"" | "build" | "run">("");
  const [mode, setMode] = useState<"docker" | "native">("docker");

  const id = slug(name);
  const isHttps = /^https:\/\//i.test(apiUrl.trim());
  const hasToken = Boolean(token);
  // Build the image once so the run command below can reference it. This makes
  // the panel self-contained (no unpublished image assumed); operators who pull
  // a published image can skip this and edit the tag in the run command.
  const buildCommand = "docker build -t portwiz/agent:latest apps/agent";
  const command =
    `docker run -d --restart unless-stopped --name portwiz-agent-${id} ` +
    `-e PORTWIZ_API_URL=${apiUrl} ` +
    `-e PORTWIZ_AGENT_TOKEN=${token || TOKEN_PLACEHOLDER} ` +
    `-e PORTWIZ_AGENT_ID=${id} ` +
    `-e PORTWIZ_POLL_SECONDS=${pollSeconds} ` +
    `portwiz/agent:latest`;

  // The non-Docker path: build the Go binary, then run it with the same env the
  // container would set. nmap must be on PATH for service-version detection.
  const nativeBuildCommand = "go build -o portwiz-agent ./apps/agent/cmd/agent";
  const nativeCommand =
    `PORTWIZ_API_URL=${apiUrl} ` +
    `PORTWIZ_AGENT_TOKEN=${token || TOKEN_PLACEHOLDER} ` +
    `PORTWIZ_AGENT_ID=${id} ` +
    `PORTWIZ_POLL_SECONDS=${pollSeconds} ` +
    `./portwiz-agent`;
  const isDocker = mode === "docker";

  function copyBtn(which: "build" | "run", value: string) {
    return (
      <button
        onClick={() => {
          void navigator.clipboard?.writeText(value);
          setCopied(which);
        }}
        className="whitespace-nowrap rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
      >
        {copied === which ? t("agents.copied") : t("agents.copy")}
      </button>
    );
  }

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
        {isHttps ? (
          <p className="mt-1 text-xs text-emerald-400/80">{t("agents.deploy.tlsOk")}</p>
        ) : (
          <p className="mt-1 text-xs text-amber-400">{t("agents.deploy.tlsWarn")}</p>
        )}
      </div>

      <div className="flex gap-2 text-xs">
        <button
          type="button"
          onClick={() => setMode("docker")}
          className={`rounded-lg px-3 py-1.5 font-medium ${
            isDocker
              ? "bg-emerald-600 text-white"
              : "border border-slate-700 text-slate-300 hover:bg-slate-800"
          }`}
        >
          {t("agents.deploy.modeDocker")}
        </button>
        <button
          type="button"
          onClick={() => setMode("native")}
          className={`rounded-lg px-3 py-1.5 font-medium ${
            !isDocker
              ? "bg-emerald-600 text-white"
              : "border border-slate-700 text-slate-300 hover:bg-slate-800"
          }`}
        >
          {t("agents.deploy.modeNative")}
        </button>
      </div>

      <div>
        <label className="block text-xs text-slate-400">
          {isDocker ? t("agents.deploy.buildTitle") : t("agents.deploy.nativeBuildTitle")}
        </label>
        <div className="flex items-start gap-2">
          <code className="flex-1 overflow-x-auto whitespace-pre rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
            {isDocker ? buildCommand : nativeBuildCommand}
          </code>
          {copyBtn("build", isDocker ? buildCommand : nativeBuildCommand)}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {isDocker ? t("agents.deploy.buildHint") : t("agents.deploy.nativeBuildHint")}
        </p>
      </div>

      <div>
        <label className="block text-xs text-slate-400">
          {isDocker ? t("agents.deploy.command") : t("agents.deploy.nativeCommand")}
        </label>
        <div className="flex items-start gap-2">
          <code className="flex-1 overflow-x-auto whitespace-pre rounded bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
            {isDocker ? command : nativeCommand}
          </code>
          {copyBtn("run", isDocker ? command : nativeCommand)}
        </div>
        {!hasToken && (
          <p className="mt-1 text-xs text-amber-400">{t("agents.deploy.tokenPlaceholderHint")}</p>
        )}
        {!isDocker && (
          <p className="mt-1 text-xs text-slate-500">{t("agents.deploy.nativeNmapHint")}</p>
        )}
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
