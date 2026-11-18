/*
 * Train tab home: two big cards, Splits and All exercises, plus a shortcut to the
 * active split's session (or the workout in progress).
 */
import { useCallback, useEffect, useState } from "react";
import { getSplits, trainErrorKey, type SplitList } from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ChevronRight, Dumbbell, Search } from "../components/Icons";
import { Calendar } from "../components/PlanIcons";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function TrainHome({ t }: { t: T }) {
  const [data, setData] = useState<SplitList | null>(null);
  const [error, setError] = useState<TextKey | null>(null);

  const load = useCallback(() => {
    setError(null);
    getSplits().then(setData).catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load]);
  useEffect(() => bindNativeBack(null), []); // a tab: no Back button

  const active = data?.splits.find((s) => s.active) ?? null;

  return (
    <main className="train">
      <h1 className="screen-title left">{t("train_title")}</h1>

      <div className="train-home-cards">
        <button type="button" className="train-home-card" onClick={() => { haptic.tap(); navigate({ name: "splits" }); }}>
          <span className="train-home-icon"><Calendar /></span>
          <span className="train-home-text">
            <span className="train-home-title">{t("train_splits")}</span>
            <span className="muted small">{t("train_splits_hint")}</span>
          </span>
          <ChevronRight />
        </button>
        <button type="button" className="train-home-card" onClick={() => { haptic.tap(); navigate({ name: "exercises" }); }}>
          <span className="train-home-icon"><Search /></span>
          <span className="train-home-text">
            <span className="train-home-title">{t("train_all_exercises")}</span>
            <span className="muted small">{t("train_all_exercises_hint")}</span>
          </span>
          <ChevronRight />
        </button>
      </div>

      {error && (
        <section className="card center" role="alert">
          <p>{t(error)}</p>
          <button type="button" className="button-primary" onClick={load}>{t("retry")}</button>
        </section>
      )}
      {!data && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {data && active && (
        <section className="card train-active split-active">
          <p className="plan-eyebrow">{data.workout_active ? t("train_in_progress") : t("train_active_split")}</p>
          <h2 className="plan-program-name">{dayName(active, t)}</h2>
          <p className="muted small">
            {t("split_meta", { n: active.exercises.length, min: active.minutes })}
          </p>
          <button type="button" className="button-primary"
                  onClick={() => { haptic.tap(); navigate({ name: data.workout_active ? "workoutGuided" : "workoutSession" }); }}>
            <Dumbbell />{data.workout_active ? t("train_continue") : t("train_open_session")}
          </button>
        </section>
      )}
    </main>
  );
}
