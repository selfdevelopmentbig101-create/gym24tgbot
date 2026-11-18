/* Split detail: name, description, counts, exercises, and "Choose this split". */
import { useEffect, useState } from "react";
import { chooseSplit, getSplit, trainErrorKey, type Split } from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { repRange } from "../lib/trainText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import { setFlash } from "../lib/flash";
import type { TextKey } from "../i18n";
import { ExerciseImage } from "../components/ExerciseImage";
import { BackHeader, splitDescription } from "./Splits";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function SplitDetail({ id, t }: { id: number; t: T }) {
  const [split, setSplit] = useState<Split | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setError(null);
    getSplit(id).then(setSplit).catch((e) => setError(trainErrorKey(e)));
  };
  useEffect(load, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const back = () => goBack({ name: "splits" });
  useEffect(() => bindNativeBack(back), [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function choose() {
    if (!split || busy || split.active) return;
    setBusy(true);
    setError(null);
    try {
      await chooseSplit(split.id);
      haptic.success();
      setFlash(t("split_chosen", { name: dayName(split, t) }));
      goBack({ name: "splits" });
    } catch (e) {
      haptic.error();
      setError(trainErrorKey(e));
      setBusy(false);
    }
  }

  return (
    <main className="train split-detail">
      <BackHeader title={split ? dayName(split, t) : t("train_splits")} t={t} onBack={back} />

      {error && (
        <section className="card center" role="alert">
          <p>{t(error)}</p>
          {!split && <button type="button" className="button-primary" onClick={load}>{t("retry")}</button>}
        </section>
      )}
      {!split && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {split && (
        <>
          <section className={"card" + (split.active ? " split-active" : "")}>
            {split.active && <span className="split-badge">{t("split_active_badge")}</span>}
            <p className="split-desc">{splitDescription(split, t)}</p>
            <div className="split-stats">
              <span><b>{split.exercises.length}</b><small>{t("split_stat_exercises")}</small></span>
              <span><b>~{split.minutes}</b><small>{t("split_stat_minutes")}</small></span>
              <span><b>{split.energy.hard_sets}</b><small>{t("split_stat_hard_sets")}</small></span>
            </div>
          </section>

          {split.exercises.length === 0 ? (
            <div className="empty"><p>{t("split_empty")}</p></div>
          ) : (
            <ol className="train-list">
              {split.exercises.map((ex, i) => (
                <li key={ex.exercise_id + i}>
                  <button type="button" className="train-row split-ex"
                          onClick={() => { haptic.tap(); navigate({ name: "exercise", id: ex.exercise_id }); }}>
                    <ExerciseImage still={ex.image} muscle={ex.muscle_group} size="thumb" />
                    <span className="exercise-text">
                      <span className="exercise-name">{ex.name}</span>
                      <span className="exercise-meta">{t("train_target", { sets: ex.sets, reps: repRange(ex, t) })}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          )}

          <div className="split-footer">
            <button type="button" className="button-primary" disabled={busy || split.active || split.exercises.length === 0}
                    onClick={() => void choose()}>
              {busy ? <span className="spinner spinner-small" /> : split.active ? t("split_current") : t("split_choose")}
            </button>
          </div>
        </>
      )}
    </main>
  );
}
