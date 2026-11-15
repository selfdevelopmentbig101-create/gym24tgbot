/*
 * Horizontal ruler picker (reference image 3): big value in the middle, the
 * values 5 units either side, ticks below and a mint pointer. Scroll/swipe to
 * change; arrow keys work too (role="slider").
 */
import { useEffect, useRef } from "react";
import { haptic } from "../lib/telegram";

const TICK_PX = 12;

interface Props {
  value: number;
  min: number;
  max: number;
  step: number;
  /** Units between the side labels and between tall ticks (e.g. 5 cm). */
  major?: number;
  format?: (value: number) => string;
  label: string;
  onChange: (value: number) => void;
}

export function Ruler({ value, min, max, step, major = 5, format = String, label, onChange }: Props) {
  const track = useRef<HTMLDivElement>(null);
  const settling = useRef(false);
  const count = Math.round((max - min) / step) + 1;
  const index = Math.round((value - min) / step);
  const toValue = (i: number) => Math.round((min + i * step) * 10) / 10;

  // Keep the scroll position in step with `value` (first render, unit switch, keys).
  useEffect(() => {
    const el = track.current;
    if (!el) return;
    if (Math.round(el.scrollLeft / TICK_PX) !== index) {
      settling.current = true;
      el.scrollLeft = index * TICK_PX;
      requestAnimationFrame(() => { settling.current = false; });
    }
  }, [index]);

  function onScroll() {
    const el = track.current;
    if (!el || settling.current) return;
    const i = Math.min(count - 1, Math.max(0, Math.round(el.scrollLeft / TICK_PX)));
    const next = toValue(i);
    if (next !== value) {
      haptic.select();
      onChange(next);
    }
  }

  function onKey(event: React.KeyboardEvent) {
    const moves: Record<string, number> = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1,
      PageDown: -10, PageUp: 10 };
    const move = moves[event.key];
    if (move === undefined) return;
    event.preventDefault();
    onChange(toValue(Math.min(count - 1, Math.max(0, index + move))));
  }

  const side = Math.round(major / step);
  const left = index - side >= 0 ? format(toValue(index - side)) : "";
  const right = index + side < count ? format(toValue(index + side)) : "";

  return (
    <div className="ruler">
      <div className="ruler-values" aria-hidden>
        <span className="ruler-side">{left}</span>
        <span className="ruler-value">{format(value)}</span>
        <span className="ruler-side">{right}</span>
      </div>
      <div ref={track} className="ruler-track" onScroll={onScroll} onKeyDown={onKey} tabIndex={0}
           role="slider" aria-label={label} aria-valuemin={min} aria-valuemax={max}
           aria-valuenow={value} aria-valuetext={format(value)}>
        {Array.from({ length: count }, (_, i) => {
          const isMajor = Math.round(toValue(i) / step) % side === 0;
          return <span key={i} className={`tick ${isMajor ? "tick-major" : ""}`} />;
        })}
      </div>
      <div className="ruler-pointer" aria-hidden />
    </div>
  );
}
