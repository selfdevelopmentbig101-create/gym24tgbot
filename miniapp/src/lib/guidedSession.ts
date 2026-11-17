/*
 * Guided workout: what the app remembers on THIS phone so a workout can be resumed after
 * the Mini App was closed (which exercise, whether we were resting, how much rest is left).
 * The sets themselves live on the server (they are saved one by one through the API); this
 * only stores the screen state. It is never sent to the API.
 */
import { localUserKey } from "./telegram";

export type GuidedPhase = "countdown" | "exercise" | "done" | "rest";

export interface GuidedState {
  workoutId: number;
  phase: GuidedPhase;
  index: number;                 // exercise on screen (in "rest": the one just finished)
  finished: number[];            // exercises finished in the guided flow (even with fewer sets than planned)
  restEndsAt: number | null;     // epoch ms
  restTotal: number;             // seconds
  restChoice: number;            // seconds picked on the "completed" screen, 0 = skip
  at: number;                    // when this was saved (epoch ms)
}

const COUNTDOWN_MAX_AGE_MS = 30_000;
const storageKey = () => `gym24.guided.${localUserKey()}`;

export function loadGuided(workoutId: number): GuidedState | null {
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return null;
    const state = JSON.parse(raw) as GuidedState;
    if (state.workoutId !== workoutId || !Array.isArray(state.finished)) return null;
    return state;
  } catch {
    return null;
  }
}

export function saveGuided(state: GuidedState): void {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(state));
  } catch {
    /* private mode / storage full: resuming still works from the server's data */
  }
}

export function clearGuided(): void {
  try {
    localStorage.removeItem(storageKey());
  } catch {
    /* ignore */
  }
}

/** Called right after "Start training": the guided screen opens with the 3-2-1 countdown. */
export function markFreshStart(workoutId: number): void {
  saveGuided({
    workoutId, phase: "countdown", index: 0, finished: [],
    restEndsAt: null, restTotal: 0, restChoice: 90, at: Date.now(),
  });
}

/** A countdown saved a moment ago is replayed; an old one means the user is resuming. */
export function countdownIsFresh(state: GuidedState): boolean {
  return state.phase === "countdown" && Date.now() - state.at < COUNTDOWN_MAX_AGE_MS;
}
