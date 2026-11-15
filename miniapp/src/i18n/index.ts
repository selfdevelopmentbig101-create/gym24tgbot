/*
 * Mini App texts. One JSON file per language in this folder; missing keys fall
 * back to English. To add Uzbek texts, fill uz.json (and later plan.uz.json,
 * train.uz.json) with the same keys as the English files.
 *
 * A feature can keep its texts in its own file (plan.*.json, train.*.json);
 * they are merged here, so screens just call t("key").
 */
import en from "./en.json";
import ru from "./ru.json";
import uz from "./uz.json";
import planEn from "./plan.en.json";
import planRu from "./plan.ru.json";
import trainEn from "./train.en.json";
import trainRu from "./train.ru.json";
import type { LanguageCode } from "../lib/api";

type Dict = Record<string, string>;
const EN = { ...en, ...planEn, ...trainEn };
const DICTS: Record<LanguageCode, Dict> = { en: EN, ru: { ...ru, ...planRu, ...trainRu }, uz };

export type TextKey = keyof typeof EN;

export function translate(lang: LanguageCode, key: TextKey, vars: Record<string, string | number> = {}): string {
  const template = DICTS[lang]?.[key] ?? (EN as Dict)[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}
