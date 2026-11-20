/*
 * Mini App onboarding: one question per screen, "n of N" progress (reference image 3).
 * Answers are kept on this device until saved, so closing the app doesn't lose them.
 * Everything is validated again by the server (same rules as the bot's onboarding).
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  acceptDisclaimer, fieldError, saveProfile, setLanguage,
  type AppConfig, type Diet, type Equipment, type Experience, type Goal, type Injury,
  type LanguageCode, type Me, type ProfileSaved, type Sex,
} from "../lib/api";
import { previewPlan, type PlanPreview } from "../lib/planApi";
import { repsText } from "../lib/planText";
import { bindNativeBack, closeApp, haptic, localUserKey } from "../lib/telegram";
import { clamp, cmToIn, formatFeet, inToCm, kgToLb, lbToKg, snap, type HeightUnit, type WeightUnit } from "../lib/units";
import type { TextKey } from "../i18n";
import {
  ArrowLeft, Close, Dumbbell, Female, Heart, Leaf, Male, Neutral, Scale, Sparkles, TrendDown, TrendUp,
} from "../components/Icons";
import { Options, UnitToggle } from "../components/Options";
import { Ruler } from "../components/Ruler";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

interface Draft {
  language?: LanguageCode;
  sex?: Sex;
  goal?: Goal;
  age: number;
  height_cm: number;
  weight_kg: number;
  target_weight_kg: number | null;
  experience?: Experience;
  /** Answer to the days question; seeds the recommended split. */
  daysAnswer?: number;
  /** Days of the chosen split (the days answer until the user picks another). */
  training_days?: number;
  /** The split step was confirmed (the split itself is stored as training_days). */
  splitChosen: boolean;
  equipment?: Equipment;
  injuries: Injury[];
  injuriesAnswered: boolean;
  diet?: Diet;
  heightUnit: HeightUnit;
  weightUnit: WeightUnit;
}

type StepId = "language" | "sex" | "goal" | "age" | "height" | "weight" | "target" | "experience"
  | "days" | "equipment" | "injuries" | "diet" | "split" | "disclaimer";

const LANGUAGES: { code: LanguageCode; label: string }[] = [
  { code: "en", label: "English" }, { code: "ru", label: "Русский" }, { code: "uz", label: "O‘zbekcha" },
];

const HINTS: Partial<Record<StepId, TextKey>> = {
  age: "h_age", target: "h_target", days: "h_days", injuries: "h_injuries", split: "h_split",
};

const KNOWN_ERRORS = new Set(["err_age", "err_height", "err_weight", "err_target_weight", "err_generic"]);

const STEP_FOR_FIELD: Record<string, StepId> = {
  goal: "goal", age: "age", sex: "sex", height_cm: "height", weight_kg: "weight",
  target_weight_kg: "target", experience: "experience", training_days: "days",
  equipment: "equipment", injuries: "injuries", diet: "diet",
};

// Goals that reduce weight, goals that keep it stable, everything else gains.
const LOSS_GOALS: Goal[] = ["lose_weight", "get_in_shape"];
const MAINTAIN_GOALS: Goal[] = ["recomp", "improve_health"];

/** +1 = gain, -1 = lose, 0 = maintenance (no goal weight). */
function goalDirection(goal?: Goal): number {
  if (!goal || MAINTAIN_GOALS.includes(goal)) return 0;
  return LOSS_GOALS.includes(goal) ? -1 : 1;
}

// ---------- Artwork ----------
// Files live in miniapp/public/onboarding/ (see the README there). The images
// are hidden until the files exist, so the cards work without them.
const art = (name: string) => `/onboarding/${name}.png`;

const GOAL_ART: Partial<Record<Goal, string>> = {
  bulk: art("goal_bulk"),
  lean_bulk: art("goal_lean_bulk"),
  recomp: art("goal_recomp"),
  lose_weight: art("goal_lose_weight"),
  gain_muscle: art("goal_gain_muscle"),
  improve_health: art("goal_improve_health"),
  get_in_shape: art("goal_get_in_shape"),
};
const EXPERIENCE_ART_MALE: Partial<Record<Experience, string>> = {
  beginner: art("exp_beginner"),
  intermediate: art("exp_intermediate"),
  advanced: art("exp_advanced"),
};
const EXPERIENCE_ART_FEMALE: Partial<Record<Experience, string>> = {
  beginner: art("exp_beginner_female"),
  intermediate: art("exp_intermediate_female"),
  advanced: art("exp_advanced_female"),
};
const experienceArt = (sex?: Sex) => sex === "female" ? EXPERIENCE_ART_FEMALE : EXPERIENCE_ART_MALE;
const EQUIPMENT_ART: Partial<Record<Equipment, string>> = {
  full_gym: art("eq_full_gym"),
  home_dumbbells: art("eq_home_dumbbells"),
  bodyweight: art("eq_bodyweight"),
};
const DIET_ART: Partial<Record<Diet, string>> = {
  none: art("diet_none"),
  vegetarian: art("diet_vegetarian"),
  vegan: art("diet_vegan"),
  pescatarian: art("diet_pescatarian"),
};

