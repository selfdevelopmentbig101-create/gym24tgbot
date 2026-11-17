/*
 * Full-screen start countdown: 3, 2, 1, then a short "GO!". Each step scales and fades in
 * (see workout.css), with a light haptic tap. Calls onDone when GO! is over.
 */
import { useEffect, useRef, useState } from "react";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

const NUMBER_MS = 900;
const GO_MS = 700;

export function Countdown({ t, onDone }: { t: T; onDone: () => void }) {
  const [step, setStep] = useState(0);          // 0, 1, 2 = "3", "2", "1"; 3 = GO!
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    haptic.tap();
    const timer = setTimeout(() => {
      if (step < 3) setStep(step + 1);
      else done.current();
    }, step < 3 ? NUMBER_MS : GO_MS);
    return () => clearTimeout(timer);
  }, [step]);

  const isGo = step === 3;
  return (
    <div className="gx-countdown" role="timer" aria-live="assertive">
      <span key={step} className={"gx-count-num" + (isGo ? " gx-count-go" : "")}>
        {isGo ? t("gx_go") : 3 - step}
      </span>
    </div>
  );
}
