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
