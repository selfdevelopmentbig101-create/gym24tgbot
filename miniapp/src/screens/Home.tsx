/*
 * Home tab (reference image 1): greeting, the character, the next workout with a
 * Start button (or Continue for the one in progress), this week at a glance
 * (Mon-Sun dots, workouts vs goal, sets, volume, records, minutes), today's
 * calories and protein, body weight, and shortcuts.
 */
import { useCallback, useEffect, useState } from "react";
import { getHome, type HomeView } from "../lib/homeApi";
import { startWorkout, trainErrorKey } from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { CharacterCard } from "../components/CharacterCard";
import { Check, ChevronRight, Dumbbell, Flame, Search } from "../components/Icons";
import { Calendar } from "../components/PlanIcons";
import "./plan.css";
import "./home.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

function Bar({ value, target }: { value: number; target: number }) {
  const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  return (
    <span className="home-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
      <span style={{ width: `${pct}%` }} />
    </span>
  );
}

export function Home({ t, name, locale }: { t: T; name: string; locale: string }) {
  const [view, setView] = useState<HomeView | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getHome().then((v) => { setView(v); setError(null); }).catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load]);
  useEffect(() => bindNativeBack(null), []); // a tab: no Back button
  useEffect(() => {
    // Fresh numbers when you come back to the app (e.g. after logging in the chat).
    const onShow = () => { if (document.visibilityState === "visible") load(); };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [load]);

  async function start() {
    if (!view?.next_workout || busy) return;
    setBusy(true);
    try {
      await startWorkout(view.next_workout.index);
      haptic.success();
      navigate({ name: "workoutLive" });
    } catch (e) {
      haptic.error();
      setError(trainErrorKey(e));
      setBusy(false);
    }
  }

  const weekday = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
  const greetingName = name.trim() || t("home_greeting_noname");

  return (
    <main className="home">
      <header className="home-head">
        <h1 className="home-greeting">
          {t(("home_greeting_" + (view?.part_of_day ?? "morning")) as TextKey, { name: greetingName })}
        </h1>
        {view && (
          <p className="muted small">
            {new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long" })
              .format(new Date(view.today + "T12:00:00"))}
          </p>
        )}
      </header>

      <CharacterCard t={t} />

      {error && <p className="notice" role="alert">{t(error)}</p>}
      {!view && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {view && view.active && (
        <section className="card home-next home-live">
          <p className="plan-eyebrow">{t("home_in_progress")}</p>
          <h2 className="home-next-name">{dayName({ ...view.active, title: null }, t)}</h2>
          <Bar value={view.active.done_sets} target={view.active.planned_sets} />
          <p className="muted small">{t("home_progress", { done: view.active.done_sets, planned: view.active.planned_sets })}</p>
          <button type="button" className="button-primary"
                  onClick={() => { haptic.tap(); navigate({ name: "workoutLive" }); }}>{t("home_continue")}</button>
        </section>
      )}

      {view && !view.active && view.next_workout && (
        <section className="card home-next">
          <p className="plan-eyebrow">{t("home_next")}</p>
          <h2 className="home-next-name">{dayName(view.next_workout, t)}</h2>
          <p className="muted small">
            {t("home_next_meta", { n: view.next_workout.exercises, min: view.next_workout.minutes })}
          </p>
          {view.next_workout.muscles.length > 0 && (
            <div className="chips wrap home-muscles">
              {view.next_workout.muscles.map((m) => (
                <span key={m} className="chip chip-static">{t(("muscle_" + m) as TextKey)}</span>
              ))}
            </div>
          )}
          {view.next_workout.names.length > 0 && (
            <p className="small home-names">{view.next_workout.names.join(" · ")}</p>
          )}
          <div className="home-actions">
            <button type="button" className="button-primary" disabled={busy} onClick={() => void start()}>
              {busy ? <span className="spinner spinner-small" /> : <><Dumbbell />{t("home_start")}</>}
            </button>
            <button type="button" className="button-link"
                    onClick={() => { haptic.tap(); navigate({ name: "workout" }); }}>{t("home_see_day")}</button>
          </div>
        </section>
      )}

      {view && (
        <section className="card">
          <div className="home-row">
            <h2 className="card-title">{t("home_week")}</h2>
            <span className="small home-streak"><Flame />{t("char_streak", { n: view.week.streak_weeks })}</span>
          </div>
          <ol className="week-dots">
            {view.week.days.map((d) => (
              <li key={d.date} className={"week-dot" + (d.trained ? " week-dot-on" : "") + (d.today ? " week-dot-today" : "")}>
                <span className="week-dot-circle">{d.trained && <Check />}</span>
                <span className="week-dot-label">{weekday.format(new Date(d.date + "T12:00:00"))}</span>
              </li>
            ))}
          </ol>
          <p className="small home-week-goal">
            {t("home_week_done", { done: view.week.done, goal: view.week.goal })} ·{" "}
            {view.week.done >= view.week.goal
              ? t("home_week_goal_met")
              : t("home_week_left", { n: view.week.goal - view.week.done })}
          </p>
          <div className="home-stats">
            <span><b>{view.week.sets}</b>{t("home_week_sets")}</span>
            <span><b>{view.week.volume_kg.toLocaleString(locale)}</b>{t("home_week_volume")}</span>
            <span><b>{view.week.prs}</b>{t("home_week_prs")}</span>
            <span><b>{view.week.minutes}</b>{t("home_week_minutes")}</span>
          </div>
        </section>
      )}

      {view && (
        <section className="card">
          <div className="home-row">
            <h2 className="card-title">{t("home_today")}</h2>
            <button type="button" className="button-link"
                    onClick={() => { haptic.tap(); navigate({ name: "targets" }); }}>{t("home_targets")}</button>
          </div>
          <div className="home-macro">
            <span>{t("home_calories")}</span>
            <span className="muted small">
              {t("home_of", { value: view.nutrition.calories, target: view.nutrition.calories_target, unit: t("home_kcal") })}
            </span>
          </div>
          <Bar value={view.nutrition.calories} target={view.nutrition.calories_target} />
          <div className="home-macro">
            <span>{t("home_protein")}</span>
            <span className="muted small">
              {t("home_of", { value: view.nutrition.protein_g, target: view.nutrition.protein_target, unit: t("home_g") })}
            </span>
          </div>
          <Bar value={view.nutrition.protein_g} target={view.nutrition.protein_target} />
          <p className="muted small">{t("home_food_hint")}</p>
        </section>
      )}

      {view && (
        <section className="card home-row">
          <div>
            <h2 className="card-title">{t("home_weight")}</h2>
            <p className="muted small">{view.weight.logged_at ? t("home_weight_hint") : t("home_weight_from_profile")}</p>
          </div>
          <b className="home-weight">{t("home_weight_value", { kg: view.weight.kg })}</b>
        </section>
      )}

      <nav className="home-links" aria-label={t("home_links")}>
        <button type="button" className="home-link" onClick={() => { haptic.tap(); navigate({ name: "library" }); }}>
          <Search /><span>{t("home_link_library")}</span><ChevronRight />
        </button>
        <button type="button" className="home-link" onClick={() => { haptic.tap(); navigate({ name: "plan" }); }}>
          <Calendar /><span>{t("home_link_plan")}</span><ChevronRight />
        </button>
        <button type="button" className="home-link" onClick={() => { haptic.tap(); navigate({ name: "programs" }); }}>
          <Dumbbell /><span>{t("home_link_programs")}</span><ChevronRight />
        </button>
      </nav>
    </main>
  );
}
