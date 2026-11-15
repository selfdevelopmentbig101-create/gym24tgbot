/*
 * Program form (reference image 2, "Cycle Overview"): name, weeks, workouts per week,
 * training goal. Three uses: a new custom program, starting a built-in one, editing.
 */
import { useEffect, useState } from "react";
import {
  createProgram, getProgram, getPrograms, patchProgram,
  type ProgramDetail, type TemplateInfo, type TrainingGoal,
} from "../lib/api";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import { errorMessage, type T } from "../lib/plan";
import type { TextKey } from "../i18n";
import { ArrowLeft } from "../components/Icons";

const WEEKS = [4, 6, 8, 10, 12];
const GOALS: TrainingGoal[] = ["strength", "hypertrophy", "endurance"];

type Mode = { kind: "new" } | { kind: "template"; days: number } | { kind: "edit"; id: number };

export function ProgramForm({ mode, t }: { mode: Mode; t: T }) {
  const [name, setName] = useState("");
  const [weeks, setWeeks] = useState(8);
  const [perWeek, setPerWeek] = useState(3);
  const [goal, setGoal] = useState<TrainingGoal>("hypertrophy");
  const [template, setTemplate] = useState<TemplateInfo | null>(null);
  const [original, setOriginal] = useState<ProgramDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (mode.kind === "template") {
      getPrograms().then((d) => setTemplate(d.available.find((x) => x.days === mode.days) ?? null))
        .catch(() => setError(t("error_generic")));
    }
    if (mode.kind === "edit") {
      getProgram(mode.id).then((p) => {
        setOriginal(p);
        setName(p.name ?? "");
        setWeeks(p.weeks);
        setGoal(p.goal);
      }).catch(() => setError(t("error_generic")));
    }
  }, [mode.kind, mode.kind === "template" ? mode.days : mode.kind === "edit" ? mode.id : 0]); // eslint-disable-line react-hooks/exhaustive-deps

  const back = () => goBack(mode.kind === "edit" ? { name: "program", id: mode.id } : { name: "programs" });
  useEffect(() => bindNativeBack(back), []); // eslint-disable-line react-hooks/exhaustive-deps

  const nameRequired = mode.kind === "new";
  const valid = !nameRequired || name.trim().length > 0;

  async function submit(activate: boolean) {
    if (!valid || busy) return;
    haptic.tap();
    setBusy(true);
    setError(null);
    try {
      let program: ProgramDetail;
      if (mode.kind === "edit") {
        const goalChanged = original && original.goal !== goal;
        program = await patchProgram(mode.id, { name: name.trim() || null, weeks, goal });
        haptic.success();
        if (goalChanged) sessionStorage.setItem("gym24.notice", "goal_changed");
        goBack({ name: "program", id: program.id });
        return;
      }
      program = await createProgram({
        name: name.trim() || null, weeks, goal, activate,
        ...(mode.kind === "template" ? { template_days: mode.days } : { workouts_per_week: perWeek }),
      });
      haptic.success();
      navigate({ name: "program", id: program.id }, { replace: true });
    } catch (err) {
      haptic.error();
      setError(errorMessage(err, t));
    } finally {
      setBusy(false);
    }
  }

  const title = mode.kind === "edit" ? t("edit_program")
    : mode.kind === "template" && template ? t(("split_" + template.split) as TextKey) : t("create_program");

  return (
    <main className="program-form">
      <header className="screen-header">
        <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}><ArrowLeft /></button>
        <h1 className="screen-header-title">{title}</h1>
        <span className="round-spacer" />
      </header>

      {mode.kind === "template" && template && (
        <section className="card">
          <p className="muted small">{t(("split_" + template.split + "_desc") as TextKey)}</p>
          <div className="day-chips">
            {template.day_keys.map((k, i) => <span key={i} className="day-chip">{t(("day_" + k) as TextKey)}</span>)}
          </div>
          <p className="muted small">{t("template_note")}</p>
        </section>
      )}

      <label className="field">
        <span className="field-label">{t("program_name")}{!nameRequired && <span className="muted"> · {t("optional")}</span>}</span>
        <input className="text-input" value={name} maxLength={40} onChange={(e) => setName(e.target.value)}
               placeholder={mode.kind === "new" ? t("program_name_placeholder")
                 : template ? t(("split_" + template.split) as TextKey)
                   : original ? t(("split_" + original.split) as TextKey) : ""} />
      </label>

      <fieldset className="field">
        <legend className="field-label">{t("weeks_in_program")}</legend>
        <div className="number-pills" role="radiogroup" aria-label={t("weeks_in_program")}>
          {WEEKS.map((n) => (
            <button key={n} type="button" role="radio" aria-checked={weeks === n}
                    className={"number-pill" + (weeks === n ? " number-pill-on" : "")}
                    onClick={() => { haptic.select(); setWeeks(n); }}>{n}</button>
          ))}
        </div>
      </fieldset>

      {mode.kind === "new" && (
        <fieldset className="field">
          <legend className="field-label">{t("workouts_per_week")}</legend>
          <div className="number-pills" role="radiogroup" aria-label={t("workouts_per_week")}>
            {[1, 2, 3, 4, 5, 6, 7].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={perWeek === n}
                      className={"number-pill" + (perWeek === n ? " number-pill-on" : "")}
                      onClick={() => { haptic.select(); setPerWeek(n); }}>{n}</button>
            ))}
          </div>
        </fieldset>
      )}

      <fieldset className="field">
        <legend className="field-label">{t("primary_goal")}</legend>
        <div className="chips wrap" role="radiogroup" aria-label={t("primary_goal")}>
          {GOALS.map((g) => (
            <button key={g} type="button" role="radio" aria-checked={goal === g}
                    className={"chip" + (goal === g ? " chip-on" : "")}
                    onClick={() => { haptic.select(); setGoal(g); }}>{t(("tgoal_" + g) as TextKey)}</button>
          ))}
        </div>
        <p className="muted small">{t(("tgoal_" + goal + "_hint") as TextKey)}</p>
        {mode.kind === "edit" && original && original.goal !== goal && (
          <p className="step-note left">{t("goal_change_note")}</p>
        )}
      </fieldset>

      {error && <p className="field-error" role="alert">{error}</p>}

      <div className="form-actions">
        {mode.kind === "template" ? (
          <>
            <button type="button" className="button-primary" disabled={busy} onClick={() => void submit(true)}>
              {t("start_program")}
            </button>
            <button type="button" className="button-secondary" disabled={busy} onClick={() => void submit(false)}>
              {t("save_for_later")}
            </button>
          </>
        ) : (
          <button type="button" className="button-primary" disabled={!valid || busy} onClick={() => void submit(false)}>
            {mode.kind === "edit" ? t("save") : t("create")}
          </button>
        )}
      </div>
    </main>
  );
}
