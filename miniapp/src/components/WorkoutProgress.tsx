/*
 * Top of the guided workout: back button, "Exercise 2 of 6", and a segmented bar with one
 * segment per exercise (done = filled, current = highlighted, upcoming = muted).
 * With many exercises the bar scrolls sideways and keeps the current segment in view.
 * Under the bar: the names of the previous and next exercise.
 */
import { useEffect, useRef, type ReactNode } from "react";
import type { TextKey } from "../i18n";
import { ArrowLeft } from "./Icons";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export interface ProgressItem {
  name: string;
  status: "done" | "current" | "todo";
}

export function WorkoutProgress({ items, current, prevName, nextName, t, onBack, children }: {
  items: ProgressItem[];
  current: number;
  prevName: string | null;
  nextName: string | null;
  t: T;
  onBack: () => void;
  children?: ReactNode;
}) {
  const track = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const box = track.current;
    const segment = box?.children[current] as HTMLElement | undefined;
    if (!box || !segment) return;
    box.scrollTo({ left: segment.offsetLeft - (box.clientWidth - segment.clientWidth) / 2, behavior: "smooth" });
  }, [current, items.length]);

  return (
    <header className="gx-progress">
      <div className="gx-progress-top">
        <button type="button" className="gx-back" aria-label={t("back")} onClick={onBack}><ArrowLeft /></button>
        <span className="gx-progress-count">{t("gx_exercise_of", { n: current + 1, total: items.length })}</span>
        {children}
      </div>
      <div ref={track} className="gx-segs" role="progressbar" aria-label={t("gx_progress")}
           aria-valuemin={1} aria-valuemax={items.length} aria-valuenow={current + 1}>
        {items.map((item, i) => (
          <span key={i} title={item.name} className={"gx-seg gx-seg-" + item.status} />
        ))}
      </div>
      <div className="gx-neighbours">
        <span className="gx-nb-prev" title={prevName ? t("gx_prev", { name: prevName }) : undefined}>
          {prevName ? `‹ ${prevName}` : ""}
        </span>
        <span className="gx-nb-next" title={nextName ? t("gx_next", { name: nextName }) : undefined}>
          {nextName ? `${nextName} ›` : ""}
        </span>
      </div>
    </header>
  );
}
