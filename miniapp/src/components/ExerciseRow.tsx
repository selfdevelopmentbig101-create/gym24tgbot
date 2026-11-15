/* One exercise in a list: thumbnail (or muscle placeholder), name, muscle · equipment, level. */
import type { ExerciseItem } from "../lib/api";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ChevronRight } from "./Icons";
import { ExerciseImage } from "./ExerciseImage";

type T = (key: TextKey, vars?: Record<string, string | number>) => string;

export function ExerciseRow({ item, t, onOpen }: { item: ExerciseItem; t: T; onOpen: () => void }) {
  return (
    <button type="button" className={"exercise-row" + (item.fits === false ? " exercise-row-dim" : "")}
            onClick={() => { haptic.tap(); onOpen(); }}>
      <Thumb item={item} />
      <span className="exercise-text">
        <span className="exercise-name">{item.name}</span>
        <span className="exercise-meta">
          {t(("muscle_" + item.muscle_group) as TextKey)} · {t(("equip_" + item.equipment.replace(/ /g, "_")) as TextKey)}
        </span>
        <span className="exercise-tags">
          <span className={"level level-" + item.difficulty}>{t(("level_" + item.difficulty) as TextKey)}</span>
          {item.fits === false && <span className="tag-muted">{t("not_in_plan")}</span>}
        </span>
      </span>
      <ChevronRight />
    </button>
  );
}

/** Small list picture: a still, lazy-loaded, with a skeleton (no animation in lists). */
export function Thumb({ item }: { item: Pick<ExerciseItem, "image" | "muscle_group"> }) {
  return <ExerciseImage still={item.image} muscle={item.muscle_group} size="thumb" />;
}
