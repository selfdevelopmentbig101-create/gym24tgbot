/*
 * ExerciseImage: one reusable picture box for an exercise.
 *
 *   start + peak  -> loops between the two frames like an animation
 *                    (smooth crossfade, about 1.8 s per loop). Tap to pause / play.
 *   one image     -> shown as a still (no loop).
 *   no image      -> placeholder with a muscle icon (plus a caption or form tips).
 *
 * Both frames are preloaded before the loop starts. Images load only when the
 * box comes near the screen, so long lists stay fast. The box has a fixed size
 * (aspect ratio) and a skeleton while loading, so the layout never jumps.
 */
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { haptic } from "../lib/telegram";
import { Dumbbell } from "./Icons";
import "./ExerciseImage.css";

export interface ExerciseImageProps {
  start?: string | null;
  peak?: string | null;
  still?: string | null;
  /** Primary muscle (used for the placeholder). */
  muscle: string;
  /** Accessible name, usually the exercise name. Empty = decorative (lists). */
  label?: string;
  /** "thumb" = small list picture (still only); "large" = detail screen (animated). */
  size?: "thumb" | "large";
  /** Large placeholder only: a short line under the icon, e.g. the muscle name. */
  caption?: string;
  /** Large placeholder only: form tips to show when there is no image. */
  tips?: string[];
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

export function ExerciseImage({ start, peak, still, muscle, label = "", size = "large", caption, tips = [] }: ExerciseImageProps) {
  const wantsLoop = size === "large" && Boolean(start && peak);
  const single = still ?? start ?? peak ?? null;
  const frames: string[] = wantsLoop ? [start as string, peak as string] : single ? [single] : [];
  const framesKey = frames.join("|");

  const box = useRef<HTMLDivElement>(null);
  const near = useNearScreen(box, frames.length > 0);
  // Frames that finished loading (null = still loading).
  const [loaded, setLoaded] = useState<string[] | null>(null);
  // Respect the phone's "reduce motion" setting: start paused there.
  const [playing, setPlaying] = useState(() => !prefersReducedMotion());

  useEffect(() => {
    setLoaded(null);
    if (!near || frames.length === 0) return;
    let live = true;
    Promise.all(frames.map(preload)).then((ok) => {
      if (live) setLoaded(frames.filter((_, i) => ok[i]));
    });
    return () => { live = false; };
  }, [near, framesKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const ready = loaded !== null;
  const failed = loaded !== null && loaded.length === 0;
  // Only loop when BOTH frames loaded; if one failed, show the other as a still.
  const animated = wantsLoop && loaded !== null && loaded.length === 2;
  const shown = loaded ?? frames;

  // ---- No image (or every image failed): placeholder ----
  if (frames.length === 0 || failed) {
    return (
      <div className={`ex-image ex-image-${size} ex-image-empty`} data-muscle={muscle}
           role={label ? "img" : undefined} aria-label={label || undefined}
           aria-hidden={label ? undefined : true}>
        <Dumbbell />
        {size === "large" && caption && <p className="ex-image-caption">{caption}</p>}
        {size === "large" && tips.length > 0 && (
          <ul className="ex-image-tips">
            {tips.slice(0, 3).map((tip, i) => <li key={i}>{tip}</li>)}
          </ul>
        )}
      </div>
    );
  }

  const toggle = () => {
    if (!animated) return;
    haptic.tap();
    setPlaying((p) => !p);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggle();
    }
  };

  const classes = ["ex-image", `ex-image-${size}`];
  if (ready) classes.push("ex-image-ready");
  if (animated) classes.push(playing ? "ex-image-playing" : "ex-image-paused");

  return (
    <div ref={box} className={classes.join(" ")}
         role={animated ? "button" : label ? "img" : undefined}
         aria-label={label || undefined}
         aria-hidden={!animated && !label ? true : undefined}
         aria-pressed={animated ? !playing : undefined}
         tabIndex={animated ? 0 : undefined}
         onClick={animated ? toggle : undefined}
         onKeyDown={animated ? onKey : undefined}>
      {!ready && <span className="ex-image-skeleton" aria-hidden />}
      {near && <img className="ex-image-frame" src={shown[0]} alt="" decoding="async" draggable={false} />}
      {near && animated && (
        <img className="ex-image-frame ex-image-peak" src={shown[1]} alt="" decoding="async" draggable={false} />
      )}
      {animated && !playing && <span className="ex-image-badge" aria-hidden><PlayIcon /></span>}
    </div>
  );
}

/** Load an image in the background; resolves true when it loaded, false on error. */
function preload(src: string): Promise<boolean> {
  return new Promise((resolve) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = src;
  });
}

/** True once the element is on (or close to) the screen. Stays true after that. */
function useNearScreen(ref: RefObject<HTMLElement | null>, enabled: boolean): boolean {
  const [near, setNear] = useState(false);
  useEffect(() => {
    if (!enabled || near) return;
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setNear(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px 0px" },  // start loading a little before it scrolls into view
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, enabled, near]);
  return near;
}

function PlayIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
      <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
    </svg>
  );
}
