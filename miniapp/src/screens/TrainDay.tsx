/*
 * Train tab: the workout-day screen. Pick a day of the current program (the next
 * one is preselected), see its exercises with last time's numbers and the session
 * load, then Start. With a workout in progress it shows the statuses
 * (done / now / next) and a Continue button. Links to the exercise library.
 */
import { useCallback, useEffect, useState } from "react";
import { getTrain, startWorkout, trainErrorKey, type TrainOverview } from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { fmtSets, repRange } from "../lib/trainText";
import { navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { EnergyBar } from "../components/EnergyBar";
import { ExerciseImage } from "../components/ExerciseImage";
import { Search } from "../components/Icons";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function TrainDay({ t }: { t: T }) {
  const [data, setData] = useState<TrainOverview | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [armed, setArmed] = useState(false);

  const load = useCallback(() => {
    setError(null);
    getTrain()
      .then((d) => {
        setData(d);
        setSelected((s) => s ?? d.active?.day_index ?? d.next_index);
      })
      .catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load]);
  useEffect(() => bindNativeBack(null), []); // a tab: no Back button

  async function start(force: boolean) {
    if (busy || selected === null) return;
    setBusy(true);
    setError(null);
    try {
      await startWorkout(selected, force);
      haptic.success();
      navigate({ name: "workoutLive" });
    } catch (e) {
      haptic.error();
      setError(trainErrorKey(e));
    } finally {
      setBusy(false);
    }
  }

  const day = data?.days.find((d) => d.index === selected) ?? data?.days[0];
  const active = data?.active ?? null;
  const activeHere = active !== null && day !== undefined && active.day_index === day.index;

  return (
    <main className="train">
      <div className="train-head">
        <h1 className="screen-title left">{t("train_title")}</h1>
        <button type="button" className="button-secondary button-small"
                onClick={() => { haptic.tap(); navigate({ name: "library" }); }}>
          <Search />{t("train_library")}
        </button>
      </div>

      {error && (
        <section className="card center" role="alert">
          <p>{t(error)}</p>
          {!data && <button type="button" className="button-primary" onClick={load}>{t("retry")}</button>}
        </section>
      )}
      {!data && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {data && active && (
        <section className="card train-active">
          <p className="plan-eyebrow">{t("train_in_progress")}</p>
          <h2 className="plan-program-name">{dayName(active, t)}</h2>
          <p className="muted small">{t("train_progress", { done: active.done_sets, planned: active.planned_sets })}</p>
          <button type="button" className="button-primary"
                  onClick={() => { haptic.tap(); navigate({ name: "workoutLive" }); }}>{t("train_continue")}</button>
        </section>
      )}

      {data && day && (
        <>
          <div className="chips" role="tablist" aria-label={t("train_title")}>
            {data.days.map((d) => (
              <button key={d.id} type="button" role="tab" aria-selected={d.index === day.index}
                      className={"chip" + (d.index === day.index ? " chip-on" : "")}
                      onClick={() => { haptic.select(); setSelected(d.index); setArmed(false); }}>
                {dayName(d, t)}{d.index === data.next_index && <span className="chip-badge">{t("train_next")}</span>}
              </button>
            ))}
          </div>

          <section className="card">
            <div className="train-day-head">
              <h2 className="editor-day-name">{dayName(day, t)}</h2>
              <span className="muted small">{t("train_minutes", { n: day.minutes })}</span>
            </div>
            <EnergyBar load={day.energy} t={t} />
          </section>

          <ol className="train-list">
            {day.exercises.map((ex, i) => {
              const status = activeHere && active ? active.items[i]?.status ?? "upcoming" : "upcoming";
              return (
                <li key={ex.exercise_id + i} className={"train-row train-" + status}>
                  <ExerciseImage still={ex.image} muscle={ex.muscle_group} size="thumb" />
                  <span className="exercise-text">
                    <span className="exercise-name">{ex.name}</span>
                    <span className="exercise-meta">{t("train_target", { sets: ex.sets, reps: repRange(ex, t) })}</span>
                    <span className="exercise-meta">
                      {ex.last.length ? t("train_last", { sets: fmtSets(ex.last, ex.equipment, ex.timed, t) }) : t("train_first_time")}
                    </span>
                  </span>
                  <span className={"status-pill status-" + status}>{t(("status_" + status) as TextKey)}</span>
                </li>
              );
            })}
          </ol>

          {!active && (
            <button type="button" className="button-primary train-start" disabled={busy} onClick={() => void start(false)}>
              {busy ? <span className="spinner spinner-small" /> : t("train_start")}
            </button>
          )}
          {active && !activeHere && (
            <button type="button" className={"button-link" + (armed ? " danger" : "")} disabled={busy}
                    onClick={() => {
                      if (!armed) { haptic.warning(); setArmed(true); return; }
                      void start(true);
                    }}>
              {armed ? t("editor_confirm") : t("train_start_new")}
            </button>
          )}
        </>
      )}
    </main>
  );
}
