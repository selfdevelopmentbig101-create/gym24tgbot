/*
 * Stage 4 API client: programs, split editor, calendar, energy.
 * Shapes match api/routes/plan.py and services/programs.py. Every editor call
 * answers with the whole updated plan (PlanView), so screens just replace it.
 */
import { api } from "./api";

export type Goal = "strength" | "hypertrophy" | "endurance";

export interface EnergyLoad {
  exercises: number;
  hard_sets: number;
  energy_cost: number;   // % of a session's energy the planned sets use (can go above 100)
  energy_left: number;   // 0-100 after all planned sets
  demanding: boolean;
  warnings: string[];    // too_many_exercises, too_many_sets
}

export interface MuscleVolume { muscle: string; sets: number; status: "low" | "ok" | "high" }

export interface Limits {
  session_energy: number;
  session_exercises_high: number;
  session_hard_sets_high: number;
  session_hard_sets_typical: [number, number];
  weekly_sets_low: number;
  weekly_sets_high: number;
}

export interface PlanEntry {
  id: number;
  exercise_id: string;
  name: string;
  muscle_group: string | null;
  secondary_muscles: string[];
  movement_type: string | null;
  image: string | null;
  fits: boolean;
  position: number;
  sets: number;
  rep_min: number;
  rep_max: number;
  timed: boolean;        // reps are seconds (plank)
  rest_seconds: number;
}

export interface DayHead { name_key: string; suffix: string; title: string | null }

export interface PlanDay extends DayHead {
  id: number;
  index: number;
  minutes: number;
  energy: EnergyLoad;
  exercises: PlanEntry[];
}

export interface ProgramItem {
  id: number;
  name: string | null;       // null = use name_key
  name_key: string | null;
  kind: "default" | "template" | "custom";
  goal: Goal;
  weeks: number;
  workouts_per_week: number;
  status: "current" | "saved";
  split: string | null;
  started_on: string | null;
}

export interface ProgramDetails {
  focus: Goal;
  volume_trend: string;
  rpe: [number, number];
  rep_range: [number, number] | null;
  minutes: number;
}

export interface Upcoming extends DayHead {
  day_id: number;
  index: number;
  exercises: number;
  minutes: number;
  in_days: number;
  date: string;
}

export interface ProgramCard extends ProgramItem {
  week: number;
  completed: number;
  target: number;
  percent: number;
  weekdays: number[];
  upcoming: Upcoming | null;
  details: ProgramDetails;
}

export interface PlanView {
  program: ProgramCard;
  days: PlanDay[];
  weekly_volume: MuscleVolume[];
  limits: Limits;
}

export interface Template {
  key: string;
  name_key: string;
  workouts_per_week: number;
  goal: Goal;
  weeks: number;
  split: string;
}

export interface CalendarDay { date: string; status: "done" | "planned" | "missed" | "rest" | "none" }

export interface CalendarMonth {
  month: string;
  today: string;
  weekdays: number[];
  days: CalendarDay[];
  counts: Record<string, number>;
}

export interface EntryChanges { sets?: number; rep_min?: number; rep_max?: number; rest_seconds?: number; position?: number }

export interface NewProgram { name: string; weeks: number; workouts_per_week: number; goal: Goal; activate: boolean }

// ---- onboarding split preview (nothing is saved) ----
export interface PreviewExercise {
  exercise_id: string;
  name: string;
  muscle_group: string;
  sets: number;
  rep_min: number;
  rep_max: number;
  timed: boolean;
  rest_seconds: number;
}

export interface PreviewDay {
  name_key: string;
  suffix: string;
  exercises: PreviewExercise[];
}

export interface PlanPreview {
  split: string;
  weeks: number;
  weekdays: number[];
  days: PreviewDay[];
}

export const previewPlan = (body: {
  experience: string;
  equipment: string;
  injuries: string[];
  days: number;
}) => api<PlanPreview>("/api/plan/preview", { method: "POST", body });

// ---- current plan and split editor ----
export const getPlan = () => api<PlanView>("/api/plan");
export const addDay = (title?: string) =>
  api<PlanView>("/api/plan/days", { method: "POST", body: { title: title ?? null } });
export const updateDay = (id: number, changes: { title?: string | null; position?: number }) =>
  api<PlanView>(`/api/plan/days/${id}`, { method: "PATCH", body: changes });
export const deleteDay = (id: number) => api<PlanView>(`/api/plan/days/${id}`, { method: "DELETE" });
export const addExercise = (dayId: number, exerciseId: string) =>
  api<PlanView>(`/api/plan/days/${dayId}/exercises`, { method: "POST", body: { exercise_id: exerciseId } });
export const updateEntry = (id: number, changes: EntryChanges) =>
  api<PlanView>(`/api/plan/exercises/${id}`, { method: "PATCH", body: changes });
export const deleteEntry = (id: number) => api<PlanView>(`/api/plan/exercises/${id}`, { method: "DELETE" });
export const substituteEntry = (id: number) =>
  api<PlanView>(`/api/plan/exercises/${id}/substitute`, { method: "POST" });

// ---- programs ----
export const listPrograms = (tab: "current" | "created") =>
  api<{ tab: string; items: ProgramItem[] }>(`/api/programs?tab=${tab}`);
export const listTemplates = () => api<{ tab: string; items: Template[] }>("/api/programs?tab=available");
export const createProgram = (body: NewProgram) => api<ProgramItem>("/api/programs", { method: "POST", body });
export const startTemplate = (key: string) =>
  api<PlanView>(`/api/programs/templates/${encodeURIComponent(key)}/start`, { method: "POST" });
export const activateProgram = (id: number) => api<PlanView>(`/api/programs/${id}/activate`, { method: "POST" });
export const resetProgram = (id: number) => api<PlanView>(`/api/programs/${id}/reset`, { method: "POST" });
export const deleteProgram = (id: number) => api<null>(`/api/programs/${id}`, { method: "DELETE" });

// ---- calendar ----
export const getCalendar = (month: string) => api<CalendarMonth>(`/api/calendar?month=${month}`);
