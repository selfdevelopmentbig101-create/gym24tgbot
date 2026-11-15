/*
 * Home: the character (medium) with level, XP bar, weekly streak and energy.
 * Tap opens the Profile tab. Shows the celebration when a new level was reached.
 */
import { useEffect, useState } from "react";
import { getLevel, type LevelView } from "../lib/profileApi";
import { navigate } from "../lib/router";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Character } from "./Character";
import { useCelebration } from "./Celebration";
import "./Character.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function xpLine(view: LevelView, t: T): string {
  const { level } = view;
  if (level.next_key === null) return t("char_max");
  return t("char_to_next", { n: level.to_next, rank: t(("rank_" + level.next_key) as TextKey) });
}

export function CharacterCard({ t }: { t: T }) {
  const [view, setView] = useState<LevelView | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    getLevel().then(setView).catch(() => setFailed(true));
  }, []);
  const celebration = useCelebration(view ? view.level : null, null, t);

  if (failed) return null;  // Home still works without the card
  if (!view) return <section className="card char-card char-card-loading" aria-busy="true" />;
  const rank = t(("rank_" + view.level.key) as TextKey);
  return (
    <>
      <button type="button" className="card char-card" aria-label={t("char_open_profile")}
              onClick={() => { haptic.tap(); navigate({ name: "profile" }); }}>
        <Character level={view.level.index} mood={view.mood} size={96} label={rank} />
        <span className="char-info">
          <span className="char-rank">{t("char_level", { n: view.level.index + 1, rank })}</span>
          <span className="xp-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={view.level.progress}
                aria-label={xpLine(view, t)}>
            <span style={{ width: `${view.level.progress}%` }} />
          </span>
          <span className="muted small">{xpLine(view, t)}</span>
          <span className="char-chips">
            <span>{t("char_streak", { n: view.streak_weeks })}</span>
            <span>{t("char_energy", { n: view.energy })}</span>
          </span>
          <span className="small char-mood">{t(("mood_" + view.mood) as TextKey)}</span>
        </span>
      </button>
      {celebration}
    </>
  );
}
