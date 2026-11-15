/* One exercise in a list: thumbnail (or muscle placeholder), name, muscle · equipment, level. */
import type { ExerciseItem } from "../lib/api";
import { haptic } from "../lib/telegram";
import type { TextKey } from "../i18n";
import { ChevronRight, Dumbbell } from "./Icons";

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

export function Thumb({ item }: { item: Pick<ExerciseItem, "image" | "muscle_group"> }) {
  if (item.image) {
    return <img className="thumb" src={item.image} alt="" loading="lazy" decoding="async" width={56} height={56} />;
  }
  return (
    <span className={"thumb thumb-empty thumb-" + item.muscle_group} aria-hidden>
      <Dumbbell />
    </span>
  );
}
