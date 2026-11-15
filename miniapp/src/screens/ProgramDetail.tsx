/*
 * Program details (reference image 2, "Training Plan"): week progress, focus, rep
 * range, schedule, then each day with its exercises. Actions: make current, edit,
 * add a day, reset (built-in programs), delete (saved programs).
 */
import { useEffect, useState } from "react";
import {
  activateProgram, addDay, deleteProgram, getProgram, resetProgram, type ProgramDetail as Detail,
} from "../lib/api";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, confirmDialog, haptic } from "../lib/telegram";
import { dayName, errorMessage, formatDate, percent, programName, repsText, type T } from "../lib/plan";
import type { TextKey } from "../i18n";
import { ArrowLeft, ChevronRight, Clock, Pencil, Plus, Reset, Trash } from "../components/Icons";
import { Thumb } from "../components/ExerciseRow";

const REP_GUIDE: Record<string, string> = { strength: "4–6", hypertrophy: "8–12", endurance: "15–20" };

export function ProgramDetail({ id, t, locale }: { id: number; t: T; locale: string }) {
  const [p, setP] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    getProgram(id).then((d) => { if (live) setP(d); }).catch((e) => { if (live) setError(errorMessage(e, t)); });
    const saved = sessionStorage.getItem("gym24.notice");
    if (saved) {
      setNotice(t(("notice_" + saved) as TextKey));
      sessionStorage.removeItem("gym24.notice");
    }
    return () => { live = false; };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const back = () => goBack({ name: "programs" });
  useEffect(() => bindNativeBack(back), [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action: () => Promise<Detail | null>, done?: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      if (result) setP(result);
      haptic.success();
      if (done) setNotice(t(done as TextKey));
    } catch (e) {
      haptic.error();
      setError(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!p || !(await confirmDialog(t("confirm_delete_program")))) return;
    await run(async () => { await deleteProgram(p.id); navigate({ name: "programs" }, { replace: true }); return null; });
  }

  async function reset() {
    if (!p || !(await confirmDialog(t("confirm_reset_program")))) return;
    await run(() => resetProgram(p.id), "notice_reset");
  }

  if (!p) {
    return (
      <main className="detail">
        <header className="screen-header">
          <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}><ArrowLeft /></button>
        </header>
        {error ? <p className="muted center-text" role="alert">{error}</p> : <div className="spinner center-spinner" />}
      </main>
    );
  }

  const pct = percent(p.completed, p.total);
  return (
    <main className="program-detail">
      <header className="screen-header">
        <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}><ArrowLeft /></button>
        <h1 className="screen-header-title">{t("training_plan")}</h1>
        <button type="button" className="round-button round-close" aria-label={t("edit_program")}
                onClick={() => { haptic.tap(); navigate({ name: "programEdit", id: p.id }); }}><Pencil /></button>
      </header>

      <section className="hero">
        {p.is_current && <span className="badge-current">{t("current")}</span>}
        <h2 className="hero-title">{programName(p, t)}</h2>
        <p className="muted small">{t(("tgoal_" + p.goal + "_hint") as TextKey)}</p>
        {p.is_current && (
          <>
            <div className="program-progress">
              <span>{t("week_of", { n: p.week ?? 1, total: p.weeks })}</span>
              <span>{t("percent_done", { n: pct })}</span>
            </div>
            <div className="segments-bar" aria-hidden>
              {Array.from({ length: Math.min(p.total, 60) }, (_, i) => (
                <span key={i} className={i < Math.round((pct / 100) * Math.min(p.total, 60)) ? "on" : ""} />
              ))}
            </div>
            {p.started_on && p.ends_on && (
              <div className="program-dates">
                <span>{t("started", { date: formatDate(p.started_on, locale) })}</span>
                <span>{t("ends", { date: formatDate(p.ends_on, locale) })}</span>
              </div>
            )}
          </>
        )}
      </section>

      <div className="tiles">
        <div className="tile"><span className="tile-label">{t("focus")}</span><span className="tile-value">{t(("tgoal_" + p.goal) as TextKey)}</span></div>
        <div className="tile"><span className="tile-label">{t("rep_range")}</span><span className="tile-value">{REP_GUIDE[p.goal]}</span></div>
        <div className="tile"><span className="tile-label">{t("schedule")}</span><span className="tile-value">{t("per_week", { n: p.workouts_per_week })}</span></div>
        <div className="tile"><span className="tile-label">{t("duration")}</span><span className="tile-value">{t("weeks_n", { n: p.weeks })}</span></div>
      </div>

      {notice && <p className="notice notice-ok" role="status">{notice}</p>}
      {error && <p className="field-error" role="alert">{error}</p>}

      {!p.is_current && (
        <button type="button" className="button-primary wide" disabled={busy}
                onClick={() => void run(() => activateProgram(p.id), "notice_activated")}>
          {t("make_current")}
        </button>
      )}

      <h2 className="section-label">{t("workout_days")}</h2>
      <div className="stack">
        {p.days.map((day) => (
          <button key={day.id} type="button" className="card day-card"
                  onClick={() => { haptic.tap(); navigate({ name: "day", id: day.id }); }}>
            <span className="day-card-head">
              <span>
                <span className="day-card-index">{t("day_n", { n: day.index + 1 })}</span>
                <span className="day-card-name">{dayName(day, t)}</span>
              </span>
              <span className="day-card-meta">
                {day.exercises.length > 0 && <><Clock /> {t("minutes_short", { n: day.minutes })}</>}
                <ChevronRight />
              </span>
            </span>
            {day.exercises.length === 0 && <span className="muted small">{t("day_empty")}</span>}
            {day.exercises.map((item) => (
              <span key={item.id} className="day-line">
                <Thumb item={item.exercise} />
                <span className="day-line-text">
                  <span className="exercise-name">{item.exercise.name}</span>
                  <span className="exercise-meta">{t("sets_reps", { sets: item.sets, reps: repsText(item, t) })}</span>
                </span>
              </span>
            ))}
          </button>
        ))}
      </div>

      <div className="form-actions">
        {p.days.length < 7 && (
          <button type="button" className="button-secondary" disabled={busy}
                  onClick={() => void run(() => addDay(p.id), "notice_day_added")}><Plus /> {t("add_day")}</button>
        )}
        {p.kind === "template" && (
          <button type="button" className="button-link with-icon" disabled={busy} onClick={() => void reset()}>
            <Reset /> {t("reset_program")}
          </button>
        )}
        {!p.is_current && (
          <button type="button" className="button-link danger with-icon" disabled={busy} onClick={() => void remove()}>
            <Trash /> {t("delete_program")}
          </button>
        )}
      </div>
    </main>
  );
}
