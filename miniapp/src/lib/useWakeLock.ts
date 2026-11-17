/*
 * Keep the screen awake while `active` is true (Screen Wake Lock API).
 * Silently does nothing where it is not supported or the browser refuses.
 * The browser drops the lock when the page is hidden, so it is requested again on return.
 */
import { useEffect } from "react";

interface Sentinel { release(): Promise<void> }
interface WakeLockApi { request(type: "screen"): Promise<Sentinel> }

export function useWakeLock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const api = (navigator as unknown as { wakeLock?: WakeLockApi }).wakeLock;
    if (!api) return;

    let sentinel: Sentinel | null = null;
    let stopped = false;

    const acquire = async () => {
      try {
        const lock = await api.request("screen");
        if (stopped) {
          void lock.release().catch(() => {});
          return;
        }
        sentinel = lock;
      } catch {
        /* not allowed right now (battery saver, hidden page): try again on the next show */
      }
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void acquire();
    };

    void acquire();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      document.removeEventListener("visibilitychange", onVisible);
      void sentinel?.release().catch(() => {});
      sentinel = null;
    };
  }, [active]);
}