interface SplitChoice { days: number; labelKey: TextKey; hintKey: TextKey }

const SPLIT_CHOICES: SplitChoice[] = [
  { days: 2, labelKey: "template_full_body_2", hintKey: "split_full_body_hint" },
  { days: 3, labelKey: "template_full_body_3", hintKey: "split_full_body_hint" },
  { days: 4, labelKey: "template_upper_lower_4", hintKey: "split_upper_lower_hint" },
  { days: 5, labelKey: "template_upper_lower_ppl_5", hintKey: "split_upper_lower_ppl_hint" },
  { days: 6, labelKey: "template_ppl_6", hintKey: "split_ppl_hint" },
];

const draftKey = () => "gym24.onboarding.v1." + localUserKey();

function loadDraft(): Draft {
  const fresh: Draft = {
    age: 25, height_cm: 175, weight_kg: 70, target_weight_kg: null, injuries: [],
    injuriesAnswered: false, splitChosen: false, heightUnit: "cm", weightUnit: "kg",
  };
  try {
    const saved = JSON.parse(localStorage.getItem(draftKey()) ?? "null");
    if (!saved || typeof saved !== "object") return fresh;
    const merged = { ...fresh, ...saved };
    // Older drafts only had training_days: it was the days answer back then.
    if (merged.daysAnswer === undefined && typeof merged.training_days === "number") {
      merged.daysAnswer = merged.training_days;
    }
    return merged;
  } catch {
    return fresh;
  }
}

interface Props {
  me: Me;
  config: AppConfig;
  t: T;
  onLanguage: (me: Me) => void;
  onDone: (saved: ProfileSaved) => void;
}

