/*
 * Tiny path router (no dependency). Paths match the bot's links, e.g. MINIAPP_URL/train.
 * The API serves index.html for any path, so reloads and deep links work.
 */
import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "library" }
  | { name: "exercise"; id: string };

export function parse(path: string): Route {
  const parts = path.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts[0] === "train" && parts.length === 1) return { name: "library" };
  if (parts[0] === "exercise" && parts[1]) return { name: "exercise", id: decodeURIComponent(parts[1]) };
  return { name: "home" };
}

export function pathOf(route: Route): string {
  switch (route.name) {
    case "home": return "/";
    case "library": return "/train";
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
