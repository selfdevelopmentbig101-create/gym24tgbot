/*
 * API client. Every request carries Telegram's signed initData:
 *     Authorization: tma <initData>
 * The server checks the signature on every call; we never send a user ID ourselves.
 */
import { getInitData } from "./telegram";

const TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  /** 0 = network/timeout, 401 = login invalid or expired, 429 = too many requests */
  constructor(public status: number, public code: string, public detail?: unknown) {
    super(code);
  }
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const initData = getInitData();
  if (!initData) throw new ApiError(401, "not_in_telegram");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers: {
        Authorization: `tma ${initData}`,
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(0, "network");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof data.detail === "string" ? data.detail : "error", data.detail);
  }
  if (response.status === 204) return null as T;
  return (await response.json()) as T;
}

// ---------- Typed endpoints (match api/schemas.py) ----------

export type LanguageCode = "en" | "ru" | "uz";

export interface Me {
  first_name: string;
  language: LanguageCode | null;
  language_effective: LanguageCode;
  disclaimer_accepted: boolean;
  profile_complete: boolean;
}

export const getMe = () => api<Me>("/api/me");
export const setLanguage = (language: LanguageCode) =>
  api<Me>("/api/me/language", { method: "PATCH", body: { language } });

// ---------- Stage 2: onboarding and targets ----------

export type Goal = "bulk" | "lean_bulk" | "recomp";
export type Sex = "male" | "female" | "unspecified";
export type Experience = "beginner" | "intermediate" | "advanced";
export type Equipment = "full_gym" | "home_dumbbells" | "bodyweight";
export type Injury = "shoulder" | "elbow_wrist" | "lower_back" | "knee" | "hip";
export type Diet = "none" | "vegetarian" | "vegan" | "pescatarian";

export interface ProfileRules {
  age: [number, number];
  height_cm: [number, number];
  weight_kg: [number, number];
  training_days: [number, number];
  goals: Goal[];
  sexes: Sex[];
  experience: Experience[];
  equipment: Equipment[];
  injuries: Injury[];
  diets: Diet[];
}

export interface AppConfig {
  app_name: string;
  attribution: string;
  languages: { code: LanguageCode; name: string }[];
  profile_rules: ProfileRules;
}

export interface Profile {
  goal: Goal;
  age: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  experience: Experience;
  training_days: number;
  equipment: Equipment;
  injuries: Injury[];
  diet: Diet;
  target_weight_kg: number | null;
}

export interface Targets {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  bmr: number;
  tdee: number;
  surplus: number;
  protein_g_per_kg: number;
  weekly_gain_kg: [number, number];
  goal: {
    target_weight_kg: number;
    to_gain_kg: number;
    estimated_date: string;
    earliest_date: string;
    latest_date: string;
  } | null;
  notes: string[];
}

export interface ProfileSaved {
  profile: Profile;
  targets: Targets;
  plan_ready: boolean;
  plan_rebuilt: boolean;
}

/** 422 from /api/profile: which answer was rejected and why (an i18n key). */
export function fieldError(error: unknown): { field: string; error: string } | null {
  if (error instanceof ApiError && error.status === 422 && error.detail && typeof error.detail === "object") {
    const d = error.detail as { field?: unknown; error?: unknown };
    if (typeof d.field === "string" && typeof d.error === "string") return { field: d.field, error: d.error };
  }
  return null;
}

export const getConfig = () => api<AppConfig>("/api/config");
export const acceptDisclaimer = () => api<null>("/api/me/disclaimer", { method: "POST" });
export const saveProfile = (profile: Profile) =>
  api<ProfileSaved>("/api/profile", { method: "PUT", body: profile });
export const getTargets = () => api<Targets>("/api/targets");

// ---------- Stage 3: exercise library ----------

export interface ExerciseItem {
  id: string;
  name: string;
  muscle_group: string;
  secondary_muscles: string[];
  equipment: string;
  difficulty: string;
  movement_type: string;
  home_friendly: boolean;
  image: string | null;
  fits: boolean | null;
}

export interface ExerciseList {
  items: ExerciseItem[];
  total: number;
  muscles: string[];
  equipment: string[];
  difficulties: string[];
}

export interface ExerciseDetail extends ExerciseItem {
  media: { kind: "animation" | "photo" | null; start: string | null; peak: string | null; still: string | null };
  form_tips: string | null;
  reasons: ("equipment" | "level" | "injury")[];
  substitutes: ExerciseItem[];
}

export interface LibraryQuery {
  q: string;
  muscle: string | null;
  equipment: string | null;
  difficulty: string | null;
  home: boolean;
  fits: boolean;
}

export function getExercises(query: LibraryQuery): Promise<ExerciseList> {
  const params = new URLSearchParams();
  if (query.q.trim()) params.set("q", query.q.trim().slice(0, 60));
  if (query.muscle) params.set("muscle", query.muscle);
  if (query.equipment) params.set("equipment", query.equipment);
  if (query.difficulty) params.set("difficulty", query.difficulty);
  if (query.home) params.set("home", "true");
  if (query.fits) params.set("fits", "true");
  const qs = params.toString();
  return api<ExerciseList>("/api/exercises" + (qs ? "?" + qs : ""));
}

