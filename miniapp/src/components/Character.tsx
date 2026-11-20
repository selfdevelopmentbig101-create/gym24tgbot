/*
 * Level artwork: the supplied illustrations with the background removed.
 * The figure, aura, lightning and particles are one bitmap, so every effect
 * stays exactly as drawn; only the surroundings were cleared.
 */
import type { CSSProperties } from "react";
import "./Character.css";

export type Mood = "rested" | "tired" | "celebrating";

const LEVEL_IMAGES = [
  "/static/levels/male_1_rookie.png",
  "/static/levels/male_2_beginner.png",
  "/static/levels/male_3_regular.png",
  "/static/levels/male_4_advanced.png",
  "/static/levels/male_5_pro.png",
] as const;

// Every file keeps the source canvas (652x1073), so one shared window crops all
// five the same way: the ranks stay aligned and at the same scale.
const CANVAS_WIDTH = 652;
const CANVAS_HEIGHT = 1073;
const WINDOW = { x: 22, y: 36, width: 508, height: 991 } as const;

export function Character({ level, mood, size = 140, label }: {
  level: number; mood: Mood; size?: number; label?: string;
}) {
  const lv = Math.max(0, Math.min(LEVEL_IMAGES.length - 1, Math.round(level)));
  return (
    <svg className={`character character-${mood}`}
         style={{ "--character-size": `${size}px` } as CSSProperties}
         width={size} height={size * WINDOW.height / WINDOW.width}
         viewBox={`${WINDOW.x} ${WINDOW.y} ${WINDOW.width} ${WINDOW.height}`}
         role={label ? "img" : undefined} aria-label={label}
         aria-hidden={label ? undefined : true}>
      <image className="character-art" href={LEVEL_IMAGES[lv]}
             x="0" y="0" width={CANVAS_WIDTH} height={CANVAS_HEIGHT} />
    </svg>
  );
}