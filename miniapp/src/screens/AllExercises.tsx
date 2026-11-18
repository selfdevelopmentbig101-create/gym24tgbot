/*
 * Train > All exercises. A segmented toggle (remembered for this session):
 *   By muscle  2-column grid of anatomy cards (public/muscles/{key}.png, placeholder if missing)
 *   All        every exercise, A-Z, with a name search
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ExerciseList } from "../lib/api";
import { getAllExercises, getMuscles, trainErrorKey, type MuscleGroup } from "../lib/trainApi";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { Close, Dumbbell, Search } from "../components/Icons";
import { ExerciseRow } from "../components/ExerciseRow";
import { BackHeader } from "./Splits";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;
type Mode = "muscle" | "all";

const MODE_KEY = "gym24.exercises.mode";
const SEARCH_KEY = "gym24.exercises.q";
const MUSCLE_IMAGES = "/muscles/";

function savedMode(): Mode {
  try { return sessionStorage.getItem(MODE_KEY) === "all" ? "all" : "muscle"; } catch { return "muscle"; }
}

export function AllExercises({ t, locale }: { t: T; locale: string }) {
  const [mode, setMode] = useState<Mode>(savedMode);
  const back = () => goBack({ name: "workout" });
  useEffect(() => bindNativeBack(back), []); // eslint-disable-line react-hooks/exhaustive-deps

  function pick(next: Mode) {
    if (next === mode) return;
    haptic.select();
    setMode(next);
    try { sessionStorage.setItem(MODE_KEY, next); } catch { /* private mode */ }
  }

  return (
    <main className="train">
      <BackHeader title={t("train_all_exercises")} t={t} onBack={back} />
      <div className="segmented" role="tablist" aria-label={t("train_all_exercises")}>
        <button type="button" role="tab" aria-selected={mode === "muscle"}
                className={"segment" + (mode === "muscle" ? " segment-on" : "")} onClick={() => pick("muscle")}>
          {t("exercises_by_muscle")}
        </button>
        <button type="button" role="tab" aria-selected={mode === "all"}
                className={"segment" + (mode === "all" ? " segment-on" : "")} onClick={() => pick("all")}>
          {t("exercises_all")}
        </button>
      </div>
      {mode === "muscle" ? <MuscleGrid t={t} /> : <AllList t={t} locale={locale} />}
    </main>
  );
}

function MuscleGrid({ t }: { t: T }) {
  const [items, setItems] = useState<MuscleGroup[] | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const load = useCallback(() => {
    setError(null);
    getMuscles().then((r) => setItems(r.items)).catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorCard t={t} error={error} onRetry={load} />;
  if (!items) return <div className="spinner center-spinner" aria-label={t("loading")} />;
  if (items.length === 0) return <div className="empty"><p>{t("no_results")}</p></div>;
  return (
    <div className="muscle-grid">
      {items.map((m) => (
        <button key={m.key} type="button" className="muscle-card"
                onClick={() => { haptic.tap(); navigate({ name: "muscle", key: m.key }); }}>
          <MuscleImage file={m.image} />
          <span className="muscle-name">{t(("muscle_" + m.key) as TextKey)}</span>
          <span className="muted small">{t("muscle_count", { n: m.count })}</span>
        </button>
      ))}
    </div>
  );
}

export function MuscleImage({ file }: { file: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="muscle-image">
      {failed ? <span className="muscle-placeholder"><Dumbbell /></span>
              : <img src={MUSCLE_IMAGES + file} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />}
    </span>
  );
}

function AllList({ t, locale }: { t: T; locale: string }) {
  const [data, setData] = useState<ExerciseList | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [q, setQ] = useState(() => { try { return sessionStorage.getItem(SEARCH_KEY) ?? ""; } catch { return ""; } });
  const load = useCallback(() => {
    setError(null);
    getAllExercises().then(setData).catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load]);
  useEffect(() => { try { sessionStorage.setItem(SEARCH_KEY, q); } catch { /* ignore */ } }, [q]);

  const shown = useMemo(() => {
    const needle = q.trim().toLocaleLowerCase(locale);
    const items = [...(data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name, locale));
    return needle ? items.filter((i) => i.name.toLocaleLowerCase(locale).includes(needle)) : items;
  }, [data, q, locale]);

  return (
    <>
      <label className="search">
        <Search />
        <input type="search" value={q} placeholder={t("exercises_search")} enterKeyHint="search"
               aria-label={t("exercises_search")} maxLength={60} onChange={(e) => setQ(e.target.value)} />
        {q && (
          <button type="button" className="search-clear" aria-label={t("clear")} onClick={() => setQ("")}><Close /></button>
        )}
      </label>
      {error && <ErrorCard t={t} error={error} onRetry={load} />}
      {!data && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}
      {data && shown.length === 0 && (
        <div className="empty">
          <p>{t("no_results")}</p>
          {q && <button type="button" className="button-link" onClick={() => setQ("")}>{t("clear")}</button>}
        </div>
      )}
      {data && shown.length > 0 && (
        <div className="rows">
          {shown.map((item) => (
            <ExerciseRow key={item.id} item={item} t={t} onOpen={() => navigate({ name: "exercise", id: item.id })} />
          ))}
        </div>
      )}
    </>
  );
}

export function ErrorCard({ t, error, onRetry }: { t: T; error: TextKey; onRetry: () => void }) {
  return (
    <section className="card center" role="alert">
      <p>{t(error)}</p>
      <button type="button" className="button-primary" onClick={() => { haptic.tap(); onRetry(); }}>{t("retry")}</button>
    </section>
  );
}
