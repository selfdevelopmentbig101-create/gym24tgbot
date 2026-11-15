/* /targets: the daily targets screen (calories, macros, goal date), opened from Home. */
import { useEffect } from "react";
import type { LanguageCode, Targets as TargetsData } from "../lib/api";
import { goBack } from "../lib/router";
import { bindNativeBack } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { PlanReady } from "./PlanReady";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function Targets({ targets, lang, t }: { targets: TargetsData; lang: LanguageCode; t: T }) {
  useEffect(() => bindNativeBack(() => goBack({ name: "home" })), []);
  return <PlanReady targets={targets} lang={lang} t={t} justFinished={false} planReady={false} languagePicker={null} />;
}
