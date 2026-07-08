import { ApiError } from "../api/client";
import { useI18n } from "./I18nContext";

/** Turn any thrown value into a user-facing message: an ApiError carries the
 * server's message; anything else falls back to a localized generic error.
 * One shared hook so every page doesn't redeclare the same helper (and doesn't
 * hardcode an untranslated fallback). */
export function useErrorMessage(): (e: unknown) => string {
  const { t } = useI18n();
  return (e) => (e instanceof ApiError ? e.message : t("common.error"));
}
