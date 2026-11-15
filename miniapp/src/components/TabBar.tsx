/* Bottom tab bar. Only built tabs are listed (Stats and Profile come in later stages). */
import type { ReactNode } from "react";
import { navigate, tabOf, type Route } from "../lib/router";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Calendar, Dumbbell, Home } from "./Icons";

const TABS: { id: ReturnType<typeof tabOf>; route: Route; key: TextKey; icon: ReactNode }[] = [
  { id: "home", route: { name: "home" }, key: "tab_home", icon: <Home /> },
  { id: "plan", route: { name: "plan" }, key: "tab_plan", icon: <Calendar /> },
  { id: "train", route: { name: "library" }, key: "tab_train", icon: <Dumbbell /> },
];

export function TabBar({ current, t }: { current: Route; t: (key: TextKey) => string }) {
  const active = tabOf(current);
  return (
    <nav className="tabbar" aria-label={t("tabs")}>
      {TABS.map((tab) => {
        const on = tab.id === active;
        return (
          <button key={tab.id} type="button" className={"tab" + (on ? " tab-on" : "")}
                  aria-current={on ? "page" : undefined}
                  onClick={() => { if (current.name !== tab.route.name) { haptic.select(); navigate(tab.route); } }}>
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{t(tab.key)}</span>
          </button>
        );
      })}
    </nav>
  );
}
