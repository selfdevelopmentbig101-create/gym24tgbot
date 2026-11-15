/*
 * App shell. Startup: verify login (GET /api/me) and load settings, then
 *   profile incomplete -> Onboarding
 *   profile complete   -> daily targets ("Your plan is ready")
 * The bottom tabs (Home, Plan, Train, Stats, Profile) appear once those tabs are
 * built (Stage 3+); unbuilt tabs stay hidden.
 */
import { useCallback, useEffect, useState } from "react";
import {
  ApiError, getConfig, getMe, getTargets, setLanguage,
  type AppConfig, type LanguageCode, type Me, type Targets,
} from "./lib/api";
import { haptic } from "./lib/telegram";
import { translate, type TextKey } from "./i18n";
import { Onboarding } from "./screens/Onboarding";
import { PlanReady } from "./screens/PlanReady";

const LANGUAGES: { code: LanguageCode; label: string }[] = [
  { code: "en", label: "English" },
  { code: "ru", label: "Русский" },
  { code: "uz", label: "O‘zbekcha" },
];

type State =
  | { kind: "loading" }
  | { kind: "error"; key: TextKey }
  | { kind: "onboarding"; me: Me; config: AppConfig }
  | { kind: "targets"; me: Me; targets: Targets; justFinished: boolean; planReady: boolean };

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
  const lang: LanguageCode = "me" in state ? state.me.language_effective : "en";
  const t = useCallback((key: TextKey, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const me = await getMe();
      if (!me.profile_complete) {
        setState({ kind: "onboarding", me, config: await getConfig() });
      } else {
        setState({ kind: "targets", me, targets: await getTargets(), justFinished: false, planReady: true });
      }
    } catch (error) {
      setState({ kind: "error", key: errorKey(error) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function chooseLanguage(code: LanguageCode) {
    if (state.kind !== "targets" || saving) return;
    haptic.select();
    setSaving(code);
    try {
      const me = await setLanguage(code);
      setState({ ...state, me });
      haptic.success();
    } catch {
      haptic.error();
    } finally {
      setSaving(null);
    }
  }

  if (state.kind === "onboarding") {
    return (
      <Onboarding me={state.me} config={state.config} t={t}
                  onLanguage={(me) => setState({ ...state, me })}
                  onDone={(saved) => setState({
                    kind: "targets", me: { ...state.me, profile_complete: true, disclaimer_accepted: true },
                    targets: saved.targets, justFinished: true, planReady: saved.plan_ready,
                  })} />
    );
  }

  if (state.kind === "targets") {
    const picker = (
      <section className="language-row">
        <span className="muted small">{t("language_title")}</span>
        <div className="pills" role="radiogroup" aria-label={t("language_title")}>
          {LANGUAGES.map(({ code, label }) => (
            <button key={code} type="button" role="radio" aria-checked={state.me.language_effective === code}
                    className={"pill" + (state.me.language_effective === code ? " pill-on" : "")}
                    disabled={saving !== null} onClick={() => void chooseLanguage(code)}>
              {saving === code ? "…" : label}
            </button>
          ))}
        </div>
      </section>
    );
    return <PlanReady targets={state.targets} lang={lang} t={t} justFinished={state.justFinished}
                      planReady={state.planReady} languagePicker={picker} />;
  }

  return (
    <main className="screen">
      <h1 className="wordmark">{t("app_name")}</h1>
      {state.kind === "loading" ? (
        <section className="card center" aria-busy="true">
          <div className="spinner" />
          <p className="muted">{t("loading")}</p>
        </section>
      ) : (
        <section className="card center" role="alert">
          <p>{t(state.key)}</p>
          {state.key !== "error_outside" && (
            <button type="button" className="button-primary" onClick={() => { haptic.tap(); void load(); }}>
              {t("retry")}
            </button>
          )}
        </section>
      )}
    </main>
  );
}
