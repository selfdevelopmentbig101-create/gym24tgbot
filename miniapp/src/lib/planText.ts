/* Small text helpers for the Plan screens (names, "in 2 days", error messages). */
import { ApiError } from "./api";
import type { TextKey } from "../i18n";
import type { DayHead } from "./planApi";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

// Error codes from services/programs.py that have their own message (plan_err_<code>).
const KNOWN_ERRORS = new Set([
  "profile_required", "no_exercises", "already_in_day", "too_many_exercises", "too_many_days",
  "last_day", "last_exercise", "no_substitute", "program_is_current", "too_many_programs",
  "bad_sets", "bad_reps", "bad_rest", "no_program", "no_day", "no_plan_exercise",
]);

export function planErrorKey(error: unknown): TextKey {
  if (error instanceof ApiError) {
    if (KNOWN_ERRORS.has(error.code)) return ("plan_err_" + error.code) as TextKey;
    if (error.status === 0) return "error_network";
    if (error.status === 401) return "error_auth";
    if (error.status === 429) return "error_rate";
  }
  return "error_generic";
}

/** The name the user gave a day, or its default name ("Upper A"). */
export function dayName(day: DayHead, t: T): string {
  if (day.title) return day.title;
  return t(("plan_day_" + day.name_key) as TextKey) + (day.suffix ? " " + day.suffix : "");
}

/** A program's own name, or its default name (from the split or the built-in program). */
export function programName(program: { name: string | null; name_key: string | null }, t: T): string {
  return program.name ?? t((program.name_key ?? "program_default") as TextKey);
}

export function whenText(inDays: number, t: T): string {
  if (inDays <= 0) return t("plan_today");
  if (inDays === 1) return t("plan_tomorrow");
  return t("plan_in_days", { n: inDays });
}

export function repsText(entry: { rep_min: number; rep_max: number; timed: boolean }, t: T): string {
  const vars = { min: entry.rep_min, max: entry.rep_max };
  return entry.timed ? t("editor_hold_value", vars) : t("editor_reps_value", vars);
}
