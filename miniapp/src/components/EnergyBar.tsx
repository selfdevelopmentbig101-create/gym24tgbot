/*
 * Session load bar for one day: how much of a session's energy the planned hard
 * sets use (compound sets cost more). Above the limits in services/energy_config.py
 * it shows a clear warning, but never blocks anything.
 */
import type { TextKey } from "../i18n";
import type { EnergyLoad } from "../lib/planApi";
import { Bolt, Warn } from "./PlanIcons";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function EnergyBar({ load, t }: { load: EnergyLoad; t: T }) {
  const used = Math.max(0, load.energy_cost);
  const shown = Math.min(100, used);
  const level = load.demanding || used > 100 ? "high" : used > 80 ? "mid" : "ok";
  return (
    <div className={"energy energy-" + level}>
      <div className="energy-head">
        <span className="energy-label"><Bolt />{t("energy_label")}</span>
        <span className="energy-value">{t("energy_used", { n: used })}</span>
      </div>
      <div className="energy-track" role="meter" aria-label={t("energy_label")}
           aria-valuemin={0} aria-valuemax={100} aria-valuenow={shown}>
        <span style={{ width: `${shown}%` }} />
      </div>
      <p className="energy-meta">{t("energy_meta", { sets: load.hard_sets, exercises: load.exercises })}</p>
      {load.demanding && (
        <div className="notice energy-warning" role="note">
          <Warn />
          <div>
            <p className="notice-title">{t("energy_warning")}</p>
            <p>{t("not_medical_advice")}</p>
          </div>
        </div>
      )}
    </div>
  );
}
