/* Option rows (reference image 3, "biological sex"): icon circle, label, check when selected.
 * Card style (reference goal cards): taller row with an optional illustration on the right. */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check } from "./Icons";
import { haptic } from "../lib/telegram";

export interface Option<T extends string> {
  value: T;
  label: string;
  hint?: string;
  icon?: ReactNode;
  /** Illustration on the right of a card (URL). Empty until the artwork is added. */
  art?: string;
  /** How the illustration fills its panel: "contain" for cut-out art (default),
   *  "cover" for images that already carry their own background. */
  artFit?: "contain" | "cover";
}

interface Props<T extends string> {
  options: Option<T>[];
  selected: T[];
  multi?: boolean;
  label: string;
  /** Taller cards with room for an illustration on the right. */
  card?: boolean;
  onToggle: (value: T) => void;
}

export function Options<T extends string>({ options, selected, multi = false, label, card = false, onToggle }: Props<T>) {
  return (
    <div className={"options" + (card ? " options-cards" : "")} role={multi ? "group" : "radiogroup"} aria-label={label}>
      {options.map((option) => {
        const on = selected.includes(option.value);
        return (
          <button key={option.value} type="button" role={multi ? "checkbox" : "radio"} aria-checked={on}
                  className={`option ${on ? "option-on" : ""}`}
                  onClick={() => { haptic.select(); onToggle(option.value); }}>
            {option.icon && <span className="option-icon">{option.icon}</span>}
            <span className="option-text">
              <span className="option-label">{option.label}</span>
              {option.hint && <span className="option-hint">{option.hint}</span>}
            </span>
            <span className={`option-check ${on ? "option-check-on" : ""}`}>{on && <Check />}</span>
            {option.art && <OptionArt src={option.art} fit={option.artFit ?? "contain"} />}
          </button>
        );
      })}
    </div>
  );
}

/** Card illustration: stays hidden until it loads, disappears if the file is missing. */
function OptionArt({ src, fit }: { src: string; fit: "contain" | "cover" }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const ref = useRef<HTMLImageElement>(null);

  // Cached images can finish before React attaches onLoad.
  useEffect(() => {
    const image = ref.current;
    if (image?.complete) setState(image.naturalWidth ? "ready" : "error");
  }, [src]);

  if (state === "error") return null;
  return (
    <img ref={ref} className={`option-art option-art-${fit}`} src={src} alt="" loading="lazy" decoding="async"
         style={state === "loading" ? { visibility: "hidden" } : undefined}
         onLoad={() => setState("ready")}
         onError={() => setState("error")} />
  );
}

/** Two-way unit switch (cm | in, kgs | lbs). */
export function UnitToggle<T extends string>({ value, options, label, onChange }:
  { value: T; options: { value: T; label: string }[]; label: string; onChange: (value: T) => void }) {
  return (
    <div className="toggle" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value}
                className={`toggle-item ${o.value === value ? "toggle-on" : ""}`}
                onClick={() => { haptic.select(); onChange(o.value); }}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
