/*
 * Stage 0 screen: a connection check. It proves the whole chain works:
 * Telegram -> signed initData -> our API -> database -> shared language.
 * Stage 2 replaces this with the real app shell (tabs + onboarding).
 */
import { useCallback, useEffect, useState } from "react";
import { ApiError, getMe, setLanguage, type LanguageCode, type Me } from "./lib/api";
import { getInitData, haptic } from "./lib/telegram";
import { translate, type TextKey } from "./i18n";

const LANGUAGES: { code: LanguageCode; label: string }[] = [
  { code: "en", label: "English" },
  { code: "ru", label: "Русский" },
  { code: "uz", label: "O‘zbekcha" },
];

type State =
  | { kind: "loading" }
  | { kind: "error"; key: TextKey }
  | { kind: "ready"; me: Me };

function errorKey(error: unknown): TextKey {
  if (!(error instanceof ApiError)) return "error_generic";
  if (error.code === "not_in_telegram") return "error_outside";
  if (error.status === 401) return "error_auth";
  if (error.status === 429) return "error_rate";
  if (error.status === 0) return "error_network";
  return "error_generic";
}

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [saving, setSaving] = useState<LanguageCode | null>(null);
  const lang: LanguageCode = state.kind === "ready" ? state.me.language_effective : "en";
  const t = (key: TextKey, vars?: Record<string, string | number>) => translate(lang, key, vars);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", me: await getMe() });
    } catch (error) {
      setState({ kind: "error", key: errorKey(error) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function chooseLanguage(code: LanguageCode) {
    if (state.kind !== "ready" || saving) return;
    haptic.select();
    setSaving(code);
    try {
      setState({ kind: "ready", me: await setLanguage(code) });
      haptic.success();
    } catch (error) {
      haptic.error();
      setState({ kind: "error", key: errorKey(error) });
    } finally {
      setSaving(null);
    }
  }

  return (
    <main className="screen">
      <h1 className="wordmark">{t("app_name")}</h1>

      {state.kind === "loading" && (
        <section className="card center" aria-busy="true">
          <div className="spinner" />
          <p className="muted">{t("loading")}</p>
        </section>
      )}

      {state.kind === "error" && (
        <section className="card center" role="alert">
          <p>{t(state.key)}</p>
          {state.key !== "error_outside" && (
            <button className="button-primary" onClick={() => { haptic.tap(); void load(); }}>
              {t("retry")}
            </button>
          )}
        </section>
      )}

      {state.kind === "ready" && (
        <>
          <h2 className="title">{t("hello", { name: state.me.first_name || "👋" })}</h2>
          <section className="card">
            <h3 className="card-title">{t("setup_title")}</h3>
            <p className="muted small">{t("setup_subtitle")}</p>
            <ul className="checks">
              <Check ok={!!getInitData()} label={t("check_telegram")} />
              <Check ok label={t("check_signature")} />
              <Check ok label={t("check_account")} />
              <Check ok={state.me.profile_complete}
                     label={t(state.me.profile_complete ? "profile_done" : "profile_missing")} />
            </ul>
          </section>

          <section className="card">
            <h3 className="card-title">{t("language_title")}</h3>
            <div className="pills" role="radiogroup">
              {LANGUAGES.map(({ code, label }) => (
                <button key={code} role="radio" aria-checked={state.me.language_effective === code}
                        className={`pill ${state.me.language_effective === code ? "pill-on" : ""}`}
                        disabled={saving !== null} onClick={() => void chooseLanguage(code)}>
                  {saving === code ? "…" : label}
                </button>
              ))}
            </div>
            <p className="muted small">{t("language_hint")}</p>
          </section>
        </>
      )}
    </main>
  );
}

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="check">
      <span className={`check-badge ${ok ? "check-ok" : "check-pending"}`} aria-hidden>
        {ok ? "✓" : "•"}
      </span>
      {label}
    </li>
  );
}
