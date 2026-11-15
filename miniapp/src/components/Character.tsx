/*
 * The Gym24 character: one SVG drawn in code (no images), in the app's colours.
 *
 *   level 0-4  body build gets broader and the outfit gains gear:
 *              0 Rookie   plain grey tee
 *              1 Beginner mint tee + lime wristbands
 *              2 Regular  gradient tank top + headband
 *              3 Advanced + lifting belt
 *              4 Pro      + medal
 *   mood       rested (smile), tired (sleepy eyes, sweat drop, slumped),
 *              celebrating (arms up, big smile, sparkles, a little bounce)
 *   size       width in px (height is 4/3 of it)
 */
import { useId } from "react";
import "./Character.css";

export type Mood = "rested" | "tired" | "celebrating";

const SKIN = "var(--color-text)";
const FACE = "var(--color-bg)";

function star(x: number, y: number, r: number): string {
  return `M${x} ${y - r} L${x + r * 0.3} ${y - r * 0.3} L${x + r} ${y} L${x + r * 0.3} ${y + r * 0.3} ` +
         `L${x} ${y + r} L${x - r * 0.3} ${y + r * 0.3} L${x - r} ${y} L${x - r * 0.3} ${y - r * 0.3} Z`;
}

export function Character({ level, mood, size = 140, label }: {
  level: number; mood: Mood; size?: number; label?: string;
}) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const lv = Math.max(0, Math.min(4, Math.round(level)));
  const b = lv / 4;                      // build 0..1
  const cx = 60;
  const slump = mood === "tired" ? 4 : 0;
  const sw = 20 + 9 * b;                 // half shoulder width
  const ww = 13 + 3 * b;                 // half waist width
  const arm = 7 + 4 * b;                 // arm thickness
  const shoulderY = 62 + slump;
  const waistY = 104 + slump / 2;
  const headY = shoulderY - 25;
  const up = mood === "celebrating";
  const shirt = lv === 0 ? "var(--color-surface-raised)" : lv === 1 ? "var(--color-mint)" : `url(#shirt${id})`;

  const armPath = (side: -1 | 1) => {
    const sx = cx + side * (sw - 3);
    const sy = shoulderY + 3;
    const elbow = up ? [cx + side * (sw + 12), shoulderY - 8] : [cx + side * (sw + 6), shoulderY + 18];
    const hand = up ? [cx + side * (sw + 6), shoulderY - 30] : [cx + side * (sw + 3), shoulderY + 38];
    return { d: `M${sx} ${sy} Q${elbow[0]} ${elbow[1]} ${hand[0]} ${hand[1]}`, hand };
  };
  const left = armPath(-1);
  const right = armPath(1);
  const legW = 10 + 2 * b;
  const torso = `M${cx - sw} ${shoulderY} Q${cx} ${shoulderY - 6} ${cx + sw} ${shoulderY} ` +
                `L${cx + ww} ${waistY} L${cx - ww} ${waistY} Z`;

  return (
    <svg className={`character character-${mood}`} width={size} height={(size * 4) / 3} viewBox="0 0 120 160"
         role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <defs>
        <linearGradient id={`shirt${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--color-mint)" />
          <stop offset="1" stopColor="var(--color-lime)" />
        </linearGradient>
        <radialGradient id={`glow${id}`}>
          <stop offset="0" stopColor="var(--color-mint)" stopOpacity="0.45" />
          <stop offset="1" stopColor="var(--color-mint)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <ellipse cx={cx} cy={152} rx={34} ry={7} fill={`url(#glow${id})`} />

      {/* legs and shorts */}
      <rect x={cx - ww + 1} y={waistY - 2} width={legW} height={44 - slump / 2} rx={5} fill={SKIN} />
      <rect x={cx + ww - 1 - legW} y={waistY - 2} width={legW} height={44 - slump / 2} rx={5} fill={SKIN} />
      <rect x={cx - ww - 2} y={waistY - 4} width={2 * ww + 4} height={16} rx={4} fill="var(--color-surface-sunken)" />

      {/* arms (behind the shirt when down, in front when raised) */}
      {!up && <path d={left.d} stroke={SKIN} strokeWidth={arm} strokeLinecap="round" fill="none" />}
      {!up && <path d={right.d} stroke={SKIN} strokeWidth={arm} strokeLinecap="round" fill="none" />}

      {/* neck, shirt, sleeves */}
      <rect x={cx - 5} y={shoulderY - 10} width={10} height={12} rx={3} fill={SKIN} />
      <path d={torso} fill={shirt} />
      {lv <= 1 && <circle cx={cx - sw + 2} cy={shoulderY + 3} r={arm * 0.9} fill={shirt} />}
      {lv <= 1 && <circle cx={cx + sw - 2} cy={shoulderY + 3} r={arm * 0.9} fill={shirt} />}

      {/* gear */}
      {lv >= 3 && (
        <>
          <rect x={cx - ww - 1} y={waistY - 9} width={2 * ww + 2} height={6} rx={2} fill={FACE} />
          <rect x={cx - 3} y={waistY - 9} width={6} height={6} rx={1} fill="var(--color-lime)" />
        </>
      )}
      {lv >= 4 && (
        <>
          <path d={`M${cx - 6} ${shoulderY - 2} L${cx} ${shoulderY + 14} L${cx + 6} ${shoulderY - 2}`}
                stroke="var(--color-mint)" strokeWidth={2} fill="none" />
          <circle cx={cx} cy={shoulderY + 18} r={5} fill="var(--color-lime)" />
        </>
      )}

      {up && <path d={left.d} stroke={SKIN} strokeWidth={arm} strokeLinecap="round" fill="none" />}
      {up && <path d={right.d} stroke={SKIN} strokeWidth={arm} strokeLinecap="round" fill="none" />}
      {lv >= 1 && [left.hand, right.hand].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={arm * 0.62} fill="none" stroke="var(--color-lime)" strokeWidth={2.2} />
      ))}

      {/* head */}
      <circle cx={cx} cy={headY} r={15} fill={SKIN} />
      {lv >= 2 && <rect x={cx - 15} y={headY - 10} width={30} height={5} rx={2}
                        fill={lv >= 4 ? "var(--color-lime)" : "var(--color-mint)"} />}

      {/* face */}
      {mood === "tired" ? (
        <>
          <path d={`M${cx - 8} ${headY} L${cx - 3} ${headY}`} stroke={FACE} strokeWidth={2} strokeLinecap="round" />
          <path d={`M${cx + 3} ${headY} L${cx + 8} ${headY}`} stroke={FACE} strokeWidth={2} strokeLinecap="round" />
          <path d={`M${cx - 4} ${headY + 8} L${cx + 4} ${headY + 8}`} stroke={FACE} strokeWidth={2} strokeLinecap="round" />
          <path d={`M${cx + 17} ${headY - 8} q3 5 0 7 q-3 -2 0 -7`} fill="var(--color-mint)" />
        </>
      ) : mood === "celebrating" ? (
        <>
          <path d={`M${cx - 8} ${headY} q2.5 -4 5 0`} stroke={FACE} strokeWidth={2} fill="none" strokeLinecap="round" />
          <path d={`M${cx + 3} ${headY} q2.5 -4 5 0`} stroke={FACE} strokeWidth={2} fill="none" strokeLinecap="round" />
          <path d={`M${cx - 6} ${headY + 5} Q${cx} ${headY + 14} ${cx + 6} ${headY + 5} Z`} fill={FACE} />
        </>
      ) : (
        <>
          <ellipse cx={cx - 5.5} cy={headY - 1} rx={1.8} ry={2.4} fill={FACE} />
          <ellipse cx={cx + 5.5} cy={headY - 1} rx={1.8} ry={2.4} fill={FACE} />
          <path d={`M${cx - 5} ${headY + 6} Q${cx} ${headY + 10} ${cx + 5} ${headY + 6}`} stroke={FACE}
                strokeWidth={2} fill="none" strokeLinecap="round" />
        </>
      )}

      {up && (
        <g fill="var(--color-lime)" className="character-sparkles">
          <path d={star(16, 34, 5)} />
          <path d={star(104, 26, 6)} />
          <path d={star(100, 70, 3.5)} />
          <path d={star(22, 76, 3)} />
        </g>
      )}
    </svg>
  );
}
