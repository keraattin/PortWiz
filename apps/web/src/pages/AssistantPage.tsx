import { type FormEvent, useState } from "react";
import {
  ApiError,
  askAssistant,
  fingerprintBanner,
} from "../api/client";
import { type TKey } from "../i18n/locales/en";
import { useI18n } from "../i18n/I18nContext";

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

function errorMessage(e: unknown, t: Translate): string {
  return e instanceof ApiError
    ? e.status === 502
      ? t("assistant.providerUnavailable")
      : e.message
    : t("common.error");
}

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500";

const buttonClass =
  "rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50";

function ProviderBadge({ provider }: { provider: string }) {
  return (
    <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs uppercase tracking-wide text-emerald-400">
      {provider}
    </span>
  );
}

export default function AssistantPage() {
  const { t } = useI18n();
  // Fingerprint helper state.
  const [banner, setBanner] = useState("");
  const [port, setPort] = useState("");
  const [protocol, setProtocol] = useState("tcp");
  const [fpResult, setFpResult] = useState<{ provider: string; summary: string } | null>(null);
  const [fpError, setFpError] = useState<string | null>(null);
  const [fpLoading, setFpLoading] = useState(false);

  // Assistant Q&A state.
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{ provider: string; answer: string } | null>(null);
  const [qError, setQError] = useState<string | null>(null);
  const [qLoading, setQLoading] = useState(false);

  async function onFingerprint(e: FormEvent) {
    e.preventDefault();
    setFpError(null);
    setFpResult(null);
    setFpLoading(true);
    try {
      const result = await fingerprintBanner({
        banner,
        port: port ? Number(port) : null,
        protocol: protocol || null,
      });
      setFpResult(result);
    } catch (err) {
      setFpError(errorMessage(err, t));
    } finally {
      setFpLoading(false);
    }
  }

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    setQError(null);
    setAnswer(null);
    setQLoading(true);
    try {
      setAnswer(await askAssistant(question));
    } catch (err) {
      setQError(errorMessage(err, t));
    } finally {
      setQLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <p className="text-sm text-slate-500">{t("assistant.intro")}</p>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">{t("assistant.fingerprintTitle")}</h2>
        <form
          onSubmit={onFingerprint}
          className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4"
        >
          <textarea
            className={`${inputClass} h-24 font-mono`}
            placeholder={t("assistant.bannerPlaceholder")}
            value={banner}
            onChange={(e) => setBanner(e.target.value)}
            required
          />
          <div className="flex flex-wrap gap-3">
            <input
              className={`${inputClass} sm:w-32`}
              placeholder={t("assistant.portPlaceholder")}
              inputMode="numeric"
              value={port}
              onChange={(e) => setPort(e.target.value)}
            />
            <input
              className={`${inputClass} sm:w-32`}
              placeholder={t("assistant.protocolPlaceholder")}
              value={protocol}
              onChange={(e) => setProtocol(e.target.value)}
            />
            <button type="submit" className={buttonClass} disabled={fpLoading}>
              {fpLoading ? t("assistant.analyzing") : t("assistant.identify")}
            </button>
          </div>
        </form>
        {fpError && <p className="text-sm text-red-400">{fpError}</p>}
        {fpResult && (
          <div className="space-y-2 rounded-xl border border-slate-800 bg-slate-950 p-4">
            <ProviderBadge provider={fpResult.provider} />
            <pre className="whitespace-pre-wrap text-sm text-slate-200">{fpResult.summary}</pre>
          </div>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">{t("assistant.askTitle")}</h2>
        <form onSubmit={onAsk} className="flex gap-3">
          <input
            className={inputClass}
            placeholder={t("assistant.questionPlaceholder")}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
          />
          <button type="submit" className={buttonClass} disabled={qLoading}>
            {qLoading ? t("assistant.thinking") : t("assistant.ask")}
          </button>
        </form>
        {qError && <p className="text-sm text-red-400">{qError}</p>}
        {answer && (
          <div className="space-y-2 rounded-xl border border-slate-800 bg-slate-950 p-4">
            <ProviderBadge provider={answer.provider} />
            <p className="whitespace-pre-wrap text-sm text-slate-200">{answer.answer}</p>
          </div>
        )}
      </section>
    </div>
  );
}
