/* − value + control with big tap targets (sets, reps, rest, weeks). */
import { haptic } from "../lib/telegram";

export function Stepper({ label, value, min, max, step = 1, format, onChange }: {
  label: string; value: number; min: number; max: number; step?: number;
  format?: (value: number) => string; onChange: (value: number) => void;
}) {
  const set = (next: number) => {
    const clamped = Math.max(min, Math.min(max, next));
    if (clamped !== value) {
      haptic.select();
      onChange(clamped);
    }
  };
  return (
    <div className="stepper">
      <span className="stepper-label">{label}</span>
      <div className="stepper-controls">
        <button type="button" aria-label={label + " −"} disabled={value <= min} onClick={() => set(value - step)}>−</button>
        <span className="stepper-value" aria-live="polite">{format ? format(value) : value}</span>
        <button type="button" aria-label={label + " +"} disabled={value >= max} onClick={() => set(value + step)}>+</button>
      </div>
    </div>
  );
}
