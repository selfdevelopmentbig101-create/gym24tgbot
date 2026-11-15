/* Option rows (reference image 3, "biological sex"): icon circle, label, check when selected. */
import type { ReactNode } from "react";
import { Check } from "./Icons";
import { haptic } from "../lib/telegram";

export interface Option<T extends string> {
  value: T;
  label: string;
  hint?: string;
  icon?: ReactNode;
}

interface Props<T extends string> {
  options: Option<T>[];
  selected: T[];
  multi?: boolean;
  label: string;
  onToggle: (value: T) => void;
}

export function Options<T extends string>({ options, selected, multi = false, label, onToggle }: Props<T>) {
  return (
    <div className="options" role={multi ? "group" : "radiogroup"} aria-label={label}>
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
          </button>
        );
      })}
    </div>
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
