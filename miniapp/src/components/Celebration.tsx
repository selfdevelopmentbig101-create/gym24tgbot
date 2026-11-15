/*
 * Celebration moment: confetti + a message when you reach a new level or unlock
 * an achievement. What you've already seen is remembered on this device, so each
 * moment is shown once.
 */
import { useEffect, useState } from "react";
import type { TextKey } from "../i18n";
import { haptic, localUserKey } from "../lib/telegram";
import { Character } from "./Character";
import "./Character.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const COLORS = ["var(--color-mint)", "var(--color-lime)", "var(--color-text)", "var(--color-pill-on)"];

export function Celebration({ message, level, t, onClose }: {
  message: string; level: number; t: T; onClose: () => void;
}) {
  return (
    <div className="celebration" role="dialog" aria-modal="true" aria-label={message} onClick={onClose}>
      <div className="confetti" aria-hidden>
        {Array.from({ length: 24 }, (_, i) => (
          <i key={i} style={{
            left: `${(i * 37) % 100}%`, background: COLORS[i % COLORS.length],
            animationDelay: `${(i % 8) * 0.25}s`, animationDuration: `${2 + (i % 5) * 0.3}s`,
          }} />
        ))}
      </div>
      <div className="celebration-card" onClick={(e) => e.stopPropagation()}>
        <Character level={level} mood="celebrating" size={120} />
        <h2>{message}</h2>
        <button type="button" className="button-primary" onClick={onClose}>{t("celebrate_close")}</button>
      </div>
    </div>
  );
}

const STORE = () => "gym24.seen." + localUserKey();

/**
 * Compares the level / number of unlocked achievements with what this device saw
 * last time, and returns the celebration overlay when something new happened.
 * The first time ever, it only remembers (no celebration for old progress).
 */
export function useCelebration(level: { index: number; key: string } | null, achievements: number | null, t: T) {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    if (level === null && achievements === null) return;
    let seen: { level?: number; ach?: number } = {};
    try {
      seen = JSON.parse(localStorage.getItem(STORE()) ?? "{}");
    } catch {
      seen = {};
    }
    let text: string | null = null;
    if (level && seen.level !== undefined && level.index > seen.level) {
      text = t("celebrate_level", { rank: t(("rank_" + level.key) as TextKey) });
    } else if (achievements !== null && seen.ach !== undefined && achievements > seen.ach) {
      text = t("celebrate_achievement");
    }
    const next = { ...seen, ...(level ? { level: level.index } : {}), ...(achievements !== null ? { ach: achievements } : {}) };
    try {
      localStorage.setItem(STORE(), JSON.stringify(next));
    } catch {
      /* private mode: no celebrations, nothing breaks */
    }
    if (text) {
      haptic.success();
      setMessage(text);
    }
  }, [level?.index, achievements]); // eslint-disable-line react-hooks/exhaustive-deps

  return message ? <Celebration message={message} level={level?.index ?? 0} t={t} onClose={() => setMessage(null)} /> : null;
}
