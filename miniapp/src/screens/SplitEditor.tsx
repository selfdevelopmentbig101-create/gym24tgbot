/*
 * Split editor (current program). Pick a day, see its energy bar, rename / move /
 * delete the day, change sets, reps and rest, reorder, substitute or remove
 * exercises, add exercises from the library, add a day, reset to default.
 *
 * Every change is saved right away and the server answers with the whole plan,
 * so what you see is always what is stored. Deleting asks for a second tap.
 */
import { useEffect, useState } from "react";
import { getExercises, type ExerciseItem } from "../lib/api";
import {
  addDay, addExercise, deleteDay, deleteEntry, getPlan, resetProgram, substituteEntry, updateDay, updateEntry,
  type EntryChanges, type PlanEntry, type PlanView,
} from "../lib/planApi";
import { dayName, planErrorKey, repsText } from "../lib/planText";
import { goBack } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ArrowLeft, ChevronRight, Close, Search, Swap } from "../components/Icons";
import { ArrowDown, ArrowUp, ChevronLeft, Pencil, Plus, Trash } from "../components/PlanIcons";
import { EnergyBar } from "../components/EnergyBar";
import { ExerciseImage } from "../components/ExerciseImage";
import { ExerciseRow } from "../components/ExerciseRow";
import { Stepper } from "../components/Stepper";
import { VolumeList } from "../components/VolumeList";
import "./plan.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function SplitEditor({ initialDay, t }: { initialDay?: number; t: T }) {
  const [plan, setPlan] = useState<PlanView | null>(null);
  const [dayId, setDayId] = useState<number | undefined>(initialDay);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<TextKey | null>(null);
  const [armed, setArmed] = useState<string | null>(null);      // waiting for the confirming 2nd tap
  const [renaming, setRenaming] = useState<string | null>(null);
  const [editing, setEditing] = useState<PlanEntry | null>(null);
  const [picker, setPicker] = useState(false);

  useEffect(() => {
    getPlan().then(setPlan).catch((e) => setError(planErrorKey(e)));
  }, []);
  useEffect(() => bindNativeBack(() => goBack({ name: "plan" })), []);

  const day = plan ? plan.days.find((d) => d.id === dayId) ?? plan.days[0] : undefined;

  /** Run one change; the answer is the new plan. Errors show at the top. */
  async function run(action: () => Promise<PlanView>): Promise<PlanView | null> {
    if (busy) return null;
    setBusy(true);
    setError(null);
    setArmed(null);
    try {
      const next = await action();
      setPlan(next);
      return next;
    } catch (e) {
      haptic.error();
      setError(planErrorKey(e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  /** First tap arms the button, the second one does it. */
  function confirmThen(key: string, action: () => void) {
    if (armed === key) action();
    else {
      haptic.warning();
      setArmed(key);
    }
  }

  return (
    <main className="editor">
      <header className="editor-header">
        <button type="button" className="round-button round-back" aria-label={t("back")}
                onClick={() => goBack({ name: "plan" })}><ArrowLeft /></button>
        <h1 className="editor-title">{t("editor_title")}</h1>
        <span className="round-spacer" />
      </header>

      {error && <p className="notice editor-error" role="alert">{t(error)}</p>}
      {!plan && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {plan && day && (
        <>
          <div className="chips" role="tablist" aria-label={t("editor_title")}>
            {plan.days.map((d) => (
              <button key={d.id} type="button" role="tab" aria-selected={d.id === day.id}
                      className={"chip" + (d.id === day.id ? " chip-on" : "")}
                      onClick={() => { haptic.select(); setDayId(d.id); setRenaming(null); setArmed(null); }}>
                {dayName(d, t)}
              </button>
            ))}
            <button type="button" className="chip chip-add" disabled={busy}
                    onClick={async () => {
                      haptic.tap();
                      const next = await run(() => addDay());
                      if (next) setDayId(next.days[next.days.length - 1]?.id);
                    }}>
              <Plus />{t("editor_add_day")}
            </button>
          </div>

          <section className="card editor-day">
            {renaming === null ? (
              <div className="editor-day-head">
                <h2 className="editor-day-name">{dayName(day, t)}</h2>
                <button type="button" className="icon-button" aria-label={t("editor_rename")}
                        onClick={() => setRenaming(day.title ?? dayName(day, t))}><Pencil /></button>
                <button type="button" className="icon-button" aria-label={t("editor_move_left")}
                        disabled={busy || day.index === 0}
                        onClick={() => void run(() => updateDay(day.id, { position: day.index - 1 }))}><ChevronLeft /></button>
                <button type="button" className="icon-button" aria-label={t("editor_move_right")}
                        disabled={busy || day.index === plan.days.length - 1}
                        onClick={() => void run(() => updateDay(day.id, { position: day.index + 1 }))}><ChevronRight /></button>
                <button type="button" className={"icon-button" + (armed === "day" ? " icon-button-danger" : "")}
                        aria-label={armed === "day" ? t("editor_confirm") : t("editor_delete_day")}
                        disabled={busy || plan.days.length <= 1}
                        onClick={() => confirmThen("day", async () => {
                          const next = await run(() => deleteDay(day.id));
                          if (next) setDayId(next.days[0]?.id);
                        })}><Trash /></button>
              </div>
            ) : (
              <form className="editor-rename" onSubmit={async (e) => {
                e.preventDefault();
                const next = await run(() => updateDay(day.id, { title: renaming }));
                if (next) setRenaming(null);
              }}>
                <input value={renaming} maxLength={30} autoFocus aria-label={t("editor_day_name")}
                       onChange={(e) => setRenaming(e.target.value)} />
                <button type="submit" className="button-primary button-small" disabled={busy}>{t("editor_save")}</button>
                <button type="button" className="button-link" onClick={() => setRenaming(null)}>{t("editor_cancel")}</button>
              </form>
            )}
            {armed === "day" && <p className="small editor-confirm">{t("editor_confirm")}</p>}
            <EnergyBar load={day.energy} t={t} />
          </section>

          <ol className="editor-list">
            {day.exercises.map((entry, i) => (
              <li key={entry.id} className="editor-entry">
                <button type="button" className="editor-entry-main" onClick={() => { haptic.tap(); setEditing(entry); }}>
                  <ExerciseImage still={entry.image} muscle={entry.muscle_group ?? "core"} size="thumb" />
                  <span className="exercise-text">
                    <span className="exercise-name">{entry.name}</span>
                    <span className="exercise-meta">
                      {t("editor_sets_reps", { sets: entry.sets, reps: repsText(entry, t) })} · {t("editor_rest_value", { n: entry.rest_seconds })}
                    </span>
                    {!entry.fits && <span className="tag-muted">{t("editor_not_fit")}</span>}
                  </span>
                </button>
                <div className="editor-entry-actions">
                  <button type="button" className="icon-button" aria-label={t("editor_move_up")} disabled={busy || i === 0}
                          onClick={() => void run(() => updateEntry(entry.id, { position: i - 1 }))}><ArrowUp /></button>
                  <button type="button" className="icon-button" aria-label={t("editor_move_down")}
                          disabled={busy || i === day.exercises.length - 1}
                          onClick={() => void run(() => updateEntry(entry.id, { position: i + 1 }))}><ArrowDown /></button>
                  <button type="button" className="icon-button" aria-label={t("editor_substitute")} disabled={busy}
                          onClick={async () => {
                            haptic.tap();
                            if (await run(() => substituteEntry(entry.id))) haptic.success();
                          }}><Swap /></button>
                  <button type="button"
                          className={"icon-button" + (armed === `entry-${entry.id}` ? " icon-button-danger" : "")}
                          aria-label={armed === `entry-${entry.id}` ? t("editor_confirm") : t("editor_remove")}
                          disabled={busy || day.exercises.length <= 1}
                          onClick={() => confirmThen(`entry-${entry.id}`, () => void run(() => deleteEntry(entry.id)))}>
                    <Trash />
                  </button>
                </div>
                {armed === `entry-${entry.id}` && <p className="small editor-confirm">{t("editor_confirm")}</p>}
              </li>
            ))}
          </ol>

          <button type="button" className="button-secondary editor-add" disabled={busy}
                  onClick={() => { haptic.tap(); setPicker(true); }}>
            <Plus />{t("editor_add_exercise")}
          </button>

          <VolumeList volume={plan.weekly_volume} limits={plan.limits} t={t} />

          <section className="editor-reset">
            <button type="button" className={"button-link" + (armed === "reset" ? " danger" : "")} disabled={busy}
                    onClick={() => confirmThen("reset", async () => {
                      const next = await run(() => resetProgram(plan.program.id));
                      if (next) {
                        haptic.success();
                        setDayId(next.days[0]?.id);
                      }
                    })}>
              {armed === "reset" ? t("editor_confirm") : t("editor_reset")}
            </button>
            <p className="muted small">{t("editor_reset_hint")}</p>
          </section>
        </>
      )}

      {editing && (
        <EntrySheet entry={editing} t={t} busy={busy} onClose={() => setEditing(null)}
                    onSave={async (changes) => {
                      const next = await run(() => updateEntry(editing.id, changes));
                      if (next) {
                        haptic.success();
                        setEditing(null);
                      }
                    }} />
      )}
      {picker && day && (
        <ExercisePicker t={t} exclude={new Set(day.exercises.map((e) => e.exercise_id))}
                        onClose={() => setPicker(false)}
                        onPick={async (exerciseId) => {
                          const next = await run(() => addExercise(day.id, exerciseId));
                          if (next) {
                            haptic.success();
                            setPicker(false);
                          }
                        }} />
      )}
    </main>
  );
}

/** Sets, reps (or seconds for holds) and rest for one exercise. */
function EntrySheet({ entry, t, busy, onClose, onSave }: {
  entry: PlanEntry; t: T; busy: boolean; onClose: () => void; onSave: (changes: EntryChanges) => void;
}) {
  const [sets, setSets] = useState(entry.sets);
  const [low, setLow] = useState(entry.rep_min);
  const [high, setHigh] = useState(entry.rep_max);
  const [rest, setRest] = useState(entry.rest_seconds);
  const step = entry.timed ? 5 : 1;
  const floor = entry.timed ? 10 : 1;
  const ceiling = entry.timed ? 180 : 50;
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={t("editor_edit_exercise")}
           onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        <h2 className="sheet-title">{entry.name}</h2>
        <Stepper label={t("editor_sets")} value={sets} min={1} max={10} onChange={setSets} />
        <Stepper label={entry.timed ? t("editor_seconds_min") : t("editor_reps_min")} value={low}
                 min={floor} max={high} step={step} onChange={setLow} />
        <Stepper label={entry.timed ? t("editor_seconds_max") : t("editor_reps_max")} value={high}
                 min={low} max={ceiling} step={step} onChange={setHigh} />
        <Stepper label={t("editor_rest")} value={rest} min={15} max={600} step={15}
                 format={(n) => t("editor_rest_value", { n })} onChange={setRest} />
        <div className="sheet-actions">
          <button type="button" className="button-link" onClick={onClose}>{t("editor_cancel")}</button>
          <button type="button" className="button-primary" disabled={busy}
                  onClick={() => onSave({ sets, rep_min: low, rep_max: high, rest_seconds: rest })}>
            {t("editor_save")}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Library search (name or primary/secondary muscle) to add an exercise to the day. */
function ExercisePicker({ t, exclude, onClose, onPick }: {
  t: T; exclude: Set<string>; onClose: () => void; onPick: (exerciseId: string) => void;
}) {
  const [typed, setTyped] = useState("");
  const [items, setItems] = useState<ExerciseItem[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      setFailed(false);
      getExercises({ q: typed, muscle: null, equipment: null, difficulty: null, home: false, fits: false })
        .then((result) => { if (live) setItems(result.items); })
        .catch(() => { if (live) setFailed(true); });
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [typed]);

  const shown = (items ?? []).filter((item) => !exclude.has(item.id));
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet sheet-tall" role="dialog" aria-modal="true" aria-label={t("editor_add_exercise")}
           onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        <h2 className="sheet-title">{t("editor_add_exercise")}</h2>
        <label className="search">
          <Search />
          <input type="search" value={typed} placeholder={t("editor_search")} aria-label={t("editor_search")}
                 maxLength={60} enterKeyHint="search" onChange={(e) => setTyped(e.target.value)} />
          {typed && (
            <button type="button" className="search-clear" aria-label={t("clear")} onClick={() => setTyped("")}>
              <Close />
            </button>
          )}
        </label>
        {failed && <p className="muted center-text" role="alert">{t("error_generic")}</p>}
        {!items && !failed && <div className="spinner center-spinner" aria-label={t("loading")} />}
        <div className="rows picker-rows">
          {shown.map((item) => <ExerciseRow key={item.id} item={item} t={t} onOpen={() => onPick(item.id)} />)}
        </div>
      </div>
    </div>
  );
}