export function Onboarding({ me, config, t, onLanguage, onDone }: Props) {
  const rules = config.profile_rules;
  const goalsFor = (sex?: Sex) => (sex ? rules.goals_by_sex[sex] : rules.goals);

  const [draft, setDraft] = useState<Draft>(() => {
    const saved = loadDraft();
    // A saved goal from the other goal set (e.g. an old draft) no longer applies.
    if (saved.sex && saved.goal && !rules.goals_by_sex[saved.sex].includes(saved.goal)) {
      return { ...saved, goal: undefined, target_weight_kg: null };
    }
    return saved;
  });
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Asked once at the start, even after the choice is saved mid-onboarding.
  const [askLanguage] = useState(!me.language);
  const [askDisclaimer] = useState(!me.disclaimer_accepted);

  const direction = goalDirection(draft.goal);
  // Any goal weight in the allowed range is fine; whether it means losing or
  // gaining is read from the selected value, not from the goal.
  const targetRange: [number, number] = rules.target_weight_kg ?? [35, 200];
  const targetRoom = direction !== 0;

  const steps = useMemo<StepId[]>(() => {
    const list: StepId[] = [];
    if (askLanguage) list.push("language");
    list.push("sex", "goal", "age", "height", "weight");
    if (targetRoom) list.push("target");
    list.push("experience", "days", "equipment", "injuries", "diet", "split");
    if (askDisclaimer) list.push("disclaimer");
    return list;
  }, [askLanguage, askDisclaimer, targetRoom]);

  const step = steps[Math.min(stepIndex, steps.length - 1)];

  useEffect(() => {
    localStorage.setItem(draftKey(), JSON.stringify(draft));
  }, [draft]);

  const back = stepIndex > 0 ? () => { haptic.tap(); setError(null); setStepIndex((i) => i - 1); } : null;
  useEffect(() => bindNativeBack(back), [stepIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (patch: Partial<Draft>) => {
    setError(null);
    setDraft((d) => {
      const next = { ...d, ...patch };
      if (patch.sex !== undefined && patch.sex !== d.sex) {
        // The goal cards depend on sex: drop a goal from the other set.
        if (next.goal && !rules.goals_by_sex[next.sex ?? "unspecified"].includes(next.goal)) {
          next.goal = undefined;
          next.target_weight_kg = null;
        }
      }
      if (patch.goal !== undefined && patch.goal !== d.goal) next.target_weight_kg = null;
      if (patch.weight_kg !== undefined && patch.weight_kg !== d.weight_kg) next.target_weight_kg = null;
      if (patch.training_days !== undefined || patch.daysAnswer !== undefined) next.splitChosen = false;
      return next;
    });
  };

  // Goal weight: the full range is always selectable, whatever the current
  // weight. The selected value itself says whether the user wants to lose or gain.
  const loss = direction < 0;
  const [targetMin, targetMax] = targetRange;
  const targetDefault = clamp(snap(draft.weight_kg + (loss ? -5 : 5), 0.5), targetMin, targetMax);
  const targetValue = clamp(draft.target_weight_kg ?? targetDefault, targetMin, targetMax);
  const targetLoss = targetValue < draft.weight_kg;

  const answered: Record<StepId, boolean> = {
    language: !!draft.language, sex: !!draft.sex, goal: !!draft.goal && goalsFor(draft.sex).includes(draft.goal),
    age: true, height: true, weight: true, target: true, experience: !!draft.experience,
    days: !!draft.daysAnswer, equipment: !!draft.equipment,
    injuries: draft.injuriesAnswered || draft.injuries.length > 0, diet: !!draft.diet,
    split: draft.splitChosen, disclaimer: true,
  };

  async function next() {
    if (!answered[step] || busy) return;
    haptic.tap();
    if (step === "language" && draft.language && draft.language !== me.language) {
      setBusy(true);
      try {
        onLanguage(await setLanguage(draft.language));
      } catch {
        setError(t("error_generic"));
        return;
      } finally {
        setBusy(false);
      }
    }
    if (step === "target") update({ target_weight_kg: targetValue });
    if (stepIndex < steps.length - 1) {
      setStepIndex(stepIndex + 1);
      return;
    }
    await finish();
  }

  function skipTarget() {
    haptic.tap();
    update({ target_weight_kg: null });
    setStepIndex(stepIndex + 1);
  }

  /** The split detail's "choose this split": it becomes the plan's training days. */
  function chooseSplit(days: number) {
    haptic.success();
    setError(null);
    const patch: Partial<Draft> = { training_days: days, splitChosen: true };
    setDraft((d) => ({ ...d, ...patch }));
    if (stepIndex < steps.length - 1) setStepIndex(stepIndex + 1);
    else void finish(patch);
  }

  async function finish(overrides: Partial<Draft> = {}) {
    setBusy(true);
    setError(null);
    const d = { ...draft, ...overrides };
    // Keep any goal weight inside the allowed range. The direction comes from
    // the value itself (below current = lose, above = gain).
    const target = d.target_weight_kg !== null
      && targetMin <= d.target_weight_kg && d.target_weight_kg <= targetMax
      ? d.target_weight_kg : null;
    try {
      if (!me.disclaimer_accepted) await acceptDisclaimer();
      const saved = await saveProfile({
        goal: d.goal!, age: d.age, sex: d.sex!, height_cm: d.height_cm,
        weight_kg: d.weight_kg, experience: d.experience!, training_days: d.training_days!,
        equipment: d.equipment!, injuries: d.injuries, diet: d.diet!,
        target_weight_kg: target,
      });
      haptic.success();
      localStorage.removeItem(draftKey());
      onDone(saved);
    } catch (err) {
      haptic.error();
      const invalid = fieldError(err);
      if (invalid) {
        // Jump back to the question the server rejected.
        const index = steps.indexOf(STEP_FOR_FIELD[invalid.field] ?? "goal");
        if (index >= 0) setStepIndex(index);
        setError(t((KNOWN_ERRORS.has(invalid.error) ? invalid.error : "err_generic") as TextKey));
      } else {
        setError(t("error_generic"));
      }
    } finally {
      setBusy(false);
    }
  }

  const isLast = stepIndex === steps.length - 1;
  const continueLabel = step === "disclaimer" ? t("disclaimer_accept") : t(isLast ? "finish" : "continue");
  const hint = HINTS[step];

  return (
    <main className="onboarding">
      <header className="step-header">
        {back ? (
          <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}>
            <ArrowLeft />
          </button>
        ) : <span className="round-spacer" />}
        <div className="step-progress">
          <span className="step-count">{t("step_of", { n: stepIndex + 1, total: steps.length })}</span>
          <span className="progress-bar" role="progressbar" aria-valuemin={1} aria-valuemax={steps.length}
                aria-valuenow={stepIndex + 1}>
            <span style={{ width: ((stepIndex + 1) / steps.length) * 100 + "%" }} />
          </span>
        </div>
        <button type="button" className="round-button round-close" aria-label={t("close")}
                onClick={() => { haptic.tap(); closeApp(); }}>
          <Close />
        </button>
      </header>

      <section className="step" key={step}>
        <h1 className="step-title">{t(("q_" + step) as TextKey)}</h1>
        {hint && <p className="step-hint">{t(hint)}</p>}
        <StepBody step={step} draft={draft} update={update} rules={rules} t={t}
                  goalsFor={goalsFor} targetValue={targetValue} targetMin={targetMin} targetMax={targetMax}
                  targetLoss={targetLoss} onChooseSplit={chooseSplit} />
        {error && <p className="field-error" role="alert">{error}</p>}
      </section>

      <footer className="step-footer">
        <button type="button" className="button-primary" disabled={!answered[step] || busy}
                onClick={() => void next()}>
          {busy ? <span className="spinner spinner-small" aria-label={t("saving")} /> : continueLabel}
        </button>
        {step === "target" && (
          <button type="button" className="button-link" onClick={skipTarget}>{t("skip")}</button>
        )}
      </footer>
    </main>
  );
}

interface BodyProps {
  step: StepId;
  draft: Draft;
  update: (patch: Partial<Draft>) => void;
  rules: AppConfig["profile_rules"];
  t: T;
  goalsFor: (sex?: Sex) => Goal[];
  targetValue: number;
  targetMin: number;
  targetMax: number;
  targetLoss: boolean;
  onChooseSplit: (days: number) => void;
}

const LB = 0.45359237;

const GOAL_ICONS: Record<Goal, ReactNode> = {
  bulk: <TrendUp />, lean_bulk: <Leaf />, recomp: <Scale />,
  lose_weight: <TrendDown />, gain_muscle: <Dumbbell />, improve_health: <Heart />, get_in_shape: <Sparkles />,
};

function StepBody({ step, draft, update, rules, t, goalsFor, targetValue, targetMin, targetMax, targetLoss,
                    onChooseSplit }: BodyProps) {
  switch (step) {
    case "language":
      return <Options label={t("q_language")} selected={draft.language ? [draft.language] : []}
                      options={LANGUAGES.map((l) => ({ value: l.code, label: l.label }))}
                      onToggle={(language) => update({ language })} />;

    case "sex": {
      const icons: Record<Sex, ReactNode> = { male: <Male />, female: <Female />, unspecified: <Neutral /> };
      return <Options label={t("q_sex")} selected={draft.sex ? [draft.sex] : []}
                      options={rules.sexes.map((s) => ({ value: s, label: t(("sex_" + s) as TextKey), icon: icons[s] }))}
                      onToggle={(sex) => update({ sex })} />;
    }

    case "goal":
      return <Options card label={t("q_goal")} selected={draft.goal ? [draft.goal] : []}
                      options={goalsFor(draft.sex).map((g) => ({
                        value: g, label: t(("goal_" + g) as TextKey), hint: t(("goal_" + g + "_hint") as TextKey),
                        icon: GOAL_ICONS[g], art: GOAL_ART[g],
                      }))}
                      onToggle={(goal) => update({ goal })} />;

    case "age":
      return <Ruler label={t("q_age")} value={draft.age} min={rules.age[0]} max={rules.age[1]} step={1}
                    onChange={(age) => update({ age })} />;

    case "height": {
      const [lo, hi] = rules.height_cm;
      const inLo = Math.ceil(lo / 2.54);
      const inHi = Math.floor(hi / 2.54);
      return (
        <>
          <UnitToggle label={t("unit")} value={draft.heightUnit} onChange={(heightUnit) => update({ heightUnit })}
                      options={[{ value: "cm", label: t("unit_cm") }, { value: "in", label: t("unit_in") }]} />
          {draft.heightUnit === "cm" ? (
            <Ruler label={t("q_height")} value={clamp(Math.round(draft.height_cm), lo, hi)} min={lo} max={hi}
                   step={1} major={10} onChange={(height_cm) => update({ height_cm })} />
          ) : (
            <Ruler label={t("q_height")} value={clamp(cmToIn(draft.height_cm), inLo, inHi)} min={inLo} max={inHi}
                   step={1} major={6} format={formatFeet}
                   onChange={(inches) => update({ height_cm: inToCm(inches) })} />
          )}
        </>
      );
    }

    case "weight":
    case "target": {
      const isTarget = step === "target";
      const kg = isTarget ? targetValue : draft.weight_kg;
      const min = isTarget ? targetMin : rules.weight_kg[0];
      const max = isTarget ? targetMax : rules.weight_kg[1];
      const set = (value: number) => update(isTarget ? { target_weight_kg: value } : { weight_kg: value });
      return (
        <>
          <UnitToggle label={t("unit")} value={draft.weightUnit} onChange={(weightUnit) => update({ weightUnit })}
                      options={[{ value: "kg", label: t("unit_kg") }, { value: "lb", label: t("unit_lb") }]} />
          {draft.weightUnit === "kg" ? (
            <Ruler label={t(("q_" + step) as TextKey)} value={snap(kg, 0.5)} min={snap(min, 0.5)} max={max}
                   step={0.5} onChange={set} />
          ) : (
            <Ruler label={t(("q_" + step) as TextKey)} value={clamp(kgToLb(kg), Math.ceil(min / LB), Math.floor(max / LB))}
                   min={Math.ceil(min / LB)} max={Math.floor(max / LB)} step={1} major={10}
                   onChange={(lb) => set(lbToKg(lb))} />
          )}
          {isTarget && targetValue !== draft.weight_kg && (
            <p className="step-note">
              {t(targetLoss ? "target_loss" : "target_gain", { kg: Math.round(Math.abs(kg - draft.weight_kg) * 10) / 10 })}
            </p>
          )}
        </>
      );
    }

    case "experience":
      return <Options card label={t("q_experience")} selected={draft.experience ? [draft.experience] : []}
                      options={rules.experience.map((e) => ({
                        value: e, label: t(("exp_" + e) as TextKey), hint: t(("exp_" + e + "_hint") as TextKey),
                        art: experienceArt(draft.sex)[e],
                      }))}
                      onToggle={(experience) => update({ experience })} />;

    case "days": {
      const [lo, hi] = rules.training_days;
      return (
        <div className="day-pills" role="radiogroup" aria-label={t("q_days")}>
          {Array.from({ length: hi - lo + 1 }, (_, i) => lo + i).map((n) => (
            <button key={n} type="button" role="radio" aria-checked={draft.daysAnswer === n}
                    className={"day-pill" + (draft.daysAnswer === n ? " day-pill-on" : "")}
                    onClick={() => { haptic.select(); update({ daysAnswer: n, training_days: n }); }}>
              {n}
            </button>
          ))}
        </div>
      );
    }

    case "equipment":
      return <Options card label={t("q_equipment")} selected={draft.equipment ? [draft.equipment] : []}
                      options={rules.equipment.map((e) => ({
                        value: e, label: t(("eq_" + e) as TextKey), hint: t(("eq_" + e + "_hint") as TextKey),
                        art: EQUIPMENT_ART[e], artFit: "cover" as const,
                      }))}
                      onToggle={(equipment) => update({ equipment })} />;

    case "injuries": {
      type Choice = Injury | "none";
      const selected: Choice[] = draft.injuries.length ? draft.injuries : draft.injuriesAnswered ? ["none"] : [];
      const options = [
        ...rules.injuries.map((i) => ({ value: i as Choice, label: t(("inj_" + i) as TextKey) })),
        { value: "none" as Choice, label: t("inj_none") },
      ];
      return <Options multi label={t("q_injuries")} selected={selected} options={options}
                      onToggle={(value) => {
                        if (value === "none") {
                          update({ injuries: [], injuriesAnswered: true });
                          return;
                        }
                        const has = draft.injuries.includes(value);
                        update({
                          injuriesAnswered: true,
                          injuries: has ? draft.injuries.filter((i) => i !== value) : [...draft.injuries, value],
                        });
                      }} />;
    }

    case "diet":
      return <Options card label={t("q_diet")} selected={draft.diet ? [draft.diet] : []}
                      options={rules.diets.map((d) => ({
                        value: d, label: t(("diet_" + d) as TextKey), art: DIET_ART[d],
                      }))}
                      onToggle={(diet) => update({ diet })} />;

    case "split":
      return <SplitStep draft={draft} t={t} onChoose={onChooseSplit} />;

    case "disclaimer":
      return (
        <div className="card disclaimer">
          {t("disclaimer_text").split("\n").map((line, i) => <p key={i}>{line}</p>)}
        </div>
      );
  }
}

/**
 * Split choice: the recommended split (matching the days answer) at the top,
 * a separator, then the others. Tapping one loads its days and exercises from
 * the plan generator and shows them in a sheet.
 */
function SplitStep({ draft, t, onChoose }: { draft: Draft; t: T; onChoose: (days: number) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const [data, setData] = useState<PlanPreview | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const cache = useRef(new Map<number, PlanPreview>());
  const request = useRef(0);

  // The recommendation follows the days answer, not the split already chosen.
  const recommended = SPLIT_CHOICES.find((c) => c.days === draft.daysAnswer) ?? SPLIT_CHOICES[0];
  const others = SPLIT_CHOICES.filter((c) => c !== recommended);
  const chosen = draft.splitChosen ? SPLIT_CHOICES.find((c) => c.days === draft.training_days) : undefined;
  const current = SPLIT_CHOICES.find((c) => c.days === open);

  async function openSplit(days: number) {
    haptic.select();
    setOpen(days);
    const cached = cache.current.get(days);
    if (cached) {
      setData(cached);
      setStatus("ready");
      return;
    }
    const id = ++request.current;
    setData(null);
    setStatus("loading");
    try {
      const preview = await previewPlan({
        experience: draft.experience!, equipment: draft.equipment!, injuries: draft.injuries, days,
      });
      cache.current.set(days, preview);
      if (id !== request.current) return;
      setData(preview);
      setStatus("ready");
    } catch {
      if (id !== request.current) return;
      setStatus("error");
    }
  }

  function close() {
    request.current += 1;
    setOpen(null);
  }

  const card = (choice: SplitChoice, wide: boolean) => (
    <button key={choice.days} type="button" aria-pressed={chosen === choice}
            className={"split-card" + (wide ? " split-card-wide" : "")
              + (chosen === choice ? " split-card-on" : "")}
            onClick={() => void openSplit(choice.days)}>
      <span className="split-card-name">{t(choice.labelKey)}</span>
      <span className="split-card-hint">{t(choice.hintKey)}</span>
      {wide && <span className="split-badge">{t("split_recommended")}</span>}
    </button>
  );

  return (
    <div className="split-picker">
      <div className="split-row">{card(recommended, true)}</div>
      <div className="split-separator" aria-hidden />
      <div className="split-grid">{others.map((choice) => card(choice, false))}</div>

      {open !== null && current && (
        <div className="sheet-backdrop" onClick={close}>
          <div className="sheet split-sheet" onClick={(event) => event.stopPropagation()}>
            <div className="sheet-handle" />
            {status === "loading" && (
              <p className="center-text"><span className="spinner" aria-label={t("split_loading")} /></p>
            )}
            {status === "error" && (
              <div className="split-error">
                <p className="field-error" role="alert">{t("split_error")}</p>
                <button type="button" className="button-link" onClick={() => void openSplit(open)}>
                  {t("retry")}
                </button>
              </div>
            )}
            {status === "ready" && data && (
              <>
                <h2 className="sheet-title">{t(current.labelKey)}</h2>
                <p className="split-sheet-meta">{t("split_days", { n: data.days.length })}</p>
                <div className="split-days">
                  {data.days.map((day, index) => (
                    <section className="split-day" key={index}>
                      <h3 className="split-day-name">
                        {t(("plan_day_" + day.name_key) as TextKey)}{day.suffix ? " " + day.suffix : ""}
                      </h3>
                      <ul className="split-exercises">
                        {day.exercises.map((exercise) => (
                          <li key={exercise.exercise_id} className="split-exercise">
                            <span className="split-exercise-name">{exercise.name}</span>
                            <span className="split-exercise-meta">
                              {exercise.sets} × {repsText(exercise, t)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ))}
                </div>
                <div className="split-actions">
                  <button type="button" className="button-primary"
                          onClick={() => { close(); onChoose(current.days); }}>
                    {t("split_choose")}
                  </button>
                  <button type="button" className="button-link" onClick={close}>
                    {t("split_other_choice")}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
