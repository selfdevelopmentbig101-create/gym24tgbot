/*
 * Stage 5 API client: workout-day screen and live logger.
 * Shapes match api/routes/train.py and services/train.py.
 */
import { api, ApiError } from "./api";
import type { TextKey } from "../i18n";
import type { DayHead, EnergyLoad } from "./planApi";

export interface LoggedSet {
  id: number;
  set_number: number;
  weight_kg: number;
  reps: number;            // seconds for holds
  rpe: number | null;
  warmup: boolean;
  pr: boolean;
}

/** Progressive-overload suggestion (services/progression.py); the app shows sugg_<kind>. */
export interface Hint {
  kind: string;
  weight_kg: number;
  reps: number;
  params: Record<string, number | string>;
}

export interface PastSet { weight_kg: number; reps: number }

/** Exercise pictures for the guided screen (start + peak frames loop; kind is null without images). */
export interface ItemMedia {
  kind: "animation" | "photo" | null;
  start: string | null;
  peak: string | null;
  still: string | null;
}

export interface WorkoutItem {
  index: number;
  exercise_id: string;
  name: string;
  muscle_group: string;
  equipment: string;
  image: string | null;
  sets: number;
  rep_min: number;
  rep_max: number;
  timed: boolean;
  rest_seconds: number;
  media?: ItemMedia | null;
  note: string | null;
  group: string | null;     // superset group A-D
  label: string | null;     // A1, A2, B1...
  status: "completed" | "current" | "upcoming";
  logged: LoggedSet[];      // warm-ups first, then working sets
  previous: PastSet[];      // last workout's working sets
  suggestion: Hint | null;
}

export interface WorkoutView {
  id: number;
  started_at: string;
  finished: boolean;
  day_index: number | null;
  name_key: string;
  suffix: string;
  title: string | null;
  current_index: number;
  items: WorkoutItem[];
  done_sets: number;
  planned_sets: number;
  energy: { left: number; planned_left: number; warnings: string[] };
}

export interface TrainDayExercise {
  exercise_id: string;
  name: string;
  muscle_group: string;
  equipment: string;
  image: string | null;
  sets: number;
  rep_min: number;
  rep_max: number;
  timed: boolean;
  rest_seconds: number;
  last: PastSet[];
}

export interface TrainDay extends DayHead {
  id: number;
  index: number;
  minutes: number;
  energy: EnergyLoad;
  exercises: TrainDayExercise[];
}

export interface TrainOverview { active: WorkoutView | null; next_index: number; days: TrainDay[] }

export interface LogResult {
  set: LoggedSet & { estimate: number | null; previous_best: number | null };
  workout: WorkoutView;
}

export interface Summary {
  discarded: boolean;
  xp_gained?: number;
  level?: { index: number; key: string };
  level_up?: boolean;
  minutes?: number;
  total_sets?: number;
  volume_kg?: number;
  prs?: string[];
  achievements?: string[];
  exercises?: { exercise_id: string; name: string; timed: boolean; equipment: string;
                sets: { weight_kg: number; reps: number; pr: boolean }[]; next_time: Hint | null }[];
}

export interface NewSet { index: number; weight_kg: number; reps: number; rpe: number | null; warmup: boolean }

export const getTrain = () => api<TrainOverview>("/api/train");
export const startWorkout = (dayIndex: number, force = false) =>
  api<WorkoutView>("/api/workouts", { method: "POST", body: { day_index: dayIndex, force } });
export const logSet = (id: number, body: NewSet) =>
  api<LogResult>(`/api/workouts/${id}/sets`, { method: "POST", body });
export const editSet = (id: number, setId: number, changes: { weight_kg?: number; reps?: number; rpe?: number | null }) =>
  api<WorkoutView>(`/api/workouts/${id}/sets/${setId}`, { method: "PATCH", body: changes });
export const deleteSet = (id: number, setId: number) =>
  api<WorkoutView>(`/api/workouts/${id}/sets/${setId}`, { method: "DELETE" });
export const updateItem = (id: number, index: number, changes: { note?: string | null; group?: string | null }) =>
  api<WorkoutView>(`/api/workouts/${id}/items/${index}`, { method: "PATCH", body: changes });
export const substituteItem = (id: number, index: number) =>
  api<WorkoutView>(`/api/workouts/${id}/items/${index}/substitute`, { method: "POST" });
export const finishWorkout = (id: number) => api<Summary>(`/api/workouts/${id}/finish`, { method: "POST" });

// Error codes from the server that have their own message (train_err_<code>).
const KNOWN = new Set([
  "workout_active", "workout_finished", "no_workout", "bad_day", "no_substitute", "swap_after_sets",
  "err_set_weight", "err_set_reps", "err_set_rpe", "err_bad_exercise", "err_no_set", "err_bad_group",
  "profile_required",
]);

export function trainErrorKey(error: unknown): TextKey {
  if (error instanceof ApiError) {
    if (KNOWN.has(error.code)) return ("train_err_" + error.code) as TextKey;
    if (error.status === 0) return "error_network";
    if (error.status === 401) return "error_auth";
    if (error.status === 429) return "error_rate";
  }
  return "error_generic";
}
