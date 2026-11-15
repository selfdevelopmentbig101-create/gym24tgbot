/* Stage 6 API client: level, XP, character, achievements, profile edits, deleting data. */
import { api, type Profile, type ProfileSaved } from "./api";
import type { Mood } from "../components/Character";

export interface LevelInfo {
  index: number;
  key: string;            // rank_<key>
  xp: number;
  level_xp: number;
  next_key: string | null;
  next_xp: number | null;
  to_next: number;
  progress: number;       // 0-100 within the level
  max_index: number;
}

export interface LevelView {
  level: LevelInfo;
  levels: { key: string; xp: number }[];
  streak_weeks: number;
  week_done: number;
  week_goal: number;
  energy: number;
  mood: Mood;
  in_workout: boolean;
  stats: { workouts: number; prs: number; goal_weeks: number; volume_t: number; protein_streak: number };
  xp_rules: { workout: number; pr: number; goal_week: number };
}

export interface AchievementItem {
  code: string;           // ach_name_<code>
  emoji: string;
  unlocked: boolean;
  unlocked_at: string | null;
  progress: number;
  threshold: number;
}

export interface AchievementList { items: AchievementItem[]; unlocked: number; total: number; new: string[] }

export const getLevel = () => api<LevelView>("/api/me/level");
export const getAchievements = () => api<AchievementList>("/api/achievements");
export const getProfile = () => api<Profile>("/api/profile");
export const patchProfile = (changes: Partial<Profile>) =>
  api<ProfileSaved>("/api/profile", { method: "PATCH", body: changes });
export const deleteMyData = () => api<null>("/api/me", { method: "DELETE", body: { confirm: "DELETE" } });
