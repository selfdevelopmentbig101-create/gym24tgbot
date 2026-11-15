/*
 * App shell. Startup: verify login (GET /api/me) and load settings, then
 *   profile incomplete -> Onboarding (whatever the link)
 *   profile complete   -> the screen for the URL path, with the bottom tab bar:
 *     /                 Home (daily targets until the real Home tab, Stage 7)
 *     /train            Train: exercise library (the workout logger joins it in Stage 5)
 *     /exercise/{id}    exercise detail
 * Unbuilt tabs (Plan, Stats, Profile) stay hidden.
 */
import { useCallback, useEffect, useState } from "react";
import {
  ApiError, getConfig, getMe, getTargets, setLanguage,
  type AppConfig, type LanguageCode, type Me, type Targets,
} from "./lib/api";
import { useRoute } from "./lib/router";
import { haptic } from "./lib/telegram";
import { translate, type TextKey } from "./i18n";
import { TabBar } from "./components/TabBar";
import { ExerciseDetail } from "./screens/ExerciseDetail";
import { Library } from "./screens/Library";
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
  | { kind: "main"; me: Me; config: AppConfig; targets: Targets; justFinished: boolean; planReady: boolean };

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
  const route = useRoute();
  const lang: LanguageCode = "me" in state ? state.me.language_effective : "en";
  const locale = lang === "uz" ? "uz-Latn" : lang;
  const t = useCallback((key: TextKey, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [me, config] = await Promise.all([getMe(), getConfig()]);
      if (!me.profile_complete) {
        setState({ kind: "onboarding", me, config });
      } else {
        setState({ kind: "main", me, config, targets: await getTargets(), justFinished: false, planReady: true });
      }
    } catch (error) {
      setState({ kind: "error", key: errorKey(error) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function chooseLanguage(code: LanguageCode) {
    if (state.kind !== "main" || saving) return;
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
                    kind: "main", config: state.config,
                    me: { ...state.me, profile_complete: true, disclaimer_accepted: true },
                    targets: saved.targets, justFinished: true, planReady: saved.plan_ready,
                  })} />
    );
  }

  if (state.kind === "main") {
    let screen;
    if (route.name === "library") {
      screen = <Library t={t} hasProfile locale={locale} />;
    } else if (route.name === "exercise") {
      screen = <ExerciseDetail id={route.id} t={t} attribution={state.config.attribution} />;
    } else {
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
      screen = <PlanReady targets={state.targets} lang={lang} t={t} justFinished={state.justFinished}
                          planReady={state.planReady} languagePicker={picker} />;
    }
    return (
      <div className="with-tabs">
        {screen}
        <TabBar current={route} t={t} />
      </div>
    );
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
