/*
 * Thin, typed wrapper around Telegram's Mini App SDK (window.Telegram.WebApp,
 * loaded by the <script> in index.html). Docs: https://core.telegram.org/bots/webapps
 *
 * initData is passed to our API untouched; the SERVER verifies it. The
 * "unsafe" user object here is only for instant display, never for security.
 */

type HapticImpact = "light" | "medium" | "heavy" | "rigid" | "soft";
type HapticNotice = "error" | "success" | "warning";

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; language_code?: string }; start_param?: string };
  version: string;
  platform: string;
  ready(): void;
  expand(): void;
  isVersionAtLeast(version: string): boolean;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
  setBottomBarColor?(color: string): void;
  disableVerticalSwipes?(): void;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback: {
    impactOccurred(style: HapticImpact): void;
    notificationOccurred(type: HapticNotice): void;
    selectionChanged(): void;
  };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

/** The signed login string, or "" when opened outside Telegram (or from a reply keyboard). */
export function getInitData(): string {
  return getWebApp()?.initData ?? "";
}

/** Start-up: tell Telegram we're ready, use the full height, match our colours. */
export function initTelegram(): void {
  const app = getWebApp();
  if (!app) return;
  app.ready();
  app.expand();
  if (app.isVersionAtLeast("6.1")) {
    app.setHeaderColor("#151A18");
    app.setBackgroundColor("#151A18");
  }
  if (app.isVersionAtLeast("7.10")) app.setBottomBarColor?.("#151A18");
  // Stop accidental swipe-down-to-close while scrolling lists and rulers.
  if (app.isVersionAtLeast("7.7")) app.disableVerticalSwipes?.();
}

/** Haptic feedback on key taps. Silently does nothing outside Telegram. */
export const haptic = {
  tap: () => safe(() => getWebApp()?.HapticFeedback.impactOccurred("light")),
  select: () => safe(() => getWebApp()?.HapticFeedback.selectionChanged()),
  success: () => safe(() => getWebApp()?.HapticFeedback.notificationOccurred("success")),
  warning: () => safe(() => getWebApp()?.HapticFeedback.notificationOccurred("warning")),
  error: () => safe(() => getWebApp()?.HapticFeedback.notificationOccurred("error")),
};

function safe(fn: () => void) {
  try {
    fn();
  } catch {
    /* older clients without haptics */
  }
}
