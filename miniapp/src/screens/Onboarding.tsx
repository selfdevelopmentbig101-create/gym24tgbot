/*
 * Mini App onboarding: one question per screen, "n of N" progress (reference image 3).
 * Answers are kept on this device until saved, so closing the app doesn't lose them.
 * Everything is validated again by the server (same rules as the bot's onboarding).
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  acceptDisclaimer, fieldError, saveProfile, setLanguage,
  type AppConfig, type Diet, type Equipment, type Experience, type Goal, type Injury,
  type LanguageCode, type Me, type ProfileSaved, type Sex,
} from "../lib/api";
import { bindNativeBack, closeApp, haptic, localUserKey } from "../lib/telegram";
import { clamp, cmToIn, formatFeet, inToCm, kgToLb, lbToKg, snap, type HeightUnit, type WeightUnit } from "../lib/units";
import type { TextKey } from "../i18n";
import { ArrowLeft, Close, Female, Leaf, Male, Neutral, Scale, TrendUp } from "../components/Icons";
import { Options, UnitToggle } from "../components/Options";
import { Ruler } from "../components/Ruler";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

interface Draft {
  language?: LanguageCode;
  goal?: Goal;
  age: number;
  sex?: Sex;
  height_cm: number;
  weight_kg: number;
  target_weight_kg: number | null;
  experience?: Experience;
  training_days?: number;
  equipment?: Equipment;
  injuries: Injury[];
  injuriesAnswered: boolean;
  diet?: Diet;
  heightUnit: HeightUnit;
  weightUnit: WeightUnit;
}

type StepId = "language" | "goal" | "age" | "sex" | "height" | "weight" | "target" | "experience"
  | "days" | "equipment" | "injuries" | "diet" | "disclaimer";

const LANGUAGES: { code: LanguageCode; label: string }[] = [
  { code: "en", label: "English" }, { code: "ru", label: "Русский" }, { code: "uz", label: "O‘zbekcha" },
];

const HINTS: Partial<Record<StepId, TextKey>> = {
  age: "h_age", target: "h_target", days: "h_days", injuries: "h_injuries",
};

const KNOWN_ERRORS = new Set(["err_age", "err_height", "err_weight", "err_target_weight", "err_generic"]);

const STEP_FOR_FIELD: Record<string, StepId> = {
  goal: "goal", age: "age", sex: "sex", height_cm: "height", weight_kg: "weight",
  target_weight_kg: "target", experience: "experience", training_days: "days",
  equipment: "equipment", injuries: "injuries", diet: "diet",
};

const draftKey = () => "gym24.onboarding.v1." + localUserKey();

function loadDraft(): Draft {
  const fresh: Draft = {
    age: 25, height_cm: 175, weight_kg: 70, target_weight_kg: null, injuries: [],
    injuriesAnswered: false, heightUnit: "cm", weightUnit: "kg",
  };
  try {
    const saved = JSON.parse(localStorage.getItem(draftKey()) ?? "null");
    return saved && typeof saved === "object" ? { ...fresh, ...saved } : fresh;
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
  const [draft, setDraft] = useState<Draft>(loadDraft);
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Asked once at the start, even after the choice is saved mid-onboarding.
  const [askLanguage] = useState(!me.language);
  const [askDisclaimer] = useState(!me.disclaimer_accepted);

  const steps = useMemo<StepId[]>(() => {
    const list: StepId[] = [];
    if (askLanguage) list.push("language");
    list.push("goal", "age", "sex", "height", "weight");
    if (draft.goal !== "recomp") list.push("target");
    list.push("experience", "days", "equipment", "injuries", "diet");
    if (askDisclaimer) list.push("disclaimer");
    return list;
  }, [askLanguage, askDisclaimer, draft.goal]);

  const step = steps[Math.min(stepIndex, steps.length - 1)];

  useEffect(() => {
    localStorage.setItem(draftKey(), JSON.stringify(draft));
  }, [draft]);

  const back = stepIndex > 0 ? () => { haptic.tap(); setError(null); setStepIndex((i) => i - 1); } : null;
  useEffect(() => bindNativeBack(back), [stepIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (patch: Partial<Draft>) => { setError(null); setDraft((d) => ({ ...d, ...patch })); };

  // The goal weight must stay above the current weight.
  const targetMin = snap(draft.weight_kg + 0.5, 0.5);
  const targetValue = clamp(draft.target_weight_kg ?? snap(draft.weight_kg + 5, 0.5), targetMin, rules.weight_kg[1]);

  const answered: Record<StepId, boolean> = {
    language: !!draft.language, goal: !!draft.goal, age: true, sex: !!draft.sex, height: true, weight: true,
    target: true, experience: !!draft.experience, days: !!draft.training_days, equipment: !!draft.equipment,
    injuries: draft.injuriesAnswered || draft.injuries.length > 0, diet: !!draft.diet, disclaimer: true,
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

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      if (!me.disclaimer_accepted) await acceptDisclaimer();
      const saved = await saveProfile({
        goal: draft.goal!, age: draft.age, sex: draft.sex!, height_cm: draft.height_cm,
        weight_kg: draft.weight_kg, experience: draft.experience!, training_days: draft.training_days!,
        equipment: draft.equipment!, injuries: draft.injuries, diet: draft.diet!,
        target_weight_kg: draft.goal === "recomp" ? null : draft.target_weight_kg,
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
                  targetValue={targetValue} targetMin={targetMin} />
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
  targetValue: number;
  targetMin: number;
}

const LB = 0.45359237;

function StepBody({ step, draft, update, rules, t, targetValue, targetMin }: BodyProps) {
  switch (step) {
    case "language":
      return <Options label={t("q_language")} selected={draft.language ? [draft.language] : []}
                      options={LANGUAGES.map((l) => ({ value: l.code, label: l.label }))}
                      onToggle={(language) => update({ language })} />;

    case "goal": {
      const icons: Record<Goal, ReactNode> = { bulk: <TrendUp />, lean_bulk: <Leaf />, recomp: <Scale /> };
      return <Options label={t("q_goal")} selected={draft.goal ? [draft.goal] : []}
                      options={rules.goals.map((g) => ({
                        value: g, label: t(("goal_" + g) as TextKey), hint: t(("goal_" + g + "_hint") as TextKey),
                        icon: icons[g],
                      }))}
                      onToggle={(goal) => update({ goal })} />;
    }

    case "age":
      return <Ruler label={t("q_age")} value={draft.age} min={rules.age[0]} max={rules.age[1]} step={1}
                    onChange={(age) => update({ age })} />;

    case "sex": {
      const icons: Record<Sex, ReactNode> = { male: <Male />, female: <Female />, unspecified: <Neutral /> };
      return <Options label={t("q_sex")} selected={draft.sex ? [draft.sex] : []}
                      options={rules.sexes.map((s) => ({ value: s, label: t(("sex_" + s) as TextKey), icon: icons[s] }))}
                      onToggle={(sex) => update({ sex })} />;
    }

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
                   step={1} onChange={(height_cm) => update({ height_cm })} />
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
      const max = rules.weight_kg[1];
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
          {isTarget && (
            <p className="step-note">{t("target_gain", { kg: Math.round((kg - draft.weight_kg) * 10) / 10 })}</p>
          )}
        </>
      );
    }

    case "experience":
      return <Options label={t("q_experience")} selected={draft.experience ? [draft.experience] : []}
                      options={rules.experience.map((e) => ({
                        value: e, label: t(("exp_" + e) as TextKey), hint: t(("exp_" + e + "_hint") as TextKey),
                      }))}
                      onToggle={(experience) => update({ experience })} />;

    case "days": {
      const [lo, hi] = rules.training_days;
      return (
        <div className="day-pills" role="radiogroup" aria-label={t("q_days")}>
          {Array.from({ length: hi - lo + 1 }, (_, i) => lo + i).map((n) => (
            <button key={n} type="button" role="radio" aria-checked={draft.training_days === n}
                    className={"day-pill" + (draft.training_days === n ? " day-pill-on" : "")}
                    onClick={() => { haptic.select(); update({ training_days: n }); }}>
              {n}
            </button>
          ))}
        </div>
      );
    }

    case "equipment":
      return <Options label={t("q_equipment")} selected={draft.equipment ? [draft.equipment] : []}
                      options={rules.equipment.map((e) => ({
                        value: e, label: t(("eq_" + e) as TextKey), hint: t(("eq_" + e + "_hint") as TextKey),
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
      return <Options label={t("q_diet")} selected={draft.diet ? [draft.diet] : []}
                      options={rules.diets.map((d) => ({ value: d, label: t(("diet_" + d) as TextKey) }))}
                      onToggle={(diet) => update({ diet })} />;

    case "disclaimer":
      return (
        <div className="card disclaimer">
          {t("disclaimer_text").split("\n").map((line, i) => <p key={i}>{line}</p>)}
        </div>
      );
  }
}
