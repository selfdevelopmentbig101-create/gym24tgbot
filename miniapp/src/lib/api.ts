/*
 * API client. Every request carries Telegram's signed initData:
 *     Authorization: tma <initData>
 * The server checks the signature on every call; we never send a user ID ourselves.
 */
import { getInitData } from "./telegram";

const TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  /** 0 = network/timeout, 401 = login invalid or expired, 429 = too many requests */
  constructor(public status: number, public code: string) {
    super(code);
  }
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const initData = getInitData();
  if (!initData) throw new ApiError(401, "not_in_telegram");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers: {
        Authorization: `tma ${initData}`,
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(0, "network");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof data.detail === "string" ? data.detail : "error");
  }
  return (await response.json()) as T;
}

// ---------- Typed endpoints (match api/schemas.py) ----------

export type LanguageCode = "en" | "ru" | "uz";

export interface Me {
  first_name: string;
  language: LanguageCode | null;
  language_effective: LanguageCode;
  disclaimer_accepted: boolean;
  profile_complete: boolean;
}

export const getMe = () => api<Me>("/api/me");
export const setLanguage = (language: LanguageCode) =>
  api<Me>("/api/me/language", { method: "PATCH", body: { language } });
