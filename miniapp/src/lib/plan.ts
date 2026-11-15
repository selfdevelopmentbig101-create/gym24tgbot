/* Names and numbers shared by the Plan screens. */
import { errorCode, type PlanDay, type PlanItem, type ProgramSummary } from "./api";
import { hasText, type TextKey } from "../i18n";

export type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function programName(p: Pick<ProgramSummary, "name" | "split">, t: T): string {
  return p.name || t(("split_" + p.split) as TextKey);
}

export function dayName(d: Pick<PlanDay, "name" | "name_key" | "suffix">, t: T): string {
  return d.name || (t(("day_" + d.name_key) as TextKey) + " " + d.suffix).trim();
}

export function repsText(item: Pick<PlanItem, "rep_min" | "rep_max" | "timed">, t: T): string {
  const range = item.rep_min === item.rep_max ? String(item.rep_min) : item.rep_min + "–" + item.rep_max;
  return item.timed ? t("seconds_short", { n: range }) : range;
}

export function percent(done: number, total: number): number {
  return total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
}

export function formatDate(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(new Date(iso + "T12:00:00"));
}

/** A failed request as a translated sentence ("perr_<code>", else a generic message). */
export function errorMessage(error: unknown, t: T): string {
  const key = "perr_" + errorCode(error);
  return hasText(key) ? t(key as TextKey) : t("error_generic");
}
