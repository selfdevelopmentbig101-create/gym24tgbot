/*
 * Live logger for the workout in progress.
 *
 * - The next set is pre-filled (last set today, else the overload suggestion), so
 *   logging a set is 1 tap on ✓; adjusting weight or reps first is 2-3 taps.
 * - Last time's numbers sit beside the next set; "+2.5 kg" and "Same as last time".
 * - Warm-up sets (toggle) never count for PRs, progression or the energy bar.
 * - Optional RPE, a short note and a superset group (A1/A2...) per exercise.
 * - Rest timer bar after each working set (skip, +15 s, pause) with a vibration
 *   when it ends. Inside a superset you go straight to the next exercise and rest
 *   after the round.
 * - New PRs are celebrated; Finish shows a summary with next-time suggestions.
 * The workout lives on the server, so it can be continued in the bot and back.
 */
import { useEffect, useState } from "react";
import {
  deleteSet, editSet, finishWorkout, getTrain, logSet, substituteItem, trainErrorKey, updateItem,
  type LoggedSet, type Summary, type WorkoutItem, type WorkoutView,
} from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { clock, fmtSet, fmtSets, hintText, repRange } from "../lib/trainText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ExerciseImage } from "../components/ExerciseImage";
import { ArrowLeft, Check, ChevronRight, Swap } from "../components/Icons";
import { Bolt, ChevronLeft, Warn } from "../components/PlanIcons";
import { Stepper } from "../components/Stepper";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;
type Draft = { weight: number; reps: number; rpe: number | null };
type Rest = { endsAt: number; total: number; pausedLeft: number | null };

const RPE_STEPS: (number | null)[] = [null, 6, 7, 8, 9, 10];
const WEIGHT_STEP = 2.5;
const GROUPS: (string | null)[] = [null, "A", "B", "C", "D"];

function workingSets(item: WorkoutItem): LoggedSet[] {
  return item.logged.filter((s) => !s.warmup);
}

/** What the next set is pre-filled with. */
function draftFor(item: WorkoutItem): Draft {
  const done = workingSets(item);
  const last = done[done.length - 1];
  if (last) return { weight: last.weight_kg, reps: last.reps, rpe: null };
  if (item.suggestion) return { weight: item.suggestion.weight_kg, reps: item.suggestion.reps, rpe: null };
  return { weight: 0, reps: item.rep_min, rpe: null };
}

