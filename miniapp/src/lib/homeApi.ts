/* Stage 7 API client: the Home tab (GET /api/home, see services/home.py). */
import { api } from "./api";
import type { DayHead } from "./planApi";

export interface HomeNext extends DayHead {
  index: number;
  exercises: number;
  minutes: number;
  muscles: string[];
  names: string[];
}

export interface HomeView {
  part_of_day: "morning" | "afternoon" | "evening" | "night";
  today: string;
  week: {
    start: string;
    days: { date: string; trained: boolean; today: boolean }[];
    done: number;
    goal: number;
    streak_weeks: number;
    sets: number;
    volume_kg: number;
    prs: number;
    minutes: number;
  };
  next_workout: HomeNext | null;
  active: { id: number; done_sets: number; planned_sets: number; name_key: string; suffix: string } | null;
  nutrition: { calories: number; calories_target: number; protein_g: number; protein_target: number };
  weight: { kg: number; logged_at: string | null };
}

export const getHome = () => api<HomeView>("/api/home");
