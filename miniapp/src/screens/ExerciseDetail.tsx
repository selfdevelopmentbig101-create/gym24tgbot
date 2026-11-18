/*
 * Exercise detail: looping start/peak images (tap to pause), primary and secondary
 * muscles, why it isn't in your plans, form tips, substitutes.
 */
import { useEffect, useState } from "react";
import { ApiError, getExercise, type ExerciseDetail as Detail } from "../lib/api";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ArrowLeft, Info, Swap } from "../components/Icons";
import { ExerciseRow } from "../components/ExerciseRow";
import { ExerciseImage } from "../components/ExerciseImage";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function ExerciseDetail({ id, t, attribution }: { id: string; t: T; attribution: string }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<TextKey | null>(null);

  useEffect(() => {
    let live = true;
    setDetail(null);
    setError(null);
    getExercise(id)
      .then((d) => { if (live) setDetail(d); })
      .catch((e) => { if (live) setError(e instanceof ApiError && e.status === 404 ? "exercise_missing" : "error_generic"); });
    return () => { live = false; };
  }, [id]);

  const back = () => goBack({ name: "exercises" });
  useEffect(() => bindNativeBack(back), [id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="detail">
      <header className="detail-header">
        <button type="button" className="round-button round-back" onClick={back} aria-label={t("back")}>
          <ArrowLeft />
        </button>
      </header>

      {error && <p className="muted center-text" role="alert">{t(error)}</p>}
      {!detail && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}

      {detail && (
        <article className="detail-body" key={detail.id}>
          {/* The form tips card below covers the tips, so the placeholder shows just the muscle. */}
          <ExerciseImage start={detail.media.start} peak={detail.media.peak} still={detail.media.still}
                         muscle={detail.muscle_group} label={detail.name}
                         caption={t(("muscle_" + detail.muscle_group) as TextKey)} />
          {detail.media.kind && <p className="credits">{attribution}</p>}

          <h1 className="detail-title">{detail.name}</h1>
          <div className="detail-tags">
            <span className={"level level-" + detail.difficulty}>{t(("level_" + detail.difficulty) as TextKey)}</span>
            <span className="tag">{t(("equip_" + detail.equipment.replace(/ /g, "_")) as TextKey)}</span>
            <span className="tag">{t(("move_" + detail.movement_type) as TextKey)}</span>
            {detail.home_friendly && <span className="tag">{t("home_friendly")}</span>}
          </div>

          {detail.reasons.length > 0 && (
            <div className="notice" role="note">
              <Info />
              <div>
                <p className="notice-title">{t("not_in_plan_title")}</p>
                {detail.reasons.map((r) => <p key={r}>{t(("reason_" + r) as TextKey)}</p>)}
              </div>
            </div>
          )}

          <section className="card">
            <h2 className="card-title">{t("muscles_worked")}</h2>
            <div className="muscles">
              <span className="muscle muscle-primary">
                <span className="muscle-dot" />{t(("muscle_" + detail.muscle_group) as TextKey)}
                <span className="muscle-role">{t("primary")}</span>
              </span>
              {detail.secondary_muscles.map((m) => (
                <span key={m} className="muscle">
                  <span className="muscle-dot muscle-dot-secondary" />{t(("muscle_" + m) as TextKey)}
                </span>
              ))}
            </div>
          </section>

          <section className="card">
            <h2 className="card-title">{t("form_tips")}</h2>
            {detail.form_tips
              ? <ul className="tips">{detail.form_tips.split("\n").filter(Boolean).map((tip, i) => <li key={i}>{tip}</li>)}</ul>
              : <p className="muted small">{t("form_tips_missing")}</p>}
          </section>

          {detail.substitutes.length > 0 && (
            <section>
              <h2 className="section-label with-icon"><Swap />{t("substitutes")}</h2>
              <div className="rows">
                {detail.substitutes.map((s) => (
                  <ExerciseRow key={s.id} item={s} t={t} onOpen={() => navigate({ name: "exercise", id: s.id })} />
                ))}
              </div>
            </section>
          )}
        </article>
      )}
    </main>
  );
}
