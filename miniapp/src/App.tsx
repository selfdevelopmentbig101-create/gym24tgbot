/*
 * App shell. Startup: verify login (GET /api/me) and load settings, then
 *   profile incomplete -> Onboarding (whatever the link)
 *   profile complete   -> the screen for the URL path, with the bottom tab bar:
 *     /                     Home: greeting, character, next workout, this week, today (Stage 7)
 *     /targets              daily targets (also shown once, right after onboarding)
 *     /plan                 Plan: calendar, current program, details, weekly volume
 *     /plan/edit[/{day}]    split editor with the energy bar
 *     /plan/programs[/new]  all programs, create a program
 *     /workout              Train home: Splits and All exercises
 *     /workout/session      session of the active split (statuses, last time's numbers, Start)
 *     /workout/splits[/{id}]  splits (active on top), split detail with "Choose this split"
 *     /workout/exercises[/muscle/{key}]  by muscle (grid) or all (search); one muscle's exercises
 *     /workout/live         live logger (rest timer, supersets, notes, PRs, finish summary)
 *     /workout/go           guided workout (countdown, exercise screen, rest timer, summary)
 *     /train                All exercises (old bot link)
 *     /profile              Profile: character, level, XP, achievements, settings (Stage 6)
 *     /profile/edit         edit profile answers
 *     /exercise/{id}        exercise detail
 * The Stats tab (Stage 8) stays hidden until it's built.
 */
import { useCallback, useEffect, useState } from "react";
import {
  ApiError, getConfig, getMe, getTargets, setLanguage,
  type AppConfig, type LanguageCode, type Me, type Targets,
} from "./lib/api";
import { useRoute, navigate } from "./lib/router";
import { haptic } from "./lib/telegram";
import { translate, type TextKey } from "./i18n";
import { TabBar } from "./components/TabBar";
import { ExerciseDetail } from "./screens/ExerciseDetail";
import { AllExercises } from "./screens/AllExercises";
import { MuscleExercises } from "./screens/MuscleExercises";
import { SplitDetail } from "./screens/SplitDetail";
import { Splits } from "./screens/Splits";
import { TrainHome } from "./screens/TrainHome";
import { Logger } from "./screens/Logger";
import { Profile } from "./screens/Profile";
import { ProfileEdit } from "./screens/ProfileEdit";
import { Home } from "./screens/Home";
import { Targets as TargetsScreen } from "./screens/Targets";
import { Onboarding } from "./screens/Onboarding";
import { Plan } from "./screens/Plan";
import { PlanReady } from "./screens/PlanReady";
import { ProgramNew } from "./screens/ProgramNew";
import { Programs } from "./screens/Programs";
import { SplitEditor } from "./screens/SplitEditor";
import { TrainDay } from "./screens/TrainDay";
import { Workout } from "./screens/Workout";

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
    if (route.name === "exercises") {
      screen = <AllExercises t={t} locale={locale} />;
    } else if (route.name === "muscle") {
      screen = <MuscleExercises key={route.key} muscle={route.key} t={t} />;
    } else if (route.name === "splits") {
      screen = <Splits t={t} />;
    } else if (route.name === "split") {
      screen = <SplitDetail key={route.id} id={route.id} t={t} />;
    } else if (route.name === "workoutSession") {
      screen = <TrainDay t={t} />;
    } else if (route.name === "exercise") {
      screen = <ExerciseDetail id={route.id} t={t} attribution={state.config.attribution} />;
    } else if (route.name === "plan") {
      screen = <Plan t={t} locale={locale} />;
    } else if (route.name === "planEdit") {
      screen = <SplitEditor key={route.day ?? 0} initialDay={route.day} t={t} />;
    } else if (route.name === "programs") {
      screen = <Programs t={t} />;
    } else if (route.name === "programNew") {
      screen = <ProgramNew t={t} />;
    } else if (route.name === "workout") {
      screen = <TrainHome t={t} />;
    } else if (route.name === "workoutLive") {
      screen = <Logger t={t} />;
    } else if (route.name === "workoutGuided") {
      screen = <Workout t={t} attribution={state.config.attribution} />;
    } else if (route.name === "profile") {
      screen = <Profile t={t} me={state.me} config={state.config} saving={saving}
                        onLanguage={(code) => void chooseLanguage(code)}
                        onDeleted={() => { navigate({ name: "home" }, { replace: true }); void load(); }} />;
    } else if (route.name === "profileEdit") {
      screen = <ProfileEdit t={t} config={state.config} />;
    } else if (route.name === "targets") {
      screen = <TargetsScreen targets={state.targets} lang={lang} t={t} />;
    } else if (!state.justFinished) {
      screen = <Home t={t} name={state.me.first_name} locale={locale} />;
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
      // Right after onboarding: "Your plan is ready" once, then Home.
      screen = (
        <>
          <PlanReady targets={state.targets} lang={lang} t={t} justFinished={state.justFinished}
                     planReady={state.planReady} languagePicker={picker} />
          <div className="home-continue">
            <button type="button" className="button-secondary"
                    onClick={() => { haptic.tap(); setState({ ...state, justFinished: false }); }}>
              {t("home_go_home")}
            </button>
          </div>
        </>
      );
    }
    return (
      <div className="with-tabs">
        {screen}
        {route.name !== "workoutGuided" && <TabBar current={route} t={t} />}
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
