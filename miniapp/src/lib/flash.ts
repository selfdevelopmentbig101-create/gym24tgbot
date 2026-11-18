/* A one-time message carried across a navigation (e.g. "Split chosen" shown on the Splits list). */
let pending: string | null = null;

export function setFlash(message: string): void { pending = message; }

export function takeFlash(): string | null {
  const message = pending;
  pending = null;
  return message;
}
