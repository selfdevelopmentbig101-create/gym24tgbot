/*
 * A-Z side index for long alphabetical lists (like a phone's contacts).
 * Tap a letter, or slide a finger along the strip, to jump to that section.
 * Each section needs id = idPrefix + letter (for example "az-B").
 */
import { useRef } from "react";
import { haptic } from "../lib/telegram";
import "./AzIndex.css";

export function AzIndex({ letters, idPrefix, label }: { letters: string[]; idPrefix: string; label: string }) {
  const last = useRef<string | null>(null);   // last letter jumped to (no repeat haptics while sliding)
  const touched = useRef(false);              // a touch already handled the tap; skip the click after it

  const jump = (letter: string | undefined) => {
    if (!letter || letter === last.current) return;
    last.current = letter;
    haptic.select();
    document.getElementById(idPrefix + letter)?.scrollIntoView({ block: "start" });
  };

  const letterAt = (x: number, y: number): string | undefined => {
    const el = document.elementFromPoint(x, y);
    return el instanceof HTMLElement ? el.dataset.letter : undefined;
  };

  if (letters.length < 2) return null;

  return (
    <nav className="az-index" aria-label={label}
         onTouchStart={(e) => {
           touched.current = true;
           last.current = null;
           const touch = e.touches[0];
           if (touch) jump(letterAt(touch.clientX, touch.clientY));
         }}
         onTouchMove={(e) => {
           const touch = e.touches[0];
           if (touch) jump(letterAt(touch.clientX, touch.clientY));
         }}>
      {letters.map((letter) => (
        <button key={letter} type="button" className="az-index-letter" data-letter={letter}
                onClick={() => {
                  if (touched.current) {
                    touched.current = false;
                    return;
                  }
                  last.current = null;
                  jump(letter);
                }}>
          {letter}
        </button>
      ))}
    </nav>
  );
}
