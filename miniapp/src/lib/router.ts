/*
 * Tiny path router (no dependency). Paths match the bot's links, e.g. MINIAPP_URL/train.
 * The API serves index.html for any path, so reloads and deep links work.
 *
 *   /                      home
 *   /plan                  Plan tab (calendar, current program, details)
 *   /plan/edit[/{dayId}]   split editor (optionally opened on one day)
 *   /plan/programs         all programs (Current / Available / Created)
 *   /plan/programs/new     create a program
 *   /workout               Train tab home: two cards, Splits and All exercises
 *   /workout/session       session view of the active split (load, exercises, Start)
 *   /workout/splits        all splits, the active one on top
 *   /workout/splits/{id}   split detail with "Choose this split"
 *   /workout/exercises     All exercises: by muscle (2-column grid) or the whole list
 *   /workout/exercises/muscle/{key}   exercises of one muscle
 *   /workout/live          live logger for the workout in progress
 *   /workout/go            guided workout: countdown, exercise screen, rest, summary
 *   /targets               daily targets (calories, macros, goal date)
 *   /profile               Profile tab: character, level, achievements, settings (Stage 6)
 *   /profile/edit          edit profile
 *   /train                 All exercises (the bot's 📚 Exercises button links here)
 *   /exercise/{id}         exercise detail
 */
import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "plan" }
  | { name: "planEdit"; day?: number }
  | { name: "programs" }
  | { name: "programNew" }
  | { name: "workout" }
  | { name: "workoutSession" }
  | { name: "splits" }
  | { name: "split"; id: number }
  | { name: "exercises" }
  | { name: "muscle"; key: string }
  | { name: "profile" }
  | { name: "targets" }
  | { name: "profileEdit" }
  | { name: "workoutLive" }
  | { name: "workoutGuided" }
  | { name: "exercise"; id: string };

export function parse(path: string): Route {
  const parts = path.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts[0] === "train" && parts.length === 1) return { name: "exercises" };
  if (parts[0] === "targets") return { name: "targets" };
  if (parts[0] === "profile") return parts[1] === "edit" ? { name: "profileEdit" } : { name: "profile" };
  if (parts[0] === "workout") {
    if (parts[1] === "live") return { name: "workoutLive" };
    if (parts[1] === "go") return { name: "workoutGuided" };
    if (parts[1] === "session") return { name: "workoutSession" };
    if (parts[1] === "splits") {
      const id = Number(parts[2]);
      return Number.isInteger(id) && id > 0 ? { name: "split", id } : { name: "splits" };
    }
    if (parts[1] === "exercises") {
      if (parts[2] === "muscle" && parts[3]) return { name: "muscle", key: decodeURIComponent(parts[3]) };
      return { name: "exercises" };
    }
    return { name: "workout" };
  }
  if (parts[0] === "exercise" && parts[1]) return { name: "exercise", id: decodeURIComponent(parts[1]) };
  if (parts[0] === "plan") {
    if (parts[1] === "edit") {
      const day = Number(parts[2]);
      return Number.isInteger(day) && day > 0 ? { name: "planEdit", day } : { name: "planEdit" };
    }
    if (parts[1] === "programs") return parts[2] === "new" ? { name: "programNew" } : { name: "programs" };
    return { name: "plan" };
  }
  return { name: "home" };
}

export function pathOf(route: Route): string {
  switch (route.name) {
    case "home": return "/";
    case "plan": return "/plan";
    case "planEdit": return "/plan/edit" + (route.day ? "/" + route.day : "");
    case "programs": return "/plan/programs";
    case "programNew": return "/plan/programs/new";
    case "workout": return "/workout";
    case "profile": return "/profile";
    case "targets": return "/targets";
    case "profileEdit": return "/profile/edit";
    case "workoutLive": return "/workout/live";
    case "workoutGuided": return "/workout/go";
    case "workoutSession": return "/workout/session";
    case "splits": return "/workout/splits";
    case "split": return "/workout/splits/" + route.id;
    case "exercises": return "/workout/exercises";
    case "muscle": return "/workout/exercises/muscle/" + encodeURIComponent(route.key);
    case "exercise": return "/exercise/" + encodeURIComponent(route.id);
  }
}

const listeners = new Set<() => void>();
let depth = 0; // in-app navigations, so Back knows whether history.back() stays inside the app

export function navigate(route: Route, options: { replace?: boolean } = {}): void {
  const path = pathOf(route);
  if (path === location.pathname) return;
  // Keep Telegram's launch data in the hash: the SDK reads it from there on reload.
  if (options.replace) history.replaceState({ depth }, "", path + location.hash);
  else history.pushState({ depth: ++depth }, "", path + location.hash);
  listeners.forEach((fn) => fn());
  window.scrollTo(0, 0);
}

/** Back inside the app, or to `fallback` when this screen was opened directly (deep link). */
export function goBack(fallback: Route): void {
  if (depth > 0) history.back();
  else navigate(fallback, { replace: true });
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(location.pathname));
  useEffect(() => {
    const update = () => setRoute(parse(location.pathname));
    const onPop = (event: PopStateEvent) => {
      depth = (event.state as { depth?: number } | null)?.depth ?? 0;
      update();
    };
    listeners.add(update);
    window.addEventListener("popstate", onPop);
    return () => {
      listeners.delete(update);
      window.removeEventListener("popstate", onPop);
    };
  }, []);
  return route;
}
