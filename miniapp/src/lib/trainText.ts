/* Text helpers for the Train screens: weights, sets, targets, suggestions, timers. */
import type { TextKey } from "../i18n";
import type { Hint, PastSet } from "./trainApi";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

/** "62.5 kg", "BW" or "BW+10 kg". */
export function fmtWeight(weight: number, equipment: string, t: T): string {
  if (equipment === "bodyweight") return weight === 0 ? t("logger_bw") : `${t("logger_bw")}+${weight} ${t("logger_kg")}`;
  return `${weight} ${t("logger_kg")}`;
}

/** One set: "60 kg × 8", "BW × 12" or "45 s" for holds. */
export function fmtSet(set: PastSet, equipment: string, timed: boolean, t: T): string {
  if (timed) return `${set.reps} ${t("logger_seconds")}`;
  return `${fmtWeight(set.weight_kg, equipment, t)} × ${set.reps}`;
}

export function fmtSets(sets: PastSet[], equipment: string, timed: boolean, t: T): string {
  return sets.map((s) => fmtSet(s, equipment, timed, t)).join(" · ");
}

export function repRange(item: { rep_min: number; rep_max: number; timed: boolean }, t: T): string {
  const range = `${item.rep_min}–${item.rep_max}`;
  return item.timed ? `${range} ${t("logger_seconds")}` : range;
}

/** The overload suggestion as a sentence (sugg_<kind>), or null if unknown. */
export function hintText(hint: Hint | null, t: T): string | null {
  if (!hint) return null;
  const text = t(("sugg_" + hint.kind) as TextKey, hint.params);
  return text.startsWith("sugg_") ? null : text;
}

/** 75 -> "1:15", 3725 -> "1:02:05". */
export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
