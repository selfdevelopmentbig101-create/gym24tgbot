/*
 * Guided workout (opened by "Start workout" / "Continue workout").
 *
 *   countdown  3 - 2 - 1 - GO!
 *   exercise   looping picture on top, tracking controls below. "Next set" saves the set
 *              (POST /api/workouts/{id}/sets); on the last set the big button finishes the exercise.
 *   done       "Exercise completed" + rest choices (1:00, 1:30 preselected, 2:00, skip rest)
 *   rest       big countdown, +30 s, Start now; ends by itself and opens the next exercise
 *   summary    after the last exercise (no rest): time, exercises, sets, reps
 *
 * The segmented progress bar stays on top in every phase except the countdown and the summary.
 * Sets are saved one by one on the server, so history, stats, PRs and XP work as before and the
 * workout can also be continued in the bot or in the detailed logger (/workout/live).
 * The screen state (which exercise, resting or not) is kept in localStorage so closing the
 * Mini App mid-workout resumes where you left off. Back asks "End workout?". The screen
 * stays awake with the Wake Lock API where supported.
 */
import { useEffect, useRef, useState } from "react";
import {
  finishWorkout, getTrain, logSet, trainErrorKey,
  type LoggedSet, type Summary, type WorkoutItem, type WorkoutView,
} from "../lib/trainApi";
import { clock, repRange } from "../lib/trainText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, confirmDialog, haptic, vibrate } from "../lib/telegram";
import {
  clearGuided, countdownIsFresh, loadGuided, saveGuided, type GuidedPhase, type GuidedState,
} from "../lib/guidedSession";
import { useWakeLock } from "../lib/useWakeLock";
import type { TextKey } from "../i18n";
import { Countdown } from "../components/Countdown";
import { ExerciseImage } from "../components/ExerciseImage";
import { WorkoutProgress, type ProgressItem } from "../components/WorkoutProgress";
import "./train.css";
import "./workout.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;
type Draft = { weight: number; reps: number };
type Rest = { endsAt: number; total: number };

const WEIGHT_STEP = 2.5;
const REST_CHOICES = [60, 90, 120];   // seconds: 1:00, 1:30, 2:00
const DEFAULT_REST = 90;              // 1:30 is preselected
const RING = 2 * Math.PI * 54;        // length of the rest timer circle

function workingSets(item: WorkoutItem): LoggedSet[] {
  return item.logged.filter((s) => !s.warmup);
}

/** What the next set is pre-filled with: the last set today, else the overload suggestion. */
function draftFor(item: WorkoutItem): Draft {
  const done = workingSets(item);
  const last = done[done.length - 1];
  if (last) return { weight: last.weight_kg, reps: last.reps };
  if (item.suggestion) return { weight: item.suggestion.weight_kg, reps: item.suggestion.reps };
  return { weight: 0, reps: item.rep_min };
}

function isDone(item: WorkoutItem, finished: number[]): boolean {
  return finished.includes(item.index) || item.status === "completed";
}

/** The next exercise to do after `after`: later ones first, then any skipped earlier one. */
function findNext(items: WorkoutItem[], finished: number[], after: number): number | null {
  for (let i = after + 1; i < items.length; i++) if (!isDone(items[i], finished)) return i;
  for (let i = 0; i < after; i++) if (!isDone(items[i], finished)) return i;
  return null;
}

/** Where to continue, from the server's workout and what this phone saved. */
function restore(view: WorkoutView, saved: GuidedState | null) {
  const total = view.items.length;
  const valid = (i: number) => Number.isInteger(i) && i >= 0 && i < total;
  const finished = (saved?.finished ?? []).filter(valid);
  const result = {
    phase: "exercise" as GuidedPhase,
    index: Math.max(0, Math.min(view.current_index, total - 1)),
    finished,
    rest: null as Rest | null,
    restChoice: saved?.restChoice ?? DEFAULT_REST,
  };
  if (!saved) return result;
  if (saved.phase === "countdown") {
    if (countdownIsFresh(saved)) result.phase = "countdown";
    return result;
  }
  if (!valid(saved.index)) return result;
  result.index = saved.index;
  if (saved.phase === "done") {
    result.phase = "done";
  } else if (saved.phase === "rest") {
    const next = findNext(view.items, finished, saved.index);
    if (next === null) {
      result.phase = "done";
    } else if (saved.restEndsAt !== null && saved.restEndsAt > Date.now()) {
      result.phase = "rest";
      result.rest = { endsAt: saved.restEndsAt, total: saved.restTotal };
    } else {
      result.index = next;                // the rest is over: straight to the next exercise
    }
  } else if (finished.includes(saved.index)) {
    const next = findNext(view.items, finished, saved.index);
    if (next !== null) result.index = next;
  }
  return result;
}

