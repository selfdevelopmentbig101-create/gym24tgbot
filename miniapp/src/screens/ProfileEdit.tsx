/*
 * Edit profile: the onboarding answers on one screen. Only changed answers are
 * sent (PATCH /api/profile). The server validates them like onboarding and
 * rebuilds the plan only when equipment, level, days or injuries change.
 */
import { useEffect, useState } from "react";
import { fieldError, type AppConfig, type Profile } from "../lib/api";
import { getProfile, patchProfile } from "../lib/profileApi";
import { goBack } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Stepper } from "../components/Stepper";
import { ArrowLeft } from "../components/Icons";
import "./profile.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

function Choice<V extends string | number>({ label, options, value, text, onChange }: {
  label: string; options: readonly V[]; value: V; text: (v: V) => string; onChange: (v: V) => void;
}) {
  return (
    <fieldset className="edit-field">
      <legend className="field-label">{label}</legend>
      <div className="chips wrap">
        {options.map((option) => (
          <button key={String(option)} type="button" className={"chip" + (value === option ? " chip-on" : "")}
                  aria-pressed={value === option} onClick={() => { haptic.select(); onChange(option); }}>
            {text(option)}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function ProfileEdit({ t, config }: { t: T; config: AppConfig | null }) {
  const [original, setOriginal] = useState<Profile | null>(null);
  const [form, setForm] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => bindNativeBack(() => goBack({ name: "profile" })), []);
  useEffect(() => {
    getProfile().then((p) => { setOriginal(p); setForm(p); }).catch(() => setError(t("error_generic")));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const rules = config?.profile_rules;
  if (!form || !original || !rules) {
    return (
      <main className="profile">
        {error ? <p className="notice" role="alert">{error}</p> : <div className="spinner center-spinner" aria-label={t("loading")} />}
      </main>
    );
  }

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => {
    setMessage(null);
    setError(null);
    setForm({ ...form, [key]: value });
  };

  async function save() {
    if (!form || !original) return;
    const changes: Record<string, unknown> = {};
    (Object.keys(form) as (keyof Profile)[]).forEach((key) => {
      if (JSON.stringify(form[key]) !== JSON.stringify(original[key])) changes[key] = form[key];
    });
    if (form.goal === "recomp" && original.target_weight_kg !== null) changes.target_weight_kg = null;
    if (Object.keys(changes).length === 0) {
      setMessage(t("edit_nothing"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await patchProfile(changes as Partial<Profile>);
      haptic.success();
      setOriginal(saved.profile);
      setForm(saved.profile);
      setMessage(t("edit_saved") + (saved.plan_rebuilt ? " " + t("edit_plan_rebuilt") : ""));
    } catch (e) {
      haptic.error();
      const bad = fieldError(e);
      setError(bad ? t(bad.error as TextKey) : t("error_generic"));
    } finally {
      setBusy(false);
    }
  }

  const days = Array.from({ length: rules.training_days[1] - rules.training_days[0] + 1 }, (_, i) => rules.training_days[0] + i);
  const hasTarget = form.target_weight_kg !== null;

  return (
    <main className="profile">
      <header className="editor-header">
        <button type="button" className="round-button round-back" aria-label={t("back")}
                onClick={() => goBack({ name: "profile" })}><ArrowLeft /></button>
        <h1 className="editor-title">{t("edit_title")}</h1>
        <span />
      </header>

      <section className="card edit-card">
        <Choice label={t("pf_goal")} options={rules.goals} value={form.goal}
                text={(g) => t(("pf_goal_" + g) as TextKey)} onChange={(g) => set("goal", g)} />
        <Stepper label={t("pf_weight")} value={form.weight_kg} step={0.5} min={rules.weight_kg[0]} max={rules.weight_kg[1]}
                 onChange={(v) => set("weight_kg", v)} />
        {form.goal !== "recomp" && (
          <div className="edit-field">
            <label className="toggle-row">
              <input type="checkbox" checked={hasTarget}
                     onChange={(e) => set("target_weight_kg", e.target.checked
                       ? Math.min(rules.weight_kg[1], Math.round((form.weight_kg + 5) * 2) / 2) : null)} />
              <span>{t("pf_target_set")}</span>
            </label>
            {hasTarget && (
              <Stepper label={t("pf_target")} value={form.target_weight_kg ?? form.weight_kg} step={0.5}
                       min={Math.min(rules.weight_kg[1], form.weight_kg + 0.5)} max={rules.weight_kg[1]}
                       onChange={(v) => set("target_weight_kg", v)} />
            )}
          </div>
        )}
        <Choice label={t("pf_days")} options={days} value={form.training_days} text={(d) => String(d)}
                onChange={(d) => set("training_days", d)} />
        <Choice label={t("pf_experience")} options={rules.experience} value={form.experience}
                text={(x) => t(("pf_exp_" + x) as TextKey)} onChange={(x) => set("experience", x)} />
        <Choice label={t("pf_equipment")} options={rules.equipment} value={form.equipment}
                text={(x) => t(("pf_eq_" + x) as TextKey)} onChange={(x) => set("equipment", x)} />

        <fieldset className="edit-field">
          <legend className="field-label">{t("pf_injuries")}</legend>
          <div className="chips wrap">
            <button type="button" className={"chip" + (form.injuries.length === 0 ? " chip-on" : "")}
                    onClick={() => { haptic.select(); set("injuries", []); }}>{t("pf_injuries_none")}</button>
            {rules.injuries.map((injury) => {
              const on = form.injuries.includes(injury);
              return (
                <button key={injury} type="button" className={"chip" + (on ? " chip-on" : "")} aria-pressed={on}
                        onClick={() => {
                          haptic.select();
                          set("injuries", on ? form.injuries.filter((i) => i !== injury) : [...form.injuries, injury]);
                        }}>
                  {t(("pf_inj_" + injury) as TextKey)}
                </button>
              );
            })}
          </div>
        </fieldset>

        <Choice label={t("pf_diet")} options={rules.diets} value={form.diet}
                text={(x) => t(("pf_diet_" + x) as TextKey)} onChange={(x) => set("diet", x)} />
        <Stepper label={t("pf_age")} value={form.age} step={1} min={rules.age[0]} max={rules.age[1]}
                 onChange={(v) => set("age", Math.round(v))} />
        <Stepper label={t("pf_height")} value={form.height_cm} step={1} min={rules.height_cm[0]} max={rules.height_cm[1]}
                 onChange={(v) => set("height_cm", v)} />
        <Choice label={t("pf_sex")} options={rules.sexes} value={form.sex}
                text={(x) => t(("pf_sex_" + x) as TextKey)} onChange={(x) => set("sex", x)} />
      </section>

      {error && <p className="notice" role="alert">{error}</p>}
      {message && <p className="edit-message" role="status">{message}</p>}
      <button type="button" className="button-primary edit-save" disabled={busy} onClick={() => void save()}>
        {busy ? <span className="spinner spinner-small" /> : t("edit_save")}
      </button>
    </main>
  );
}
