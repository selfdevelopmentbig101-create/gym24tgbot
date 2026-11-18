/* Train > Splits: a 2-column grid of equal cards, the active split first, then "+ Add split". */
import { useCallback, useEffect, useState } from "react";
import { getSplits, trainErrorKey, type Split, type SplitList } from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import { takeFlash } from "../lib/flash";
import type { TextKey } from "../i18n";
import { ArrowLeft } from "../components/Icons";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

/** services/program_rules.py::MAX_DAYS: the program's days are the splits. */
const MAX_SPLITS = 7;

export function splitDescription(split: Split, t: T): string {
  const muscles = split.muscles.slice(0, 4).map((m) => t(("muscle_" + m) as TextKey));
  return muscles.length ? t("split_description", { muscles: muscles.join(", ") }) : t("split_empty");
}

export function BackHeader({ title, t, onBack }: { title: string; t: T; onBack: () => void }) {
  return (
    <header className="train-sub-head">
      <button type="button" className="round-button round-back" onClick={onBack} aria-label={t("back")}>
        <ArrowLeft />
      </button>
      <h1 className="screen-title left">{title}</h1>
    </header>
  );
}

export function Splits({ t }: { t: T }) {
  const [data, setData] = useState<SplitList | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const [toast, setToast] = useState<string | null>(takeFlash);

  const load = useCallback(() => {
    setError(null);
    getSplits().then(setData).catch((e) => setError(trainErrorKey(e)));
  }, []);
  useEffect(load, [load]);
  const back = () => goBack({ name: "workout" });
  useEffect(() => bindNativeBack(back), []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2200);
    return () => clearTimeout(timer);
  }, [toast]);

  // The active split comes first; Array.sort is stable, so the others keep their order.
  const splits = data ? [...data.splits].sort((a, b) => Number(b.active) - Number(a.active)) : [];
  const canAdd = splits.length < MAX_SPLITS;

  return (
    <main className="train">
      <BackHeader title={t("train_splits")} t={t} onBack={back} />
      {toast && <div className="toast" role="status">{toast}</div>}

      {error && (
        <section className="card center" role="alert">
          <p>{t(error)}</p>
          <button type="button" className="button-primary" onClick={load}>{t("retry")}</button>
        </section>
      )}
      {!data && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {data && (
        <>
          <div className="splits-grid">
            {splits.map((split) => (
              <button key={split.id} type="button"
                      className={"split-tile" + (split.active ? " split-tile-active" : "")}
                      onClick={() => { haptic.tap(); navigate({ name: "split", id: split.id }); }}>
                <span className="split-tile-top">
                  {split.active && <span className="split-badge">{t("split_active_badge")}</span>}
                </span>
                <span className="split-tile-name">{dayName(split, t)}</span>
                <span className="split-tile-meta">
                  {t("split_tile_exercises", { n: split.exercises.length })}
                </span>
                <span className="split-tile-minutes">{t("train_minutes", { n: split.minutes })}</span>
              </button>
            ))}
            {canAdd && (
              <button type="button" className="split-tile split-tile-add"
                      onClick={() => { haptic.tap(); navigate({ name: "splitNew" }); }}>
                <span className="split-add-plus" aria-hidden>+</span>
                <span className="split-tile-add-label">{t("split_add")}</span>
              </button>
            )}
          </div>

          {!canAdd && <p className="muted small">{t("splits_limit", { n: MAX_SPLITS })}</p>}
        </>
      )}
    </main>
  );
}