export function Workout({ t, attribution }: { t: T; attribution: string }) {
  const [ws, setWs] = useState<WorkoutView | null>(null);
  const [ready, setReady] = useState(false);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<TextKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<GuidedPhase>("exercise");
  const [index, setIndex] = useState(0);
  const [finished, setFinished] = useState<number[]>([]);
  const [rest, setRest] = useState<Rest | null>(null);
  const [restChoice, setRestChoice] = useState(DEFAULT_REST);
  const [draft, setDraft] = useState<Draft>({ weight: 0, reps: 8 });
  const [summary, setSummary] = useState<{ data: Summary; seconds: number } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const item = ws?.items[index];
  const loggedCount = item ? workingSets(item).length : 0;
  const nextIdx = ws ? findNext(ws.items, finished, index) : null;

  useWakeLock(ws !== null && summary === null);

  // ---- load the workout and restore where we were ----
  useEffect(() => {
    let live = true;
    getTrain()
      .then((d) => {
        if (!live) return;
        const active = d.active;
        if (!active || active.items.length === 0) {
          setMissing(true);
          return;
        }
        const r = restore(active, loadGuided(active.id));
        setWs(active);
        setPhase(r.phase);
        setIndex(r.index);
        setFinished(r.finished);
        setRest(r.rest);
        setRestChoice(r.restChoice);
        setReady(true);
      })
      .catch((e) => { if (live) setError(trainErrorKey(e)); });
    return () => { live = false; };
  }, []);

  // ---- remember the screen state so the Mini App can be closed and reopened ----
  useEffect(() => {
    if (!ws || !ready || summary) return;
    saveGuided({
      workoutId: ws.id, phase, index, finished, restEndsAt: rest?.endsAt ?? null,
      restTotal: rest?.total ?? 0, restChoice, at: Date.now(),
    });
  }, [ws?.id, ready, summary, phase, index, finished, rest, restChoice]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Telegram Back button: ask "End workout?" ----
  const backRef = useRef<() => void>(() => {});
  backRef.current = () => {
    if (!ws || summary || missing) {
      goBack({ name: "workout" });
      return;
    }
    haptic.warning();
    confirmDialog(`${t("gx_end_title")}\n${t("gx_end_text")}`, (ok) => {
      if (ok) goBack({ name: "workout" });
    });
  };
  useEffect(() => bindNativeBack(() => backRef.current()), []);

  // ---- pre-fill the next set ----
  useEffect(() => {
    if (item) setDraft(draftFor(item));
  }, [ws?.id, index, loggedCount, item?.exercise_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- rest clock (counts down from an end time, so it survives the phone sleeping) ----
  useEffect(() => {
    if (phase !== "rest") return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    if (phase === "rest" && rest && rest.endsAt <= now) {
      haptic.success();
      vibrate([200, 100, 200]);
      goNext();
    }
  }, [now, phase, rest]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  // All planned sets already saved (e.g. resumed): go straight to "completed".
  useEffect(() => {
    if (ready && phase === "exercise" && item && loggedCount >= item.sets) completeExercise();
  }, [ready, phase, item?.exercise_id, loggedCount]); // eslint-disable-line react-hooks/exhaustive-deps

  // Last exercise done: short pause on the success screen, then save the workout and show the summary.
  useEffect(() => {
    if (!ready || phase !== "done" || nextIdx !== null || summary) return;
    const timer = setTimeout(() => void finishAll(), 1600);
    return () => clearTimeout(timer);
  }, [ready, phase, nextIdx, summary]); // eslint-disable-line react-hooks/exhaustive-deps

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

  function completeExercise() {
    haptic.success();
    setFinished((f) => (f.includes(index) ? f : [...f, index]));
    setPhase("done");
  }

  /** Saves the set on the screen (kg + reps) through the existing API. */
  async function saveSet(): Promise<boolean> {
    if (!ws || !item) return false;
    const result = await run(() => logSet(ws.id, {
      index, weight_kg: item.timed ? 0 : draft.weight, reps: draft.reps, rpe: null, warmup: false,
    }));
    if (!result) return false;
    setWs(result.workout);
    const logged = result.set;
    if (logged.pr && logged.estimate !== null && logged.previous_best !== null) {
      haptic.success();
      setToast(t("logger_pr", { value: logged.estimate.toFixed(1), previous: logged.previous_best.toFixed(1) }));
    }
    return true;
  }

  async function onPrimary(isLastSet: boolean, setNo: number) {
    if (!(await saveSet())) return;
    if (isLastSet) {
      completeExercise();
    } else {
      haptic.tap();
      setToast(t("gx_set_saved", { n: setNo }));
    }
  }

  async function onFinishEarly() {
    if (await saveSet()) completeExercise();
  }

  async function finishAll() {
    if (!ws) return;
    const result = await run(() => finishWorkout(ws.id));
    if (!result) return;                       // the error is shown with a Retry button
    haptic.success();
    clearGuided();
    setSummary({ data: result, seconds: (Date.now() - Date.parse(ws.started_at)) / 1000 });
  }

  function goNext() {
    setRest(null);
    if (nextIdx === null) {
      setPhase("done");
      return;
    }
    setIndex(nextIdx);
    setPhase("exercise");
  }

  function startRest() {
    haptic.tap();
    if (restChoice <= 0) {
      goNext();
      return;
    }
    const at = Date.now();
    setNow(at);
    setRest({ endsAt: at + restChoice * 1000, total: restChoice });
    setPhase("rest");
  }

  // ---------- screens ----------
  if (summary && ws) {
    return <SummaryView data={summary.data} seconds={summary.seconds} total={ws.items.length} t={t} />;
  }

  if (missing || (error && !ws)) {
    return (
      <main className="gx gx-center">
        <section className="card center" role="alert">
          <p>{error ? t(error) : t("logger_no_workout")}</p>
          <button type="button" className="button-primary"
                  onClick={() => navigate({ name: "workout" }, { replace: true })}>{t("logger_open_train")}</button>
        </section>
      </main>
    );
  }
  if (!ws || !item || !ready) {
    return <main className="gx gx-center"><div className="spinner center-spinner" aria-label={t("loading")} /></main>;
  }

  if (phase === "countdown") {
    return (
      <main className="gx">
        <Countdown t={t} onDone={() => setPhase("exercise")} />
      </main>
    );
  }

  // The progress bar highlights what you are doing now; while resting that is the next exercise.
  const shown = phase === "rest" && nextIdx !== null ? nextIdx : index;
  const progress: ProgressItem[] = ws.items.map((it, i) => ({
    name: it.name,
    status: (phase === "done" && i === index) || (i !== shown && isDone(it, finished))
      ? "done" : i === shown ? "current" : "todo",
  }));

  const done = workingSets(item);
  const setNo = done.length + 1;
  const isLastSet = setNo >= item.sets;
  const media = item.media ?? null;
  const hasImage = Boolean(media?.kind || item.image);
  const muscle = t(("muscle_" + item.muscle_group) as TextKey);
  const repsTotal = done.reduce((sum, s) => sum + s.reps, 0);
  const left = rest ? Math.max(0, Math.ceil((rest.endsAt - now) / 1000)) : 0;
  const pct = rest && rest.total > 0 ? Math.min(1, left / rest.total) : 0;
  const upNext = nextIdx !== null ? ws.items[nextIdx] : null;

  return (
    <main className="gx" data-phase={phase}>
      <WorkoutProgress items={progress} current={shown} t={t}
                       prevName={ws.items[shown - 1]?.name ?? null} nextName={ws.items[shown + 1]?.name ?? null}
                       onBack={() => backRef.current()}>
        <button type="button" className="gx-link"
                onClick={() => { haptic.tap(); navigate({ name: "workoutLive" }); }}>{t("gx_details")}</button>
      </WorkoutProgress>

      {phase === "exercise" && (
        <>
          <section className="gx-media">
            <ExerciseImage key={item.exercise_id + ":" + index} start={media?.start} peak={media?.peak}
                           still={media?.still ?? item.image} muscle={item.muscle_group} label={item.name}
                           caption={muscle} />
          </section>
          {hasImage && attribution && <p className="gx-credit">{attribution}</p>}

          <section className="gx-panel">
            <div className="gx-head">
              <h1 className="gx-name">
                {item.label && <b className="superset-label">{item.label}</b>}{item.name}
              </h1>
              <p className="gx-muscle">{muscle}</p>
            </div>

            <div className="gx-setrow">
              <span className="gx-setpill">{t("gx_set_of", { n: Math.min(setNo, item.sets), total: item.sets })}</span>
              <span className="gx-target">{t("gx_target", { reps: repRange(item, t) })}</span>
            </div>

            <Counter size="big" label={item.timed ? t("gx_seconds_done") : t("gx_reps_done")}
                     value={draft.reps} display={String(draft.reps)} min={1} max={item.timed ? 600 : 100}
                     step={item.timed ? 5 : 1} onChange={(reps) => setDraft((d) => ({ ...d, reps }))} />

            {!item.timed && (
              <Counter size="small" label={`${t("gx_weight")}, ${t("logger_kg")}`} value={draft.weight}
                       display={item.equipment === "bodyweight" && draft.weight === 0 ? t("logger_bw") : String(draft.weight)}
                       min={0} max={500} step={WEIGHT_STEP}
                       onChange={(weight) => setDraft((d) => ({ ...d, weight }))} />
            )}

            {error && <p className="notice" role="alert">{t(error)}</p>}

            <button type="button" className="gx-btn gx-btn-primary" disabled={busy}
                    onClick={() => void onPrimary(isLastSet, setNo)}>
              {busy ? <span className="spinner spinner-small" /> : isLastSet ? t("gx_finish_exercise") : t("gx_next_set")}
            </button>
            {!isLastSet && (
              <button type="button" className="gx-link gx-early" disabled={busy} onClick={() => void onFinishEarly()}>
                {t("gx_finish_early")}
              </button>
            )}
          </section>
        </>
      )}

      {phase === "done" && (
        <section className="gx-stage">
          <CheckBurst />
          <h1 className="gx-done-title">{t("gx_done_title")}</h1>
          <p className="gx-done-name">{item.name}</p>
          <p className="gx-done-stats">
            {item.timed
              ? t("gx_done_stats_timed", { sets: done.length, seconds: repsTotal })
              : t("gx_done_stats", { sets: done.length, reps: repsTotal })}
          </p>

          {upNext ? (
            <>
              <p className="gx-label">{t("gx_rest_choose")}</p>
              <div className="gx-choices" role="radiogroup" aria-label={t("gx_rest_choose")}>
                {REST_CHOICES.map((seconds) => (
                  <button key={seconds} type="button" role="radio" aria-checked={restChoice === seconds}
                          className={"gx-choice" + (restChoice === seconds ? " gx-choice-on" : "")}
                          onClick={() => { haptic.select(); setRestChoice(seconds); }}>
                    {clock(seconds)}
                  </button>
                ))}
                <button type="button" role="radio" aria-checked={restChoice === 0}
                        className={"gx-choice" + (restChoice === 0 ? " gx-choice-on" : "")}
                        onClick={() => { haptic.select(); setRestChoice(0); }}>
                  {t("gx_rest_skip")}
                </button>
              </div>
              <p className="gx-upnext">{t("gx_up_next", { name: upNext.name })}</p>
              <button type="button" className="gx-btn gx-btn-primary" onClick={startRest}>
                {restChoice > 0 ? t("gx_rest_start") : t("gx_start_now")}
              </button>
            </>
          ) : error ? (
            <>
              <p className="notice" role="alert">{t(error)}</p>
              <button type="button" className="gx-btn gx-btn-primary" disabled={busy} onClick={() => void finishAll()}>
                {t("retry")}
              </button>
            </>
          ) : (
            <>
              <div className="spinner" aria-hidden />
              <p className="muted">{t("gx_saving")}</p>
            </>
          )}
        </section>
      )}

      {phase === "rest" && upNext && (
        <section className="gx-stage" role="timer" aria-label={t("gx_rest_title")}>
          <p className="gx-label">{t("gx_rest_title")}</p>
          <div className="gx-ring">
            <svg viewBox="0 0 120 120" aria-hidden>
              <circle className="gx-ring-bg" cx="60" cy="60" r="54" />
              <circle className="gx-ring-fg" cx="60" cy="60" r="54" transform="rotate(-90 60 60)"
                      strokeDasharray={RING} strokeDashoffset={RING * (1 - pct)} />
            </svg>
            <span className="gx-time">{clock(left)}</span>
          </div>
          <p className="gx-upnext">{t("gx_up_next", { name: upNext.name })}</p>
          <button type="button" className="gx-btn gx-btn-secondary"
                  onClick={() => {
                    haptic.select();
                    setRest((r) => (r ? { endsAt: r.endsAt + 30_000, total: r.total + 30 } : r));
                  }}>
            {t("gx_rest_add")}
          </button>
          <button type="button" className="gx-btn gx-btn-primary" onClick={() => { haptic.tap(); goNext(); }}>
            {t("gx_start_now")}
          </button>
        </section>
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  );
}

/** − value + with big round buttons (the reps) or smaller ones (the weight). */
function Counter({ size, label, value, display, step, min, max, onChange }: {
  size: "big" | "small"; label: string; value: number; display: string;
  step: number; min: number; max: number; onChange: (value: number) => void;
}) {
  const clamp = (v: number) => Math.max(min, Math.min(max, Math.round(v * 100) / 100));
  return (
    <div className={"gx-counter gx-counter-" + size}>
      <button type="button" className="gx-round" aria-label={`${label} −`} disabled={value <= min}
              onClick={() => { haptic.select(); onChange(clamp(value - step)); }}>−</button>
      <div className="gx-counter-value" aria-live="polite">
        <b>{display}</b>
        <span>{label}</span>
      </div>
      <button type="button" className="gx-round" aria-label={`${label} +`} disabled={value >= max}
              onClick={() => { haptic.select(); onChange(clamp(value + step)); }}>+</button>
    </div>
  );
}

/** Success animation: a circle and a check mark that draw themselves, then a soft pulse. */
function CheckBurst() {
  return (
    <div className="gx-check" aria-hidden>
      <svg viewBox="0 0 112 112">
        <circle className="gx-check-ring" cx="56" cy="56" r="48" transform="rotate(-90 56 56)" />
        <path className="gx-check-tick" d="M36 58 L51 73 L78 40" />
      </svg>
    </div>
  );
}

function SummaryView({ data, seconds, total, t }: { data: Summary; seconds: number; total: number; t: T }) {
  const exercises = data.exercises ?? [];
  const prs = data.prs ?? [];
  const reps = exercises
    .filter((e) => !e.timed)
    .reduce((sum, e) => sum + e.sets.reduce((inner, s) => inner + s.reps, 0), 0);
  const leave = () => { haptic.tap(); navigate({ name: "plan" }, { replace: true }); };

  if (data.discarded) {
    return (
      <main className="gx gx-center">
        <section className="card center">
          <p>{t("summary_discarded")}</p>
          <button type="button" className="button-primary" onClick={leave}>{t("summary_done")}</button>
        </section>
      </main>
    );
  }
  return (
    <main className="gx">
      <section className="gx-summary">
        <CheckBurst />
        <h1 className="gx-done-title">{t("summary_title")}</h1>
        <div className="gx-tiles">
          <div className="gx-tile"><b>{clock(seconds)}</b><span>{t("gx_sum_time")}</span></div>
          <div className="gx-tile"><b>{exercises.length || total} / {total}</b><span>{t("gx_sum_exercises")}</span></div>
          <div className="gx-tile"><b>{data.total_sets ?? 0}</b><span>{t("gx_sum_sets")}</span></div>
          <div className="gx-tile"><b>{reps}</b><span>{t("gx_sum_reps")}</span></div>
        </div>
        <p className="muted small">{t("summary_volume", { n: Math.round(data.volume_kg ?? 0) })}</p>
        {data.xp_gained !== undefined && (
          <p className="summary-xp">
            {t("summary_xp", { n: data.xp_gained })}
            {data.level_up && data.level ? " · " + t("summary_level_up", { rank: t(("rank_" + data.level.key) as TextKey) }) : ""}
          </p>
        )}
        {prs.length > 0 && (
          <section className="card summary-prs">
            <h2 className="card-title">🏆 {t("summary_prs")}</h2>
            <ul>{prs.map((name) => <li key={name}>{name}</li>)}</ul>
          </section>
        )}
        <button type="button" className="gx-btn gx-btn-primary" onClick={leave}>{t("summary_done")}</button>
      </section>
    </main>
  );
}