export function Logger({ t }: { t: T }) {
  const [ws, setWs] = useState<WorkoutView | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<TextKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>({ weight: 0, reps: 8, rpe: null });
  const [warmup, setWarmup] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [rest, setRest] = useState<Rest | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [editing, setEditing] = useState<LoggedSet | null>(null);
  const [armedFinish, setArmedFinish] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    getTrain()
      .then((d) => (d.active ? setWs(d.active) : setMissing(true)))
      .catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(() => bindNativeBack(() => goBack({ name: "workout" })), []);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!armedFinish) return;
    const timer = setTimeout(() => setArmedFinish(false), 4000);
    return () => clearTimeout(timer);
  }, [armedFinish]);

  const index = ws ? Math.min(selected ?? ws.current_index, ws.items.length - 1) : 0;
  const item = ws?.items[index];
  const loggedCount = item?.logged.length ?? 0;

  // New pre-filled values when the exercise changes or a set is logged.
  useEffect(() => {
    if (!item) return;
    setDraft((d) => ({ ...draftFor(item), rpe: d.rpe }));
    setNoteText(item.note ?? "");
  }, [ws?.id, index, loggedCount, item?.exercise_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Rest timer: count down from an end time (survives re-renders and the phone sleeping).
  const restLeft = rest === null ? 0 : rest.pausedLeft ?? Math.max(0, Math.ceil((rest.endsAt - now) / 1000));
  useEffect(() => {
    if (rest && rest.pausedLeft === null && rest.endsAt <= now) {
      haptic.success();                  // the "time is up" buzz
      setToast(t("logger_rest_over"));
      setRest(null);
    }
  }, [now, rest, t]);

  async function run<R>(action: () => Promise<R>): Promise<R | null> {
    if (busy) return null;
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (e) {
      haptic.error();
      setError(trainErrorKey(e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  function startRest(seconds: number) {
    if (seconds > 0) setRest({ endsAt: Date.now() + seconds * 1000, total: seconds, pausedLeft: null });
  }

  /** After a working set: next superset exercise (no rest inside a round), or rest and move on. */
  function afterWorkingSet(next: WorkoutView, at: number) {
    const current = next.items[at];
    if (!current) return;
    if (current.group) {
      const members = next.items.filter((i) => i.group === current.group);
      const pos = members.findIndex((i) => i.index === at);
      const later = members.slice(pos + 1).find((i) => i.status !== "completed");
      if (later) {
        setSelected(later.index);
        setToast(t("logger_superset_next", { name: later.name }));
        return;
      }
      const first = members.find((i) => i.status !== "completed");
      setSelected(first ? first.index : next.current_index);
    } else if (current.status === "completed") {
      setSelected(next.current_index);
    }
    startRest(current.rest_seconds);
  }

  async function onLog() {
    if (!ws || !item) return;
    const result = await run(() => logSet(ws.id, {
      index, weight_kg: item.timed ? 0 : draft.weight, reps: draft.reps, rpe: draft.rpe, warmup,
    }));
    if (!result) return;
    haptic.tap();
    setWs(result.workout);
    const logged = result.set;
    if (logged.pr && logged.estimate !== null && logged.previous_best !== null) {
      haptic.success();
      setToast(t("logger_pr", { value: logged.estimate.toFixed(1), previous: logged.previous_best.toFixed(1) }));
    }
    if (!warmup) afterWorkingSet(result.workout, index);
  }

  async function onFinish() {
    if (!ws) return;
    if (!armedFinish) {
      haptic.warning();
      setArmedFinish(true);
      return;
    }
    const result = await run(() => finishWorkout(ws.id));
    if (result) {
      haptic.success();
      setRest(null);
      setSummary(result);
    }
  }

  async function saveNote() {
    if (!ws || !item || noteText.trim() === (item.note ?? "")) return;
    const next = await run(() => updateItem(ws.id, index, { note: noteText }));
    if (next) setWs(next);
  }

  async function chooseGroup(group: string | null) {
    if (!ws || !item || item.group === group) return;
    haptic.select();
    const next = await run(() => updateItem(ws.id, index, { group }));
    if (next) setWs(next);
  }

  async function onSwap() {
    if (!ws) return;
    const next = await run(() => substituteItem(ws.id, index));
    if (next) {
      haptic.success();
      setWs(next);
    }
  }

  if (summary) return <SummaryView summary={summary} t={t} />;

  if (missing || (error && !ws)) {
    return (
      <main className="logger">
        <section className="card center" role="alert">
          <p>{error ? t(error) : t("logger_no_workout")}</p>
          <button type="button" className="button-primary"
                  onClick={() => navigate({ name: "workout" }, { replace: true })}>{t("logger_open_train")}</button>
        </section>
      </main>
    );
  }
  if (!ws || !item) return <main className="logger"><div className="spinner center-spinner" aria-label={t("loading")} /></main>;

  const done = workingSets(item);
  const nextNumber = done.length + 1;
  const previousForNext = item.previous[done.length] ?? item.previous[item.previous.length - 1];
  const hint = hintText(item.suggestion, t);
  const allDone = ws.items.every((i) => i.status === "completed");

  return (
    <main className="logger">
      <header className="logger-header">
        <button type="button" className="round-button round-back" aria-label={t("back")}
                onClick={() => goBack({ name: "workout" })}><ArrowLeft /></button>
        <div className="logger-title">
          <h1 className="editor-title">{dayName(ws, t)}</h1>
          <span className="muted small">{clock((now - Date.parse(ws.started_at)) / 1000)}</span>
        </div>
        <button type="button" className={"button-primary button-small" + (armedFinish ? " logger-armed" : "")}
                disabled={busy} onClick={() => void onFinish()}>
          {armedFinish ? t("logger_finish_confirm") : t("logger_finish")}
        </button>
      </header>

      <section className="logger-energy" aria-label={t("logger_energy")}>
        <div className="energy-head">
          <span className="energy-label"><Bolt />{t("logger_energy")}</span>
          <span className="energy-value">{t("logger_energy_left", { n: ws.energy.left })}</span>
        </div>
        <div className="energy-track" role="meter" aria-label={t("logger_energy")}
             aria-valuemin={0} aria-valuemax={100} aria-valuenow={ws.energy.left}>
          <span style={{ width: `${ws.energy.left}%` }} />
        </div>
        {ws.energy.warnings.length > 0 && (
          <p className="small logger-warning"><Warn />{t("energy_warning")} {t("not_medical_advice")}</p>
        )}
      </section>

      {error && <p className="notice editor-error" role="alert">{t(error)}</p>}

      <div className="chips logger-strip" role="tablist">
        {ws.items.map((it) => (
          <button key={it.index} type="button" role="tab" aria-selected={it.index === index}
                  className={`chip logger-chip logger-chip-${it.status}` + (it.index === index ? " chip-on" : "")}
                  onClick={() => { haptic.select(); setSelected(it.index); }}>
            {it.status === "completed" && <Check />}
            {it.label && <b className="superset-label">{it.label}</b>}
            {it.name}
          </button>
        ))}
      </div>

      <section className="card logger-card">
        <div className="logger-ex-head">
          <ExerciseImage still={item.image} muscle={item.muscle_group} size="thumb" />
          <div className="exercise-text">
            <span className="exercise-name">
              {item.label && <b className="superset-label">{item.label}</b>}{item.name}
            </span>
            <span className="exercise-meta">
              {t("logger_target", { sets: item.sets, reps: repRange(item, t), rest: item.rest_seconds })}
            </span>
          </div>
        </div>
        {hint && <p className="logger-hint">{hint}</p>}
        {item.previous.length > 0 && (
          <p className="muted small">{t("logger_previous_sets")}: {fmtSets(item.previous, item.equipment, item.timed, t)}</p>
        )}

        {item.logged.length > 0 && (
          <ol className="set-list">
            {item.logged.map((s) => (
              <li key={s.id}>
                <button type="button" className={"set-row" + (s.warmup ? " set-warmup" : "")}
                        aria-label={t("logger_edit_set")} onClick={() => { haptic.tap(); setEditing(s); }}>
                  <span className="set-no">{s.warmup ? t("logger_warmup_short") : s.set_number}</span>
                  <span className="set-value">{fmtSet(s, item.equipment, item.timed, t)}</span>
                  <span className="set-rpe">{s.rpe !== null ? `${t("logger_rpe")} ${s.rpe}` : ""}</span>
                  {s.pr && <span className="set-pr" aria-label="PR">🏆</span>}
                  <span className="set-check"><Check /></span>
                </button>
              </li>
            ))}
          </ol>
        )}

        <div className={"set-entry" + (warmup ? " set-entry-warmup" : "")}>
          <div className="set-entry-head">
            <span className="set-no">
              {warmup ? t("logger_warmup") : nextNumber > item.sets ? t("logger_extra_set") : t("logger_set", { n: nextNumber })}
            </span>
            {!warmup && previousForNext && (
              <span className="muted small">{t("logger_previous_sets")}: {fmtSet(previousForNext, item.equipment, item.timed, t)}</span>
            )}
          </div>
          <div className="set-inputs">
            {!item.timed && (
              <NumberBox label={t("logger_kg")} value={draft.weight} step={WEIGHT_STEP} min={0} max={500}
                         onChange={(weight) => setDraft((d) => ({ ...d, weight }))} />
            )}
            <NumberBox label={item.timed ? t("logger_seconds") : t("logger_reps")} value={draft.reps}
                       step={item.timed ? 5 : 1} min={1} max={item.timed ? 600 : 100}
                       onChange={(reps) => setDraft((d) => ({ ...d, reps: Math.round(reps) }))} />
            <button type="button" className="log-button" aria-label={t("logger_log")} disabled={busy}
                    onClick={() => void onLog()}><Check /></button>
          </div>
          <div className="chips wrap set-quick">
            {!item.timed && (
              <button type="button" className="chip"
                      onClick={() => { haptic.select(); setDraft((d) => ({ ...d, weight: Math.min(500, d.weight + WEIGHT_STEP) })); }}>
                {t("logger_plus_weight")}
              </button>
            )}
            {previousForNext && !warmup && (
              <button type="button" className="chip"
                      onClick={() => { haptic.select(); setDraft((d) => ({ ...d, weight: previousForNext.weight_kg, reps: previousForNext.reps })); }}>
                {t("logger_same")}
              </button>
            )}
            <button type="button" className="chip"
                    onClick={() => {
                      haptic.select();
                      const at = RPE_STEPS.indexOf(draft.rpe);
                      setDraft((d) => ({ ...d, rpe: RPE_STEPS[(at + 1) % RPE_STEPS.length] ?? null }));
                    }}>
              {draft.rpe === null ? t("logger_rpe_none") : `${t("logger_rpe")} ${draft.rpe}`}
            </button>
            <button type="button" className={"chip" + (warmup ? " chip-on" : "")} aria-pressed={warmup}
                    onClick={() => { haptic.select(); setWarmup(!warmup); }}>
              {t("logger_warmup")}
            </button>
          </div>
        </div>
        {allDone && <p className="logger-done small">{t("logger_all_done")}</p>}

        <label className="field logger-note">
          <span className="field-label">{t("logger_note")}</span>
          <input value={noteText} maxLength={200} placeholder={t("logger_note_placeholder")}
                 onChange={(e) => setNoteText(e.target.value)} onBlur={() => void saveNote()} />
        </label>

        <div className="logger-superset">
          <span className="field-label">{t("logger_superset")}</span>
          <div className="chips wrap">
            {GROUPS.map((g) => (
              <button key={g ?? "none"} type="button" className={"chip" + (item.group === g ? " chip-on" : "")}
                      disabled={busy} onClick={() => void chooseGroup(g)}>
                {g ?? t("logger_superset_none")}
              </button>
            ))}
          </div>
        </div>

        <div className="logger-nav">
          <button type="button" className="icon-button" aria-label={t("logger_prev")} disabled={index === 0}
                  onClick={() => { haptic.select(); setSelected(index - 1); }}><ChevronLeft /></button>
          {item.logged.length === 0 ? (
            <button type="button" className="button-link" disabled={busy} onClick={() => void onSwap()}>
              <Swap /> {t("logger_substitute")}
            </button>
          ) : <span />}
          <button type="button" className="icon-button" aria-label={t("logger_next")}
                  disabled={index === ws.items.length - 1}
                  onClick={() => { haptic.select(); setSelected(index + 1); }}><ChevronRight /></button>
        </div>
      </section>

      {rest && (
        <RestBar left={restLeft} total={rest.total} paused={rest.pausedLeft !== null} t={t}
                 onSkip={() => { haptic.tap(); setRest(null); }}
                 onAdd={() => {
                   haptic.select();
                   setRest((r) => r && (r.pausedLeft !== null
                     ? { ...r, pausedLeft: r.pausedLeft + 15, total: r.total + 15 }
                     : { ...r, endsAt: r.endsAt + 15_000, total: r.total + 15 }));
                 }}
                 onToggle={() => {
                   haptic.select();
                   setRest((r) => r && (r.pausedLeft !== null
                     ? { ...r, endsAt: Date.now() + r.pausedLeft * 1000, pausedLeft: null }
                     : { ...r, pausedLeft: restLeft }));
                 }} />
      )}
      {toast && <div className="toast" role="status">{toast}</div>}

      {editing && (
        <SetSheet set={editing} item={item} t={t} busy={busy} onClose={() => setEditing(null)}
                  onSave={async (changes) => {
                    const next = await run(() => editSet(ws.id, editing.id, changes));
                    if (next) { haptic.success(); setWs(next); setEditing(null); }
                  }}
                  onDelete={async () => {
                    const next = await run(() => deleteSet(ws.id, editing.id));
                    if (next) { setWs(next); setEditing(null); }
                  }} />
      )}
    </main>
  );
}

/** − value + with a typeable number in the middle. */
function NumberBox({ label, value, step, min, max, onChange }: {
  label: string; value: number; step: number; min: number; max: number; onChange: (value: number) => void;
}) {
  const [text, setText] = useState(String(value));
  // Follow outside changes (+2.5 kg, a new set) without fighting the user's typing ("62." etc).
  useEffect(() => {
    if (Number(text.replace(",", ".")) !== value) setText(String(value));
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  const clamp = (v: number) => Math.max(min, Math.min(max, Math.round(v * 100) / 100));
  return (
    <div className="numbox">
      <button type="button" aria-label={label + " −"} onClick={() => { haptic.select(); onChange(clamp(value - step)); }}>−</button>
      <label className="numbox-value">
        <input inputMode="decimal" value={text} aria-label={label}
               onChange={(e) => {
                 setText(e.target.value);
                 const n = Number(e.target.value.replace(",", "."));
                 if (e.target.value.trim() !== "" && Number.isFinite(n)) onChange(clamp(n));
               }} />
        <span>{label}</span>
      </label>
      <button type="button" aria-label={label + " +"} onClick={() => { haptic.select(); onChange(clamp(value + step)); }}>+</button>
    </div>
  );
}

function RestBar({ left, total, paused, t, onSkip, onAdd, onToggle }: {
  left: number; total: number; paused: boolean; t: T; onSkip: () => void; onAdd: () => void; onToggle: () => void;
}) {
  const pct = total > 0 ? Math.min(100, (left / total) * 100) : 0;
  return (
    <div className="rest-bar" role="timer" aria-label={t("logger_rest")}>
      <div className="rest-track"><span style={{ width: `${pct}%` }} /></div>
      <div className="rest-row">
        <span className="rest-label">{t("logger_rest")} <b>{clock(left)}</b></span>
        <button type="button" className="chip" onClick={onAdd}>{t("logger_rest_add")}</button>
        <button type="button" className="chip" onClick={onToggle}>
          {paused ? t("logger_rest_resume") : t("logger_rest_pause")}
        </button>
        <button type="button" className="chip chip-on" onClick={onSkip}>{t("logger_rest_skip")}</button>
      </div>
    </div>
  );
}

function SetSheet({ set, item, t, busy, onClose, onSave, onDelete }: {
  set: LoggedSet; item: WorkoutItem; t: T; busy: boolean; onClose: () => void;
  onSave: (changes: { weight_kg: number; reps: number; rpe: number | null }) => void; onDelete: () => void;
}) {
  const [weight, setWeight] = useState(set.weight_kg);
  const [reps, setReps] = useState(set.reps);
  const [rpe, setRpe] = useState<number | null>(set.rpe);
  const [armed, setArmed] = useState(false);
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={t("logger_edit_set")}
           onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        <h2 className="sheet-title">{t("logger_edit_set")} · {item.name}</h2>
        {!item.timed && (
          <Stepper label={t("logger_kg")} value={weight} min={0} max={500} step={WEIGHT_STEP} onChange={setWeight} />
        )}
        <Stepper label={item.timed ? t("logger_seconds") : t("logger_reps")} value={reps} min={1}
                 max={item.timed ? 600 : 100} step={item.timed ? 5 : 1} onChange={setReps} />
        <div className="chips wrap rpe-chips">
          {RPE_STEPS.map((r) => (
            <button key={r ?? 0} type="button" className={"chip" + (rpe === r ? " chip-on" : "")}
                    onClick={() => { haptic.select(); setRpe(r); }}>
              {r === null ? t("logger_rpe_none") : `${t("logger_rpe")} ${r}`}
            </button>
          ))}
        </div>
        <div className="sheet-actions">
          <button type="button" className="button-link danger" disabled={busy}
                  onClick={() => {
                    if (!armed) { haptic.warning(); setArmed(true); return; }
                    onDelete();
                  }}>
            {armed ? t("editor_confirm") : t("logger_delete_set")}
          </button>
          <button type="button" className="button-primary" disabled={busy}
                  onClick={() => onSave({ weight_kg: weight, reps, rpe })}>{t("logger_save")}</button>
        </div>
      </div>
    </div>
  );
}

function SummaryView({ summary, t }: { summary: Summary; t: T }) {
  useEffect(() => bindNativeBack(null), []);
  const exercises = summary.exercises ?? [];
  const prs = summary.prs ?? [];
  const unlocked = summary.achievements ?? [];
  if (summary.discarded) {
    return (
      <main className="logger">
        <section className="card center">
          <p>{t("summary_discarded")}</p>
          <button type="button" className="button-primary"
                  onClick={() => navigate({ name: "workout" }, { replace: true })}>{t("summary_done")}</button>
        </section>
      </main>
    );
  }
  return (
    <main className="logger summary">
      <h1 className="screen-title">{t("summary_title")}</h1>
      <div className="summary-stats">
        <span className="summary-stat">{t("summary_minutes", { n: summary.minutes ?? 0 })}</span>
        <span className="summary-stat">{t("summary_sets", { n: summary.total_sets ?? 0 })}</span>
        <span className="summary-stat">{t("summary_volume", { n: Math.round(summary.volume_kg ?? 0) })}</span>
      </div>
      {prs.length > 0 && (
        <section className="card summary-prs">
          <h2 className="card-title">🏆 {t("summary_prs")}</h2>
          <ul>{prs.map((name) => <li key={name}>{name}</li>)}</ul>
        </section>
      )}
      <section className="card">
        <h2 className="card-title">{t("summary_next")}</h2>
        <ul className="summary-list">
          {exercises.map((ex) => {
            const next = hintText(ex.next_time, t);
            return (
              <li key={ex.exercise_id}>
                <span className="exercise-name">{ex.name}</span>
                <span className="muted small">{fmtSets(ex.sets, ex.equipment, ex.timed, t)}</span>
                {next && <span className="logger-hint small">{next}</span>}
              </li>
            );
          })}
        </ul>
      </section>
      {unlocked.length > 0 && <p className="center-text">{t("summary_achievements", { n: unlocked.length })}</p>}
      <button type="button" className="button-primary"
              onClick={() => { haptic.tap(); navigate({ name: "plan" }, { replace: true }); }}>{t("summary_done")}</button>
    </main>
  );
}
