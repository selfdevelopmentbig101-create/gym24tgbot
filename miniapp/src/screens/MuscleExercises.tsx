/* Train > All exercises > one muscle: every exercise whose primary muscle it is. */
import { useCallback, useEffect, useState } from "react";
import type { ExerciseList } from "../lib/api";
import { getMuscleExercises, trainErrorKey } from "../lib/trainApi";
import { goBack, navigate } from "../lib/router";
import { bindNativeBack } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ExerciseRow } from "../components/ExerciseRow";
import { BackHeader } from "./Splits";
import { ErrorCard, MuscleImage } from "./AllExercises";
import "./train.css";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function MuscleExercises({ muscle, t }: { muscle: string; t: T }) {
  const [data, setData] = useState<ExerciseList | null>(null);
  const [error, setError] = useState<TextKey | null>(null);
  const load = useCallback(() => {
    setError(null);
    setData(null);
    getMuscleExercises(muscle).then(setData).catch((e) => setError(trainErrorKey(e)));
  }, [muscle]);
  useEffect(load, [load]);
  const back = () => goBack({ name: "exercises" });
  useEffect(() => bindNativeBack(back), [muscle]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="train">
      <BackHeader title={t(("muscle_" + muscle) as TextKey)} t={t} onBack={back} />
      <div className="muscle-hero"><MuscleImage file={muscle + ".png"} /></div>
      {error && <ErrorCard t={t} error={error} onRetry={load} />}
      {!data && !error && <div className="spinner center-spinner" aria-label={t("loading")} />}
      {data && data.items.length === 0 && <div className="empty"><p>{t("muscle_none")}</p></div>}
      {data && data.items.length > 0 && (
        <div className="rows">
          {data.items.map((item) => (
            <ExerciseRow key={item.id} item={item} t={t} onOpen={() => navigate({ name: "exercise", id: item.id })} />
          ))}
        </div>
      )}
    </main>
  );
}
