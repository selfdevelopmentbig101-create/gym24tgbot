/*
 * Plan tab home (reference image 2): month calendar with done / missed / planned
 * markers, then the current program card.
 */
import { useEffect, useState } from "react";
import { getCalendar, getPrograms, type CalendarMonth, type Programs } from "../lib/api";
import { navigate } from "../lib/router";
import { haptic } from "../lib/telegram";
import { dayName, formatDate, percent, programName, type T } from "../lib/plan";
import type { TextKey } from "../i18n";
import { ChevronLeft, ChevronRight } from "../components/Icons";

function monthKey(date: Date): string {
  return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0");
}

function shift(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  return monthKey(new Date(y, m - 1 + by, 1));
}

export function PlanHome({ t, locale }: { t: T; locale: string }) {
  const [month, setMonth] = useState(() => monthKey(new Date()));
  const [calendar, setCalendar] = useState<CalendarMonth | null>(null);
  const [programs, setPrograms] = useState<Programs | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getPrograms().then(setPrograms).catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    let live = true;
    getCalendar(month).then((c) => { if (live) setCalendar(c); }).catch(() => setFailed(true));
    return () => { live = false; };
  }, [month]);

  const current = programs?.current;

  return (
    <main className="plan-home">
      <h1 className="screen-title left">{t("plan_title")}</h1>
      {failed && <p className="muted center-text" role="alert">{t("error_generic")}</p>}

      <section className="card calendar" aria-label={t("calendar")}>
        <header className="calendar-head">
          <h2 className="calendar-month">
            {new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" })
              .format(new Date(month + "-15T12:00:00"))}
          </h2>
          <div className="calendar-nav">
            <button type="button" className="icon-button" aria-label={t("prev_month")}
                    onClick={() => { haptic.select(); setMonth(shift(month, -1)); }}><ChevronLeft /></button>
            <button type="button" className="icon-button" aria-label={t("next_month")}
                    onClick={() => { haptic.select(); setMonth(shift(month, 1)); }}><ChevronRight /></button>
          </div>
        </header>
        <Month calendar={calendar} month={month} locale={locale} t={t} />
        {calendar && (
          <p className="calendar-summary">{t("calendar_summary", { done: calendar.done, planned: calendar.planned })}</p>
        )}
      </section>

      <h2 className="section-label">{t("your_plan")}</h2>
      {programs && !current && (
        <section className="card">
          <p className="muted">{t("no_current_program")}</p>
          <button type="button" className="button-primary" onClick={() => navigate({ name: "programs" })}>
            {t("all_programs")}
          </button>
        </section>
      )}
      {current && (
        <button type="button" className="card program-card program-card-current"
                onClick={() => { haptic.tap(); navigate({ name: "program", id: current.id }); }}>
          <span className="badge-current">{t("current")}</span>
          <span className="program-name">{programName(current, t)}</span>
          <span className="program-sub">{t(("tgoal_" + current.goal) as TextKey)} · {t("per_week", { n: current.workouts_per_week })}</span>
          <span className="program-progress">
            <span>{t("week_of", { n: current.week ?? 1, total: current.weeks })}</span>
            <span>{t("percent_done", { n: percent(current.completed, current.total) })}</span>
          </span>
          <span className="progress-track"><span style={{ width: percent(current.completed, current.total) + "%" }} /></span>
          {current.started_on && current.ends_on && (
            <span className="program-dates">
              <span>{t("started", { date: formatDate(current.started_on, locale) })}</span>
              <span>{t("ends", { date: formatDate(current.ends_on, locale) })}</span>
            </span>
          )}
          {current.next_day_index !== null && current.day_names[current.next_day_index] && (
            <span className="program-next">
              {t("upcoming", { name: dayName(current.day_names[current.next_day_index], t) })}
            </span>
          )}
        </button>
      )}

      <button type="button" className="button-secondary" onClick={() => { haptic.tap(); navigate({ name: "programs" }); }}>
        {t("all_programs")}
      </button>
    </main>
  );
}

function Month({ calendar, month, locale, t }: { calendar: CalendarMonth | null; month: string; locale: string; t: T }) {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const lead = (first.getDay() + 6) % 7; // Monday first
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(locale, { weekday: "narrow" }).format(new Date(2024, 0, 1 + i)));
  const today = new Date();
  const todayIso = monthKey(today) + "-" + String(today.getDate()).padStart(2, "0");
  return (
    <div className="month" role="grid">
      {weekdays.map((w, i) => <span key={"w" + i} className="weekday" role="columnheader">{w}</span>)}
      {Array.from({ length: lead }, (_, i) => <span key={"e" + i} />)}
      {(calendar?.days ?? []).map((d) => (
        <span key={d.date} role="gridcell"
              className={"cal-day cal-" + d.status + (d.date === todayIso ? " cal-today" : "")}
              aria-label={d.date + ": " + t(("status_" + d.status) as TextKey)}>
          {Number(d.date.slice(8))}
        </span>
      ))}
    </div>
  );
}
