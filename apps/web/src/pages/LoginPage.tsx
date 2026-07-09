import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { useI18n } from "../i18n/I18nContext";

export default function LoginPage() {
  const { token, login } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (token) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      // Don't mask a down/erroring server as "wrong password": a non-technical
      // user would retype their password forever. Distinguish the real cause.
      if (err instanceof ApiError) {
        if (err.status === 429) setError(t("login.tooMany"));
        else if (err.status === 401 || err.status === 400) setError(t("login.invalid"));
        else setError(t("login.serverError"));
      } else {
        setError(t("login.unreachable"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="absolute right-4 top-4">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-emerald-400">PortWiz</h1>
          <p className="mt-1 text-sm text-slate-400">{t("login.tagline")}</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-slate-300">{t("login.email")}</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-slate-100 outline-none focus:border-emerald-500"
              placeholder="admin@portwiz.local"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-300">{t("login.password")}</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-slate-100 outline-none focus:border-emerald-500"
              placeholder="••••••••"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? t("login.signingIn") : t("login.signIn")}
          </Button>
        </form>
      </div>
    </div>
  );
}