export const getExercise = (id: string) => api<ExerciseDetail>("/api/exercises/" + encodeURIComponent(id));

// ---------- Stage 4: programs ----------

export type TrainingGoal = "strength" | "hypertrophy" | "endurance";

export interface PlanItem {
  id: number;
  exercise: ExerciseItem;
  sets: number;
  rep_min: number;
  rep_max: number;
  timed: boolean;
  rest_seconds: number;
}

export interface PlanDay {
  id: number;
  index: number;
  name_key: string;
  suffix: string;
  name: string | null;
  exercises: PlanItem[];
  sets: number;
  minutes: number;
}

export interface ProgramSummary {
  id: number;
  name: string | null;
  split: string;
  kind: "template" | "custom";
  template_days: number | null;
  goal: TrainingGoal;
  weeks: number;
  workouts_per_week: number;
  is_current: boolean;
  edited: boolean;
  started_on: string | null;
  ends_on: string | null;
  week: number | null;
  completed: number;
  total: number;
  next_day_index: number | null;
  day_names: PlanDay[];
}

export interface ProgramDetail extends ProgramSummary {
  days: PlanDay[];
}

export interface TemplateInfo {
  days: number;
  split: string;
  recommended: boolean;
  day_keys: string[];
}

export interface Programs {
  current: ProgramSummary | null;
  created: ProgramSummary[];
  available: TemplateInfo[];
}

export interface CalendarMonth {
  month: string;
  days: { date: string; status: "done" | "missed" | "planned" | "rest" }[];
  schedule: number[];
  done: number;
  planned: number;
}

export interface Energy {
  day: { sets: number; minutes: number; muscles: { muscle: string; sets: number }[] };
  week: { muscle: string; sets: number; level: "low" | "ok" | "high" }[];
  warnings: { key: string; muscle?: string | null; value: number }[];
}

export interface ProgramCreate {
  name?: string | null;
  weeks: number;
  workouts_per_week?: number;
  goal: TrainingGoal;
  template_days?: number | null;
  activate?: boolean;
}

export const getPrograms = () => api<Programs>("/api/programs");
export const getProgram = (id: number) => api<ProgramDetail>("/api/programs/" + id);
export const createProgram = (body: ProgramCreate) =>
  api<ProgramDetail>("/api/programs", { method: "POST", body });
export const patchProgram = (id: number, body: { name?: string | null; weeks?: number; goal?: TrainingGoal }) =>
  api<ProgramDetail>("/api/programs/" + id, { method: "PATCH", body });
export const deleteProgram = (id: number) => api<null>("/api/programs/" + id, { method: "DELETE" });
export const activateProgram = (id: number) =>
  api<ProgramDetail>("/api/programs/" + id + "/activate", { method: "POST" });
export const resetProgram = (id: number) =>
  api<ProgramDetail>("/api/programs/" + id + "/reset", { method: "POST" });
export const addDay = (programId: number, name?: string) =>
  api<ProgramDetail>("/api/programs/" + programId + "/days", { method: "POST", body: { name: name || null } });
export const patchDay = (programId: number, dayId: number, body: { name?: string; position?: number }) =>
  api<ProgramDetail>("/api/programs/" + programId + "/days/" + dayId, { method: "PATCH", body });
export const deleteDay = (programId: number, dayId: number) =>
  api<ProgramDetail>("/api/programs/" + programId + "/days/" + dayId, { method: "DELETE" });
export const getDay = (dayId: number) => api<PlanDay>("/api/days/" + dayId);
export const addDayExercise = (dayId: number, exerciseId: string) =>
  api<PlanDay>("/api/days/" + dayId + "/exercises", { method: "POST", body: { exercise_id: exerciseId } });
export const patchDayExercise = (dayId: number, itemId: number,
  body: { sets?: number; rep_min?: number; rep_max?: number; rest_seconds?: number; position?: number }) =>
  api<PlanDay>("/api/days/" + dayId + "/exercises/" + itemId, { method: "PATCH", body });
export const deleteDayExercise = (dayId: number, itemId: number) =>
  api<PlanDay>("/api/days/" + dayId + "/exercises/" + itemId, { method: "DELETE" });
export const substituteDayExercise = (dayId: number, itemId: number, exerciseId?: string) =>
  api<PlanDay>("/api/days/" + dayId + "/exercises/" + itemId + "/substitute",
    { method: "POST", body: { exercise_id: exerciseId ?? null } });
export const getCalendar = (month: string) => api<CalendarMonth>("/api/calendar?month=" + month);
export const getEnergy = (dayId: number) => api<Energy>("/api/energy?day=" + dayId);

/** The error code from a failed request (e.g. "program_empty"), for translated messages. */
export function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : "error";
}
