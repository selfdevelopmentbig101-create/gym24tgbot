/*
 * Create a program: name, weeks, workouts per week, primary goal
 * (Strength / Hypertrophy / Endurance). The server fills it with default days
 * for that goal and frequency; you can edit them afterwards in the split editor.
 */
import { useEffect, useState, type ReactNode } from "react";
import { createProgram, type Goal } from "../lib/planApi";
import { planErrorKey } from "../lib/planText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ArrowLeft, Check, Dumbbell, Flame, TrendUp } from "../components/Icons";
import { Stepper } from "../components/Stepper";
import "./plan.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const GOALS: { goal: Goal; icon: ReactNode }[] = [
  { goal: "strength", icon: <Dumbbell /> },
  { goal: "hypertrophy", icon: <TrendUp /> },
  { goal: "endurance", icon: <Flame /> },
];
const DAYS = [2, 3, 4, 5, 6];

export function ProgramNew({ t }: { t: T }) {
  const [name, setName] = useState("");
  const [weeks, setWeeks] = useState(8);
  const [days, setDays] = useState(3);
  const [goal, setGoal] = useState<Goal>("hypertrophy");
  const [startNow, setStartNow] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<TextKey | null>(null);

  useEffect(() => bindNativeBack(() => goBack({ name: "programs" })), []);

  async function submit() {
    if (busy) return;
    if (!name.trim()) {
      haptic.error();
      setError("program_name_required");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createProgram({ name: name.trim(), weeks, workouts_per_week: days, goal, activate: startNow });
      haptic.success();
      navigate(startNow ? { name: "plan" } : { name: "programs" }, { replace: true });
    } catch (e) {
      haptic.error();
      setError(planErrorKey(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="program-new">
      <header className="editor-header">
        <button type="button" className="round-button round-back" aria-label={t("back")}
                onClick={() => goBack({ name: "programs" })}><ArrowLeft /></button>
        <h1 className="editor-title">{t("program_new_title")}</h1>
        <span className="round-spacer" />
      </header>

      <form className="program-form" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <label className="field">
          <span className="field-label">{t("program_name")}</span>
          <input value={name} maxLength={40} placeholder={t("program_name_placeholder")}
                 onChange={(e) => setName(e.target.value)} />
        </label>

        <Stepper label={t("program_weeks")} value={weeks} min={4} max={16}
                 format={(n) => t("program_weeks_value", { n })} onChange={setWeeks} />

        <fieldset className="filter-group">
          <legend>{t("program_days")}</legend>
          <div className="day-pills" role="radiogroup" aria-label={t("program_days")}>
            {DAYS.map((n) => (
              <button key={n} type="button" role="radio" aria-checked={days === n}
                      className={"day-pill" + (days === n ? " day-pill-on" : "")}
                      onClick={() => { haptic.select(); setDays(n); }}>{n}</button>
            ))}
          </div>
        </fieldset>

        <fieldset className="filter-group">
          <legend>{t("program_goal")}</legend>
          <div className="options" role="radiogroup" aria-label={t("program_goal")}>
            {GOALS.map(({ goal: g, icon }) => (
              <button key={g} type="button" role="radio" aria-checked={goal === g}
                      className={"option" + (goal === g ? " option-on" : "")}
                      onClick={() => { haptic.select(); setGoal(g); }}>
                <span className="option-icon">{icon}</span>
                <span className="option-text">
                  <span className="option-label">{t(("goal_" + g) as TextKey)}</span>
                  <span className="option-hint">{t(("goal_" + g + "_hint") as TextKey)}</span>
                </span>
                <span className={"option-check" + (goal === g ? " option-check-on" : "")}>{goal === g && <Check />}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <button type="button" role="switch" aria-checked={startNow} className="switch-row"
                onClick={() => { haptic.select(); setStartNow(!startNow); }}>
          <span>{t("program_start_now")}</span>
          <span className={"switch" + (startNow ? " switch-on" : "")}><span /></span>
        </button>

        {error && <p className="field-error" role="alert">{t(error)}</p>}
        <button type="submit" className="button-primary program-submit" disabled={busy}>
          {busy ? <span className="spinner spinner-small" /> : t("program_create")}
        </button>
      </form>
    </main>
  );
}
