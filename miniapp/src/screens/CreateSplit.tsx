/*
 * Train > Splits > New split: name, chosen exercises with sets × reps, then Save.
 * "Add exercises" opens a full-screen picker (by muscle / all + search) right here,
 * so the draft survives while the user picks.
 */
import { useCallback, useEffect, useState } from "react";
import type { ExerciseItem } from "../lib/api";
import { createSplit, trainErrorKey } from "../lib/trainApi";
import { goBack } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import { setFlash } from "../lib/flash";
import type { TextKey } from "../i18n";
import { Close } from "../components/Icons";
import { Plus } from "../components/PlanIcons";
import { Thumb } from "../components/ExerciseRow";
import { BackHeader } from "./Splits";
import { SplitExercisePicker } from "./SplitExercisePicker";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

interface DraftExercise {
  exercise: ExerciseItem;
  sets: number;
  repMin: number;
  repMax: number;
}

/** services/program_rules.py: MAX_EXERCISES_PER_DAY. */
const MAX_EXERCISES = 12;
const DEFAULT_SETS = 3;
const DEFAULT_REP_MIN = 8;
const DEFAULT_REP_MAX = 12;

export function CreateSplit({ t, locale }: { t: T; locale: string }) {
  const [name, setName] = useState("");
  const [items, setItems] = useState<DraftExercise[]>([]);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<TextKey | null>(null);

  const back = useCallback(() => {
    if (picking) setPicking(false);
    else goBack({ name: "splits" });
  }, [picking]);
  useEffect(() => bindNativeBack(back), [back]);

  function update(id: string, change: (item: DraftExercise) => DraftExercise) {
    setItems((prev) => prev.map((item) => item.exercise.id === id ? change(item) : item));
  }

  function setSets(id: string, delta: number) {
    haptic.select();
    update(id, (item) => ({ ...item, sets: Math.max(1, Math.min(10, item.sets + delta)) }));
  }

  function shiftReps(id: string, delta: number) {
    haptic.select();
    update(id, (item) => {
      const width = item.repMax - item.repMin;
      const low = Math.min(Math.max(item.repMin + delta, 1), 50 - width);
      return { ...item, repMin: low, repMax: low + width };
    });
  }

  function remove(id: string) {
    haptic.tap();
    setItems((prev) => prev.filter((item) => item.exercise.id !== id));
  }

  function donePicking(picked: ExerciseItem[]) {
    setItems((prev) => {
      const old = new Map(prev.map((item) => [item.exercise.id, item]));
      return picked.map((exercise) => old.get(exercise.id) ?? {
        exercise, sets: DEFAULT_SETS, repMin: DEFAULT_REP_MIN, repMax: DEFAULT_REP_MAX,
      });
    });
    setPicking(false);
  }

  const title = name.trim();
  const canSave = title.length > 0 && items.length > 0 && !busy;

  async function save() {
    if (!canSave) return;
    setBusy(true);
    setError(null);
    try {
      await createSplit(title, items.map((item) => ({
        exercise_id: item.exercise.id,
        sets: item.sets,
        rep_min: item.repMin,
        rep_max: item.repMax,
      })));
      haptic.success();
      setFlash(t("split_created", { name: title }));
      goBack({ name: "splits" });
    } catch (e) {
      haptic.error();
      setError(trainErrorKey(e));
      setBusy(false);
    }
  }

  return (
    <main className="train split-create">
      <BackHeader title={t("split_new")} t={t} onBack={back} />

      <label className="split-name">
        <span className="split-name-row">
          <span className="field-label">{t("split_name")}</span>
          <span className="muted small">{name.length}/30</span>
        </span>
        <input type="text" value={name} maxLength={30} enterKeyHint="done"
               placeholder={t("split_name_placeholder")} aria-label={t("split_name")}
               onChange={(e) => setName(e.target.value)} />
      </label>

      <div className="split-selected-head">
        <h2 className="section-label">{t("split_exercises")}</h2>
        <span className="muted small">{items.length}/{MAX_EXERCISES}</span>
      </div>

      {items.length === 0 ? (
        <div className="empty"><p>{t("split_no_exercises")}</p></div>
      ) : (
        <ul className="split-ex-list">
          {items.map(({ exercise, sets, repMin, repMax }) => (
            <li key={exercise.id} className="split-ex-item">
              <div className="split-ex-head">
                <Thumb item={exercise} />
                <span className="exercise-text">
                  <span className="exercise-name">{exercise.name}</span>
                  <span className="exercise-meta">
                    {t(("muscle_" + exercise.muscle_group) as TextKey)}
                  </span>
                </span>
                <button type="button" className="split-ex-remove" aria-label={t("split_remove")}
                        onClick={() => remove(exercise.id)}><Close /></button>
              </div>

              <div className="split-ex-config">
                <div className="mini-stepper">
                  <span className="mini-label">{t("split_sets")}</span>
                  <div className="mini-controls">
                    <button type="button" aria-label={t("split_sets") + " −"} disabled={sets <= 1}
                            onClick={() => setSets(exercise.id, -1)}>−</button>
                    <b>{sets}</b>
                    <button type="button" aria-label={t("split_sets") + " +"} disabled={sets >= 10}
                            onClick={() => setSets(exercise.id, 1)}>+</button>
                  </div>
                </div>
                <div className="mini-stepper">
                  <span className="mini-label">{t("split_reps")}</span>
                  <div className="mini-controls">
                    <button type="button" aria-label={t("split_reps") + " −"} disabled={repMin <= 1}
                            onClick={() => shiftReps(exercise.id, -1)}>−</button>
                    <b>{repMin}–{repMax}</b>
                    <button type="button" aria-label={t("split_reps") + " +"} disabled={repMax >= 50}
                            onClick={() => shiftReps(exercise.id, 1)}>+</button>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className="button-secondary split-add-ex" disabled={items.length >= MAX_EXERCISES}
              onClick={() => { haptic.tap(); setPicking(true); }}>
        <Plus />{t("split_add_exercises")}
      </button>

      {error && <section className="card center" role="alert"><p>{t(error)}</p></section>}

      <div className="split-save">
        <button type="button" className="button-primary" disabled={!canSave} onClick={() => void save()}>
          {busy ? <span className="spinner spinner-small" /> : t("split_save")}
        </button>
      </div>

      {picking && (
        <SplitExercisePicker t={t} locale={locale} initial={items.map((item) => item.exercise)}
                             max={MAX_EXERCISES} onClose={() => setPicking(false)} onDone={donePicking} />
      )}
    </main>
  );
}
