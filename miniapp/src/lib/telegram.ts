/*
 * Thin, typed wrapper around Telegram's Mini App SDK (window.Telegram.WebApp,
 * loaded by the <script> in index.html). Docs: https://core.telegram.org/bots/webapps
 *
 * initData is passed to our API untouched; the SERVER verifies it. The
 * "unsafe" user object here is only for instant display, never for security.
 */

type HapticImpact = "light" | "medium" | "heavy" | "rigid" | "soft";
type HapticNotice = "error" | "success" | "warning";

interface TelegramSafeArea {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; language_code?: string }; start_param?: string };
  version: string;
  platform: string;
  isFullscreen?: boolean;
  safeAreaInset?: TelegramSafeArea;
  contentSafeAreaInset?: TelegramSafeArea;
  ready(): void;
  close(): void;
  expand(): void;
  requestFullscreen?(): void;
  isVersionAtLeast(version: string): boolean;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
  setBottomBarColor?(color: string): void;
  disableVerticalSwipes?(): void;
  onEvent?(event: string, callback: () => void): void;
  offEvent?(event: string, callback: () => void): void;
  showConfirm?(message: string, callback: (confirmed: boolean) => void): void;
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

/** Start-up: tell Telegram we're ready, go full screen, match our colours. */
export function initTelegram(): void {
  const app = getWebApp();
  if (!app) return;
  app.ready();
  app.expand();
  // Bot API 8.0+: occupy the whole screen (the launch link may still force compact mode).
  if (app.isVersionAtLeast("8.0")) {
    try {
      app.requestFullscreen?.();
    } catch {
      /* the bot has full-screen mode disabled in BotFather, or an older client */
    }
  }
  if (app.isVersionAtLeast("6.1")) {
    app.setHeaderColor("#151A18");
    app.setBackgroundColor("#151A18");
  }
  if (app.isVersionAtLeast("7.10")) app.setBottomBarColor?.("#151A18");
  // Stop accidental swipe-down-to-close while scrolling lists and rulers.
  if (app.isVersionAtLeast("7.7")) app.disableVerticalSwipes?.();
  syncSafeArea(app);
  // The insets and viewport change when the app goes full screen or the device rotates.
  if (app.onEvent) {
    const update = () => syncSafeArea(app);
    app.onEvent("fullscreenChanged", update);
    app.onEvent("safeAreaChanged", update);
    app.onEvent("contentSafeAreaChanged", update);
    app.onEvent("viewportChanged", update);
  }
}

/**
 * Keep the layout under Telegram's UI (notch, status bar, floating close/menu
 * buttons in full-screen mode). tokens.css falls back to the --tg-* variables.
 */
function syncSafeArea(app: TelegramWebApp): void {
  const root = document.documentElement;
  const safe = app.safeAreaInset;
  const content = app.contentSafeAreaInset;
  if (!safe) {
    root.style.removeProperty("--app-safe-top");
    root.style.removeProperty("--app-safe-bottom");
    return;
  }
  const baseTop = Math.max(0, safe.top) + Math.max(0, content?.top ?? 0);
  // Full screen hides Telegram's header, but its floating controls still overlay the top edge.
  const top = app.isFullscreen ? Math.max(baseTop, 56) : baseTop;
  const bottom = Math.max(0, safe.bottom) + Math.max(0, content?.bottom ?? 0);
  root.style.setProperty("--app-safe-top", `${top}px`);
  root.style.setProperty("--app-safe-bottom", `${bottom}px`);
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

/** Close the Mini App and go back to the chat (no-op in a normal browser). */
export function closeApp(): void {
  safe(() => getWebApp()?.close());
}

/**
 * Show Telegram's own Back button (top bar / Android back) while `onBack` is set.
 * Returns a cleanup function, for use in an effect.
 */
export function bindNativeBack(onBack: (() => void) | null): () => void {
  const app = getWebApp();
  if (!app || !onBack || !app.isVersionAtLeast("6.1")) {
    safe(() => app?.BackButton.hide());
    return () => {};
  }
  app.BackButton.onClick(onBack);
  app.BackButton.show();
  return () => {
    app.BackButton.offClick(onBack);
    app.BackButton.hide();
  };
}

/** Ask a yes/no question: Telegram's own popup when available, the browser's otherwise. */
export function confirmDialog(message: string, onResult: (confirmed: boolean) => void): void {
  const app = getWebApp();
  if (app?.showConfirm && app.isVersionAtLeast("6.2")) {
    try {
      app.showConfirm(message, onResult);
      return;
    } catch {
      /* fall back to the browser's dialog */
    }
  }
  onResult(window.confirm(message));
}

/** Phone vibration where the browser allows it (mostly Android). Haptics cover the rest. */
export function vibrate(pattern: number | number[]): void {
  safe(() => navigator.vibrate?.(pattern));
}

/** Telegram's user id, ONLY for keying local drafts on this device. Never sent to the API. */
export function localUserKey(): string {
  return String(getWebApp()?.initDataUnsafe.user?.id ?? "anon");
}
