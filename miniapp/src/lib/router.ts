/*
 * Tiny path router (no dependency). Paths match the bot's links, e.g. MINIAPP_URL/train.
 * The API serves index.html for any path, so reloads and deep links work.
 */
import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "library" }
  | { name: "exercise"; id: string }
  | { name: "plan" }
  | { name: "programs" }
  | { name: "program"; id: number }
  | { name: "programEdit"; id: number }
  | { name: "programNew" }
  | { name: "template"; days: number }
  | { name: "day"; id: number }
  | { name: "dayAdd"; id: number };

const num = (value: string | undefined) => (value && /^\d+$/.test(value) ? Number(value) : null);

export function parse(path: string): Route {
  const p = path.replace(/\/+$/, "").split("/").filter(Boolean);
  if (p[0] === "train" && p.length === 1) return { name: "library" };
  if (p[0] === "exercise" && p[1]) return { name: "exercise", id: decodeURIComponent(p[1]) };
  if (p[0] === "plan") {
    if (p.length === 1) return { name: "plan" };
    if (p[1] === "programs") return { name: "programs" };
    if (p[1] === "new") return { name: "programNew" };
    const id = num(p[2]);
    if (p[1] === "program" && id !== null) return p[3] === "edit" ? { name: "programEdit", id } : { name: "program", id };
    if (p[1] === "template" && id !== null) return { name: "template", days: id };
    if (p[1] === "day" && id !== null) return p[3] === "add" ? { name: "dayAdd", id } : { name: "day", id };
    return { name: "plan" };
  }
  return { name: "home" };
}

export function pathOf(route: Route): string {
  switch (route.name) {
    case "home": return "/";
    case "library": return "/train";
    case "exercise": return "/exercise/" + encodeURIComponent(route.id);
    case "plan": return "/plan";
    case "programs": return "/plan/programs";
    case "program": return "/plan/program/" + route.id;
    case "programEdit": return "/plan/program/" + route.id + "/edit";
    case "programNew": return "/plan/new";
    case "template": return "/plan/template/" + route.days;
    case "day": return "/plan/day/" + route.id;
    case "dayAdd": return "/plan/day/" + route.id + "/add";
  }
}

/** Which bottom tab a screen belongs to. */
export function tabOf(route: Route): "home" | "plan" | "train" {
  if (route.name === "home") return "home";
  if (route.name === "library" || route.name === "exercise") return "train";
  return "plan";
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
