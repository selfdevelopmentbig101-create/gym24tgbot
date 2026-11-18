/* Train > Splits: the active split on top (highlighted), every other split below. */
import { useCallback, useEffect, useState } from "react";
import { getSplits, trainErrorKey, type Split, type SplitList } from "../lib/trainApi";
import { dayName } from "../lib/planText";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack, haptic } from "../lib/telegram";
import { takeFlash } from "../lib/flash";
import type { TextKey } from "../i18n";
import { ArrowLeft, ChevronRight } from "../components/Icons";
import "./plan.css";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

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

  const active = data?.splits.find((s) => s.active) ?? null;
  const others = data?.splits.filter((s) => !s.active) ?? [];

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
      {data && data.splits.length === 0 && <div className="empty"><p>{t("splits_empty")}</p></div>}

      {active && (
        <button type="button" className="card split-card split-active"
                onClick={() => { haptic.tap(); navigate({ name: "split", id: active.id }); }}>
          <span className="split-card-top">
            <span className="split-badge">{t("split_active_badge")}</span>
          </span>
          <span className="split-card-name">{dayName(active, t)}</span>
          <span className="muted small">{splitDescription(active, t)}</span>
          <span className="split-card-meta">{t("split_meta", { n: active.exercises.length, min: active.minutes })}</span>
        </button>
      )}

      {others.length > 0 && (
        <>
          <h2 className="section-label">{t("splits_other")}</h2>
          <div className="rows">
            {others.map((s) => (
              <button key={s.id} type="button" className="split-row"
                      onClick={() => { haptic.tap(); navigate({ name: "split", id: s.id }); }}>
                <span className="exercise-text">
                  <span className="exercise-name">{dayName(s, t)}</span>
                  <span className="exercise-meta">{t("split_meta", { n: s.exercises.length, min: s.minutes })}</span>
                </span>
                <ChevronRight />
              </button>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
