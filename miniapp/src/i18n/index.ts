/*
 * Mini App texts. One JSON file per language in this folder; missing keys fall
 * back to English. To add Uzbek texts, fill uz.json with the same keys as en.json.
 */
import en from "./en.json";
import ru from "./ru.json";
import uz from "./uz.json";
import type { LanguageCode } from "../lib/api";

type Dict = Record<string, string>;
const DICTS: Record<LanguageCode, Dict> = { en, ru, uz };

export type TextKey = keyof typeof en;

export function translate(lang: LanguageCode, key: TextKey, vars: Record<string, string | number> = {}): string {
  const template = DICTS[lang]?.[key] ?? (en as Dict)[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}
