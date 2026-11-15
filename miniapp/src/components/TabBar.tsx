/* Bottom tab bar. Only built tabs are listed (Stats comes in Stage 8). */
import type { ReactNode } from "react";
import { navigate, type Route } from "../lib/router";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Dumbbell, Home } from "./Icons";
import { Calendar } from "./PlanIcons";
import { Person } from "./ProfileIcons";

const TABS: { route: Route; key: TextKey; icon: ReactNode; match: Route["name"][] }[] = [
  { route: { name: "home" }, key: "tab_home", icon: <Home />, match: ["home"] },
  { route: { name: "plan" }, key: "tab_plan", icon: <Calendar />, match: ["plan", "planEdit", "programs", "programNew"] },
  { route: { name: "workout" }, key: "tab_train", icon: <Dumbbell />, match: ["workout", "workoutLive", "library", "exercise"] },
  { route: { name: "profile" }, key: "tab_profile", icon: <Person />, match: ["profile", "profileEdit"] },
];

export function TabBar({ current, t }: { current: Route; t: (key: TextKey) => string }) {
  return (
    <nav className="tabbar" aria-label={t("tabs")}>
      {TABS.map((tab) => {
        const on = tab.match.includes(current.name);
        return (
          <button key={tab.key} type="button" className={"tab" + (on ? " tab-on" : "")}
                  aria-current={on ? "page" : undefined}
                  onClick={() => { if (!on || current.name !== tab.route.name) { haptic.select(); navigate(tab.route); } }}>
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{t(tab.key)}</span>
          </button>
        );
      })}
    </nav>
  );
}
