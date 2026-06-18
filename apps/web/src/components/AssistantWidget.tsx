import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  type ChatMessage,
  type ProposedAction,
  chatAssistant,
  executeAction,
  fetchSettings,
} from "../api/client";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";
import { useToast } from "./Toast";

function prettifyKey(key: string): string {
  return key.replace(/_/g, " ");
}

function summaryEntries(summary: Record<string, unknown>): [string, string][] {
  return Object.entries(summary)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => [k, String(v)]);
}

export default function AssistantWidget() {
  const { t } = useI18n();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<ProposedAction | null>(null);
  const [running, setRunning] = useState(false);
  const [available, setAvailable] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Only offer the assistant when an AI provider is actually configured.
  useEffect(() => {
    fetchSettings()
      .then((s) => setAvailable(s.ai_configured))
      .catch(() => setAvailable(false));
  }, []);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, action, open]);

  function append(role: ChatMessage["role"], content: string) {
    setMessages((m) => [...m, { role, content }]);
  }

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setAction(null);
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setLoading(true);
    try {
      const res = await chatAssistant(next);
      if (res.reply) append("assistant", res.reply);
      if (res.action) setAction(res.action);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("assistant.providerUnavailable");
      append("assistant", msg);
    } finally {
      setLoading(false);
    }
  }

  async function onConfirm() {
    if (!action || running) return;
    setRunning(true);
    try {
      await executeAction(action.request);
      toast.success(t("assistant.widget.done"));
      append("assistant", t("assistant.widget.done"));
      setAction(null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("assistant.widget.failed");
      toast.error(msg);
      append("assistant", `${t("assistant.widget.failed")}: ${msg}`);
    } finally {
      setRunning(false);
    }
  }

  if (!available) return null;

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label={t("assistant.widget.openAria")}
        title={t("assistant.widget.title")}
        className="fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600 text-xl text-white shadow-lg hover:bg-emerald-500"
      >
        💬
      </button>
    );
  }

  const actionTitle = action ? t(`assistant.act.${action.name.replace(/\./g, "_")}` as TKey) : "";

  return (
    <div className="fixed bottom-5 right-5 z-40 flex h-[32rem] w-[22rem] max-w-[calc(100vw-2.5rem)] flex-col rounded-2xl border border-slate-800 bg-slate-900 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <span className="font-medium text-slate-100">{t("assistant.widget.title")}</span>
        <button
          onClick={() => setOpen(false)}
          aria-label={t("assistant.widget.closeAria")}
          className="text-slate-400 hover:text-slate-200"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        {messages.length === 0 && (
          <p className="text-slate-500">{t("assistant.widget.greeting")}</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 ${
              m.role === "user"
                ? "ml-auto bg-emerald-600 text-white"
                : "bg-slate-800 text-slate-200"
            }`}
          >
            {m.content}
          </div>
        ))}

        {action && (
          <div className="space-y-2 rounded-xl border border-emerald-800 bg-emerald-950/40 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-300">
              {t("assistant.widget.confirmTitle")}
            </p>
            <p className="font-medium text-slate-100">{actionTitle}</p>
            <dl className="space-y-0.5 text-xs text-slate-300">
              {summaryEntries(action.summary).map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <dt className="text-slate-500">{prettifyKey(k)}:</dt>
                  <dd className="font-mono">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="flex gap-2 pt-1">
              <button
                onClick={onConfirm}
                disabled={running}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {running ? t("assistant.widget.running") : t("assistant.widget.confirm")}
              </button>
              <button
                onClick={() => setAction(null)}
                disabled={running}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
              >
                {t("assistant.widget.dismiss")}
              </button>
            </div>
          </div>
        )}

        {loading && <p className="text-xs text-slate-500">{t("assistant.widget.thinking")}</p>}
        <div ref={endRef} />
      </div>

      <form onSubmit={onSend} className="flex gap-2 border-t border-slate-800 p-3">
        <input
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
          placeholder={t("assistant.widget.placeholder")}
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {t("assistant.widget.send")}
        </button>
      </form>
    </div>
  );
}
