/*
 * Plan tab: current program card (week x of y, % completed, frequency, upcoming
 * workout), month calendar, program details, weekly volume per muscle, and links
 * to the split editor and to all programs.
 */
import { useCallback, useEffect, useState } from "react";
import { getCalendar, getPlan, type CalendarMonth, type PlanView } from "../lib/planApi";
import { dayName, planErrorKey, programName, whenText } from "../lib/planText";
import { navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { MonthCalendar } from "../components/MonthCalendar";
import { VolumeList } from "../components/VolumeList";
import { ChevronRight } from "../components/Icons";
import "./plan.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(key: string, by: number): string {
  return monthKey(new Date(Number(key.slice(0, 4)), Number(key.slice(5, 7)) - 1 + by, 1));
}

export function Plan({ t, locale }: { t: T; locale: string }) {
  const [plan, setPlan] = useState<PlanView | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [month, setMonth] = useState(() => monthKey(new Date()));
  const [calendar, setCalendar] = useState<CalendarMonth | null>(null);
  const [calendarFailed, setCalendarFailed] = useState(false);

  const load = useCallback(() => {
    setError(null);
    getPlan().then(setPlan).catch((e) => setError(planErrorKey(e)));
  }, []);
  useEffect(load, [load]);
  useEffect(() => bindNativeBack(null), []); // a tab: no Back button

  useEffect(() => {
    let live = true;
    setCalendar(null);
    setCalendarFailed(false);
    getCalendar(month)
      .then((data) => { if (live) setCalendar(data); })
      .catch(() => { if (live) setCalendarFailed(true); });
    return () => { live = false; };
  }, [month]);

  const program = plan?.program;
  const upcoming = program?.upcoming ?? null;
  const details = program?.details;

  return (
    <main className="plan">
      <h1 className="screen-title left">{t("plan_title")}</h1>

      {error && (
        <section className="card center" role="alert">
          <p>{t(error)}</p>
          <button type="button" className="button-primary" onClick={() => { haptic.tap(); load(); }}>{t("retry")}</button>
        </section>
      )}
      {!plan && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {plan && program && details && (
        <>
          <section className="card plan-program">
            <p className="plan-eyebrow">{t("programs_current_badge")}</p>
            <h2 className="plan-program-name">{programName(program, t)}</h2>
            <p className="muted small">
              {t("plan_week", { week: program.week, weeks: program.weeks })} · {t("plan_frequency", { n: program.workouts_per_week })}
            </p>
            <div className="progress-line" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                 aria-valuenow={program.percent} aria-label={t("plan_percent", { n: program.percent })}>
              <span style={{ width: `${program.percent}%` }} />
            </div>
            <p className="small plan-percent">
              {t("plan_percent", { n: program.percent })} · {program.completed}/{program.target}
            </p>
            {upcoming && (
              <button type="button" className="plan-upcoming"
                      onClick={() => { haptic.tap(); navigate({ name: "planEdit", day: upcoming.day_id }); }}>
                <span className="plan-upcoming-text">
                  <span className="plan-upcoming-label">{t("plan_upcoming")} · {whenText(upcoming.in_days, t)}</span>
                  <span className="plan-upcoming-name">{dayName(upcoming, t)}</span>
                  <span className="muted small">
                    {t("plan_exercises_count", { n: upcoming.exercises })} · {t("plan_minutes", { n: upcoming.minutes })}
                  </span>
                </span>
                <ChevronRight />
              </button>
            )}
          </section>

          <MonthCalendar month={month} data={calendar} failed={calendarFailed} locale={locale} t={t}
                         onShift={(by) => setMonth((m) => shiftMonth(m, by))} />

          <section className="card">
            <h2 className="card-title">{t("plan_details")}</h2>
            <dl className="plan-facts">
              <div><dt>{t("plan_focus")}</dt><dd>{t(("goal_" + details.focus) as TextKey)}</dd></div>
              <div><dt>{t("plan_volume_trend")}</dt><dd>{t(("trend_" + details.volume_trend) as TextKey)}</dd></div>
              <div>
                <dt>{t("plan_intensity")}</dt>
                <dd>{t("plan_rpe", { a: details.rpe[0], b: details.rpe[1], ra: 10 - details.rpe[1], rb: 10 - details.rpe[0] })}</dd>
              </div>
              {details.rep_range && (
                <div><dt>{t("plan_rep_range")}</dt><dd>{details.rep_range[0]}–{details.rep_range[1]}</dd></div>
              )}
              <div><dt>{t("plan_duration")}</dt><dd>{t("plan_minutes", { n: details.minutes })}</dd></div>
            </dl>
          </section>

          <VolumeList volume={plan.weekly_volume} limits={plan.limits} t={t} />

          <div className="plan-actions">
            <button type="button" className="button-primary"
                    onClick={() => { haptic.tap(); navigate({ name: "planEdit" }); }}>{t("plan_edit_split")}</button>
            <button type="button" className="button-secondary"
                    onClick={() => { haptic.tap(); navigate({ name: "programs" }); }}>{t("plan_all_programs")}</button>
          </div>
        </>
      )}
    </main>
  );
}
