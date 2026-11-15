/* Weekly hard sets per muscle, with the low/high lines from services/energy_config.py. */
import type { TextKey } from "../i18n";
import type { Limits, MuscleVolume } from "../lib/planApi";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function VolumeList({ volume, limits, t }: { volume: MuscleVolume[]; limits: Limits; t: T }) {
  if (volume.length === 0) return null;
  const scale = Math.max(limits.weekly_sets_high * 1.25, ...volume.map((v) => v.sets));
  const at = (sets: number) => `${Math.min(100, (sets / scale) * 100)}%`;
  return (
    <section className="card volume">
      <h2 className="card-title">{t("volume_title")}</h2>
      <ul className="volume-list">
        {volume.map((v) => (
          <li key={v.muscle} className={"volume-row volume-" + v.status}>
            <span className="volume-muscle">{t(("muscle_" + v.muscle) as TextKey)}</span>
            <span className="volume-track" aria-hidden>
              <span className="volume-fill" style={{ width: at(v.sets) }} />
              <i style={{ left: at(limits.weekly_sets_low) }} />
              <i style={{ left: at(limits.weekly_sets_high) }} />
            </span>
            <span className="volume-sets">{t("volume_sets", { n: v.sets })}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">{t("volume_hint", { low: limits.weekly_sets_low, high: limits.weekly_sets_high })}</p>
      {volume.some((v) => v.status === "high") && (
        <p className="volume-warning small">{t("volume_high_warning")} {t("not_medical_advice")}</p>
      )}
    </section>
  );
}
