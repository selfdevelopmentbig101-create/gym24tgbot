/*
 * Exercise picker overlay for "Add split": by muscle (grid -> that muscle's list)
 * or all exercises with a name search. Multi-select, confirm with "Done".
 * Local to the create screen, so leaving without Done keeps the previous selection.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ExerciseItem } from "../lib/api";
import {
  getAllExercises, getMuscles, getMuscleExercises, trainErrorKey, type MuscleGroup,
} from "../lib/trainApi";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Check, Close, Search } from "../components/Icons";
import { Thumb } from "../components/ExerciseRow";
import { ErrorCard, MuscleImage } from "./AllExercises";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;
type Mode = "muscle" | "all";

export function SplitExercisePicker({ t, locale, initial, max, onClose, onDone }: {
  t: T;
  locale: string;
  initial: ExerciseItem[];
  max: number;
  onClose: () => void;
  onDone: (items: ExerciseItem[]) => void;
}) {
  const [mode, setMode] = useState<Mode>("muscle");
  const [muscle, setMuscle] = useState<string | null>(null);
  const [muscles, setMuscles] = useState<MuscleGroup[] | null>(null);
  const [all, setAll] = useState<ExerciseItem[] | null>(null);
  const [muscleItems, setMuscleItems] = useState<ExerciseItem[] | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<TextKey | null>(null);
  const [picked, setPicked] = useState<ExerciseItem[]>(initial);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    setError(null);
    Promise.all([getAllExercises(), getMuscles()])
      .then(([list, groups]) => { setAll(list.items); setMuscles(groups.items); })
      .catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load, reloadKey]);

  useEffect(() => {
    if (!muscle) return;
    let live = true;
    setMuscleItems(null);
    setError(null);
    getMuscleExercises(muscle)
      .then((list) => { if (live) setMuscleItems(list.items); })
      .catch((e) => { if (live) setError(trainErrorKey(e)); });
    return () => { live = false; };
  }, [muscle, reloadKey]);

  function pick(next: Mode) {
    if (next === mode) return;
    haptic.select();
    setMode(next);
    setMuscle(null);
  }

  function toggle(item: ExerciseItem) {
    const on = picked.some((p) => p.id === item.id);
    if (!on && picked.length >= max) {
      haptic.warning();
      return;
    }
    haptic.select();
    setPicked((prev) => on ? prev.filter((p) => p.id !== item.id) : [...prev, item]);
  }

  const shownAll = useMemo(() => {
    const needle = q.trim().toLocaleLowerCase(locale);
    const items = [...(all ?? [])].sort((a, b) => a.name.localeCompare(b.name, locale));
    return needle ? items.filter((i) => i.name.toLocaleLowerCase(locale).includes(needle)) : items;
  }, [all, q, locale]);

  const shownMuscle = useMemo(
    () => [...(muscleItems ?? [])].sort((a, b) => a.name.localeCompare(b.name, locale)),
    [muscleItems, locale],
  );

  const loaded = all !== null && muscles !== null;

  return (
    <div className="picker" role="dialog" aria-modal="true" aria-label={t("split_pick_title")}>
      <header className="train-sub-head picker-head">
        <button type="button" className="round-button round-close" onClick={onClose}
                aria-label={t("close")}><Close /></button>
        <h1 className="screen-title left">{t("split_pick_title")}</h1>
        <span className="picker-count">{t("split_pick_selected", { n: picked.length })}</span>
      </header>

      <div className="picker-controls">
        <div className="segmented" role="tablist" aria-label={t("split_pick_title")}>
          <button type="button" role="tab" aria-selected={mode === "muscle"}
                  className={"segment" + (mode === "muscle" ? " segment-on" : "")}
                  onClick={() => pick("muscle")}>{t("exercises_by_muscle")}</button>
          <button type="button" role="tab" aria-selected={mode === "all"}
                  className={"segment" + (mode === "all" ? " segment-on" : "")}
                  onClick={() => pick("all")}>{t("exercises_all")}</button>
        </div>

        {mode === "all" && (
          <label className="search">
            <Search />
            <input type="search" value={q} placeholder={t("exercises_search")} enterKeyHint="search"
                   aria-label={t("exercises_search")} maxLength={60} onChange={(e) => setQ(e.target.value)} />
            {q && (
              <button type="button" className="search-clear" aria-label={t("clear")}
                      onClick={() => setQ("")}><Close /></button>
            )}
          </label>
        )}

        {mode === "muscle" && muscle && (
          <button type="button" className="button-link picker-back" onClick={() => setMuscle(null)}>
            {t("split_pick_muscles")}
          </button>
        )}
      </div>

      <div className="picker-body">
        {error && <ErrorCard t={t} error={error} onRetry={() => setReloadKey((n) => n + 1)} />}
        {!error && !loaded && <div className="spinner center-spinner" aria-label={t("loading")} />}

        {loaded && mode === "muscle" && !muscle && (
          muscles && muscles.length > 0 ? (
            <div className="muscle-grid">
              {muscles.map((m) => {
                const selected = picked.filter((p) => p.muscle_group === m.key).length;
                return (
                  <button key={m.key} type="button" className="muscle-card"
                          onClick={() => { haptic.tap(); setMuscle(m.key); }}>
                    <MuscleImage file={m.image} />
                    <span className="muscle-name">{t(("muscle_" + m.key) as TextKey)}</span>
                    <span className="muted small">
                      {selected > 0 ? t("split_pick_selected", { n: selected }) : t("muscle_count", { n: m.count })}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : <div className="empty"><p>{t("no_results")}</p></div>
        )}

        {loaded && mode === "muscle" && muscle && (
          <>
            {!muscleItems && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}
            {muscleItems && shownMuscle.length === 0 && (
              <div className="empty"><p>{t("muscle_none")}</p></div>
            )}
            {shownMuscle.length > 0 && (
              <div className="rows">
                {shownMuscle.map((item) => (
                  <PickRow key={item.id} item={item} t={t}
                           on={picked.some((p) => p.id === item.id)} onToggle={() => toggle(item)} />
                ))}
              </div>
            )}
          </>
        )}

        {loaded && mode === "all" && (
          <>
            {shownAll.length === 0 && (
              <div className="empty">
                <p>{t("no_results")}</p>
                {q && <button type="button" className="button-link" onClick={() => setQ("")}>{t("clear")}</button>}
              </div>
            )}
            {shownAll.length > 0 && (
              <div className="rows">
                {shownAll.map((item) => (
                  <PickRow key={item.id} item={item} t={t}
                           on={picked.some((p) => p.id === item.id)} onToggle={() => toggle(item)} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <div className="picker-footer">
        <button type="button" className="button-primary" onClick={() => { haptic.success(); onDone(picked); }}>
          {t("split_pick_done", { n: picked.length })}
        </button>
      </div>
    </div>
  );
}

function PickRow({ item, t, on, onToggle }: {
  item: ExerciseItem; t: T; on: boolean; onToggle: () => void;
}) {
  return (
    <button type="button" className={"exercise-row pick-row" + (on ? " pick-row-on" : "")}
            aria-pressed={on} onClick={onToggle}>
      <Thumb item={item} />
      <span className="exercise-text">
        <span className="exercise-name">{item.name}</span>
        <span className="exercise-meta">
          {t(("muscle_" + item.muscle_group) as TextKey)} · {t(("equip_" + item.equipment.replace(/ /g, "_")) as TextKey)}
        </span>
      </span>
      <span className={"pick-check" + (on ? " pick-check-on" : "")} aria-hidden>
        {on && <Check />}
      </span>
    </button>
  );
}
