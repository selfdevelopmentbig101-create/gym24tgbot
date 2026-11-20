/*
 * "Your plan is ready" (reference image 1): estimated goal date, then the daily
 * calorie and macro breakdown. Every number is shown: Gym24 has no locked content.
 * Until the Home tab exists (Stage 7), this is also the app's main screen.
 */
import type { ReactNode } from "react";
import type { LanguageCode, Targets } from "../lib/api";
import { closeApp, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Bread, Drop, Drumstick, Flame, Road, Sparkles } from "../components/Icons";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const NOTE_KEYS = new Set(["note_high_bmi_bulk", "note_under_18"]);

interface Props {
  targets: Targets;
  lang: LanguageCode;
  t: T;
  justFinished: boolean;
  planReady: boolean;
  languagePicker: ReactNode;
}

export function PlanReady({ targets, lang, t, justFinished, planReady, languagePicker }: Props) {
  const locale = lang === "uz" ? "uz-Latn" : lang;
  const number = new Intl.NumberFormat(locale);
  const dateText = (iso: string) =>
    new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" })
      .format(new Date(iso + "T12:00:00"));
  const [gainLow, gainHigh] = targets.weekly_gain_kg;
  const loss = gainHigh < 0;
  const maintain = gainHigh === 0;
  const kg = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });

  return (
    <main className="plan-ready">
      <h1 className="screen-title">{t(justFinished ? "ready_title" : "targets_title")}</h1>

      {targets.goal ? (
        <section className="card goal-card">
          <div>
            <p className="goal-label">{t("goal_date")}</p>
            <p className="goal-date">{dateText(targets.goal.estimated_date)} <span className="sparkle"><Sparkles /></span></p>
            <p className="goal-range">
              {t("goal_range", {
                kg: kg.format(targets.goal.target_weight_kg),
                from: dateText(targets.goal.earliest_date),
                to: dateText(targets.goal.latest_date),
              })}
            </p>
          </div>
          <Road />
        </section>
      ) : (
        <section className="card goal-card">
          <div>
            <p className="goal-label">
              {t(!maintain ? "goal_no_target_title"
                : targets.profile_goal === "improve_health" ? "goal_card_maintain_title" : "goal_card_recomp_title")}
            </p>
            <p className="goal-range">
              {t(!maintain ? "goal_no_target"
                : targets.profile_goal === "improve_health" ? "goal_card_maintain" : "goal_card_recomp")}
            </p>
          </div>
          <Road />
        </section>
      )}

      <h2 className="section-label">{t("breakdown")}</h2>
      <div className="macro-grid">
        <Macro icon={<Flame />} tone="calories" label={t("calories")}
               value={t("kcal_value", { n: number.format(targets.calories) })} />
        <Macro icon={<Drumstick />} tone="protein" label={t("protein")}
               value={t("g_value", { n: number.format(targets.protein_g) })} />
        <Macro icon={<Bread />} tone="carbs" label={t("carbs")}
               value={t("g_value", { n: number.format(targets.carbs_g) })} />
        <Macro icon={<Drop />} tone="fat" label={t("fat")}
               value={t("g_value", { n: number.format(targets.fat_g) })} />
      </div>

      <section className="card facts">
        <p>
          {loss
            ? t("loss_per_week", { low: kg.format(Math.abs(gainHigh)), high: kg.format(Math.abs(gainLow)) })
            : maintain
              ? t("recomp_per_week")
              : t("gain_per_week", { low: kg.format(gainLow), high: kg.format(gainHigh) })}
        </p>
        <p className="muted small">
          {maintain
            ? t("maintenance", { tdee: number.format(targets.tdee), surplus: 0 })
            : loss
              ? t("maintenance_deficit", {
                  tdee: number.format(targets.tdee),
                  deficit: number.format(Math.max(0, -targets.surplus)),
                })
              : t("maintenance", {
                  tdee: number.format(targets.tdee), surplus: number.format(Math.max(0, targets.surplus)),
                })}
        </p>
        {targets.notes.filter((n) => NOTE_KEYS.has(n)).map((note) => (
          <p key={note} className="note">{t(note as TextKey)}</p>
        ))}
      </section>

      {planReady && <p className="muted small center-text">{t("plan_in_chat")}</p>}

      <button type="button" className="button-primary" onClick={() => { haptic.tap(); closeApp(); }}>
        {t("back_to_chat")}
      </button>

      {languagePicker}
    </main>
  );
}

function Macro({ icon, tone, label, value }: { icon: ReactNode; tone: string; label: string; value: string }) {
  return (
    <div className="macro">
      <span className={"macro-icon macro-" + tone}>{icon}</span>
      <span className="macro-label">{label}</span>
      <span className="macro-value">{value}</span>
    </div>
  );
}
