/*
 * Day editor: training load (time, sets, muscles, warnings), then each exercise with
 * sets / reps / rest steppers, move, swap and remove. Add exercises from the library.
 * Rename, move or delete the day at the bottom. Every change is saved at once.
 */
import { useEffect, useState } from "react";
import {
  deleteDay, deleteDayExercise, getDay, getEnergy, getProgram, patchDay, patchDayExercise,
  substituteDayExercise, type Energy, type PlanDay, type PlanItem, type ProgramDetail,
} from "../lib/api";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, confirmDialog, haptic } from "../lib/telegram";
import { dayName, errorMessage, programName, repsText, type T } from "../lib/plan";
import type { TextKey } from "../i18n";
import { ArrowLeft, Bolt, Clock, Down, Minus, Pencil, Plus, Swap, Trash, Up } from "../components/Icons";
import { Thumb } from "../components/ExerciseRow";

export function DayEditor({ id, t }: { id: number; t: T }) {
  const [day, setDay] = useState<PlanDay | null>(null);
  const [program, setProgram] = useState<ProgramDetail | null>(null);
  const [energy, setEnergy] = useState<Energy | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh(next?: PlanDay) {
    const d = next ?? await getDay(id);
    setDay(d);
    const [p, e] = await Promise.all([getProgram(d.program_id), getEnergy(id)]);
    setProgram(p);
    setEnergy(e);
  }

  useEffect(() => {
    refresh().catch((e) => setError(errorMessage(e, t)));
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const back = () => goBack(day ? { name: "program", id: day.program_id } : { name: "plan" });
  useEffect(() => bindNativeBack(back), [id, day?.program_id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action: () => Promise<PlanDay | void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      await refresh(result || undefined);
      haptic.select();
    } catch (e) {
      haptic.error();
      setError(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (!day || !program) {
    return (
      <main className="detail">
        <header className="screen-header">
          <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}><ArrowLeft /></button>
        </header>
        {error ? <p className="muted center-text" role="alert">{error}</p> : <div className="spinner center-spinner" />}
      </main>
    );
  }

  const change = (item: PlanItem, body: Parameters<typeof patchDayExercise>[2]) =>
    run(() => patchDayExercise(day.id, item.id, body));

  async function saveName() {
    const name = (renaming ?? "").trim();
    setRenaming(null);
    if (name && name !== dayName(day!, t)) await run(async () => { await patchDay(day!.program_id, day!.id, { name }); });
  }

  async function removeDay() {
    if (!(await confirmDialog(t("confirm_delete_day")))) return;
    await run(async () => {
      await deleteDay(day!.program_id, day!.id);
      navigate({ name: "program", id: day!.program_id }, { replace: true });
    });
  }

  return (
    <main className="day-editor">
      <header className="screen-header">
        <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}><ArrowLeft /></button>
        <div className="screen-header-title stacked">
          <span className="muted small">{programName(program, t)} · {t("day_n", { n: day.index + 1 })}</span>
          {renaming === null ? (
            <button type="button" className="title-button" onClick={() => setRenaming(dayName(day, t))}>
              {dayName(day, t)} <Pencil />
            </button>
          ) : (
            <input className="text-input title-input" autoFocus maxLength={30} value={renaming}
                   aria-label={t("day_name")} onChange={(e) => setRenaming(e.target.value)}
                   onBlur={() => void saveName()} onKeyDown={(e) => { if (e.key === "Enter") void saveName(); }} />
          )}
        </div>
        <span className="round-spacer" />
      </header>

      {energy && <EnergyCard energy={energy} t={t} />}
      {error && <p className="field-error" role="alert">{error}</p>}

      <div className="stack">
        {day.exercises.length === 0 && <p className="muted center-text">{t("day_empty")}</p>}
        {day.exercises.map((item, index) => {
          const expanded = open === item.id;
          const step = item.timed ? 5 : 1;
          return (
            <section key={item.id} className={"card item" + (expanded ? " item-open" : "")}>
              <button type="button" className="item-head" aria-expanded={expanded}
                      onClick={() => { haptic.tap(); setOpen(expanded ? null : item.id); }}>
                <Thumb item={item.exercise} />
                <span className="day-line-text">
                  <span className="exercise-name">{item.exercise.name}</span>
                  <span className="exercise-meta">
                    {t("sets_reps", { sets: item.sets, reps: repsText(item, t) })} · {t("rest_s", { n: item.rest_seconds })}
                  </span>
                  {item.exercise.fits === false && <span className="tag-muted">{t("not_in_plan")}</span>}
                </span>
              </button>
              {expanded && (
                <div className="item-body">
                  <Stepper label={t("sets")} value={item.sets} min={1} max={10} disabled={busy}
                           onChange={(v) => void change(item, { sets: v })} />
                  <Stepper label={t(item.timed ? "min_seconds" : "min_reps")} value={item.rep_min} step={step}
                           min={item.timed ? 5 : 1} max={item.rep_max} disabled={busy}
                           onChange={(v) => void change(item, { rep_min: v })} />
                  <Stepper label={t(item.timed ? "max_seconds" : "max_reps")} value={item.rep_max} step={step}
                           min={item.rep_min} max={item.timed ? 600 : 100} disabled={busy}
                           onChange={(v) => void change(item, { rep_max: v })} />
                  <Stepper label={t("rest_label")} value={item.rest_seconds} step={15} min={0} max={600}
                           format={(v) => t("rest_s", { n: v })} disabled={busy}
                           onChange={(v) => void change(item, { rest_seconds: v })} />
                  <div className="item-actions">
                    <button type="button" className="icon-button" aria-label={t("move_up")} disabled={busy || index === 0}
                            onClick={() => void change(item, { position: index - 1 })}><Up /></button>
                    <button type="button" className="icon-button" aria-label={t("move_down")}
                            disabled={busy || index === day.exercises.length - 1}
                            onClick={() => void change(item, { position: index + 1 })}><Down /></button>
                    <button type="button" className="chip with-icon" disabled={busy}
                            onClick={() => void run(() => substituteDayExercise(day.id, item.id))}><Swap /> {t("swap")}</button>
                    <button type="button" className="chip danger with-icon" disabled={busy}
                            onClick={() => void run(() => deleteDayExercise(day.id, item.id))}><Trash /> {t("remove")}</button>
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>

      {day.exercises.length < 12 && (
        <button type="button" className="button-primary wide" onClick={() => { haptic.tap(); navigate({ name: "dayAdd", id: day.id }); }}>
          <Plus /> {t("add_exercise")}
        </button>
      )}

      <h2 className="section-label">{t("day_settings")}</h2>
      <div className="form-actions row">
        <button type="button" className="chip with-icon" disabled={busy || day.index === 0}
                onClick={() => void run(async () => { await patchDay(day.program_id, day.id, { position: day.index - 1 }); })}>
          <Up /> {t("move_day_earlier")}
        </button>
        <button type="button" className="chip with-icon" disabled={busy || day.index === program.days.length - 1}
                onClick={() => void run(async () => { await patchDay(day.program_id, day.id, { position: day.index + 1 }); })}>
          <Down /> {t("move_day_later")}
        </button>
        {program.days.length > 1 && (
          <button type="button" className="chip danger with-icon" disabled={busy} onClick={() => void removeDay()}>
            <Trash /> {t("delete_day")}
          </button>
        )}
      </div>
    </main>
  );
}

function Stepper({ label, value, min, max, step = 1, format = String, disabled, onChange }: {
  label: string; value: number; min: number; max: number; step?: number; format?: (v: number) => string;
  disabled?: boolean; onChange: (value: number) => void;
}) {
  return (
    <div className="stepper">
      <span className="stepper-label">{label}</span>
      <div className="stepper-controls">
        <button type="button" className="icon-button" aria-label={label + " −"} disabled={disabled || value - step < min}
                onClick={() => onChange(Math.max(min, value - step))}><Minus /></button>
        <span className="stepper-value" aria-live="polite">{format(value)}</span>
        <button type="button" className="icon-button" aria-label={label + " +"} disabled={disabled || value + step > max}
                onClick={() => onChange(Math.min(max, value + step))}><Plus /></button>
      </div>
    </div>
  );
}

function EnergyCard({ energy, t }: { energy: Energy; t: T }) {
  const muscle = (m: string) => t(("muscle_" + m) as TextKey);
  return (
    <section className="card energy" aria-label={t("training_load")}>
      <div className="energy-stats">
        <span><Clock /> {t("minutes_short", { n: energy.day.minutes })}</span>
        <span><Bolt /> {t("sets_n", { n: energy.day.sets })}</span>
      </div>
      {energy.day.muscles.length > 0 && (
        <div className="energy-muscles">
          {energy.day.muscles.slice(0, 6).map((m) => (
            <span key={m.muscle} className="muscle">{muscle(m.muscle)} <b>{m.sets}</b></span>
          ))}
        </div>
      )}
      {energy.warnings.map((w, i) => (
        <p key={i} className="energy-warning">
          {t(("warn_" + w.key) as TextKey, { n: w.value, muscle: w.muscle ? muscle(w.muscle) : "" })}
        </p>
      ))}
      <details className="energy-week">
        <summary>{t("weekly_volume")}</summary>
        {energy.week.map((m) => (
          <div key={m.muscle} className="volume-row">
            <span>{muscle(m.muscle)}</span>
            <span className="volume-bar"><span className={"vol-" + m.level} style={{ width: Math.min(100, (m.sets / 24) * 100) + "%" }} /></span>
            <span className={"vol-text vol-" + m.level}>{m.sets}</span>
          </div>
        ))}
        <p className="muted small">{t("weekly_volume_hint")}</p>
      </details>
    </section>
  );
}
