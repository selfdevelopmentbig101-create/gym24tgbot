/* Month calendar with day markers: done, planned, missed and rest days. Monday first. */
import type { TextKey } from "../i18n";
import type { CalendarMonth } from "../lib/planApi";
import { haptic } from "../lib/telegram";
import { ChevronRight } from "./Icons";
import { ChevronLeft } from "./PlanIcons";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const LEGEND = ["done", "planned", "missed", "rest"] as const;

export function MonthCalendar({ month, data, failed, locale, t, onShift }: {
  month: string; data: CalendarMonth | null; failed: boolean; locale: string; t: T;
  onShift: (by: number) => void;
}) {
  const year = Number(month.slice(0, 4));
  const index = Number(month.slice(5, 7)) - 1;
  const first = new Date(year, index, 1);
  const count = new Date(year, index + 1, 0).getDate();
  const lead = (first.getDay() + 6) % 7;          // blanks before the 1st (Monday first)
  const title = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(first);
  const weekday = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
  const names = Array.from({ length: 7 }, (_, i) => weekday.format(new Date(2024, 0, 1 + i))); // 1 Jan 2024 = Monday

  return (
    <section className="card calendar">
      <header className="cal-header">
        <button type="button" className="cal-nav" aria-label={t("calendar_prev")}
                onClick={() => { haptic.select(); onShift(-1); }}><ChevronLeft /></button>
        <h2 className="cal-title">{title}</h2>
        <button type="button" className="cal-nav" aria-label={t("calendar_next")}
                onClick={() => { haptic.select(); onShift(1); }}><ChevronRight /></button>
      </header>
      <div className={"cal-grid" + (data ? "" : " cal-loading")} aria-busy={!data && !failed}>
        {names.map((name, i) => <span key={"w" + i} className="cal-weekday" aria-hidden>{name}</span>)}
        {Array.from({ length: lead }, (_, i) => <span key={"b" + i} aria-hidden />)}
        {Array.from({ length: count }, (_, i) => {
          const info = data?.days[i];
          const status = info?.status ?? "none";
          const today = info !== undefined && info.date === data?.today;
          return (
            <span key={i} className={`cal-day cal-${status}` + (today ? " cal-today" : "")}
                  title={status === "none" ? undefined : t(("calendar_" + status) as TextKey)}>
              {i + 1}
            </span>
          );
        })}
      </div>
      {failed && <p className="muted small center-text" role="alert">{t("error_generic")}</p>}
      <div className="cal-legend">
        {LEGEND.map((s) => (
          <span key={s} className={"cal-legend-item cal-" + s}><i aria-hidden />{t(("calendar_" + s) as TextKey)}</span>
        ))}
      </div>
    </section>
  );
}
