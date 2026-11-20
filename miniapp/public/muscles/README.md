# Muscle anatomy cards

Images for Train > All exercises > Exercises by muscle and the split exercise
picker. One PNG per `muscle_group` key in `data/core_exercises.json`, saved here
as `miniapp/public/muscles/<key>.png` (served at `/muscles/<key>.png`).

Missing files fall back to the dumbbell placeholder in the app.

## Format

- **600 × 600 px** square PNG, sRGB. Transparent background (the card provides
  the dark sunken background), or a flat very dark background that matches it.
- Front-facing, neutral standing body, same camera/scale for all ten images.
- Body in grey; the target muscle in the app's orange (`#f2a33a` works well).
- No text, labels, arrows or borders. Keep the muscle readable at ~140 px.

## Files (10)

| File | Target muscle |
|---|---|
| `chest.png` | Pectorals |
| `back.png` | Lats / upper back |
| `shoulders.png` | Deltoids |
| `biceps.png` | Biceps |
| `triceps.png` | Triceps |
| `core.png` | Abdominals / obliques |
| `quads.png` | Quadriceps |
| `hamstrings.png` | Hamstrings |
| `glutes.png` | Glutes |
| `calves.png` | Calves |

The shown/hidden muscle list is generated from the exercise data, so the file
names must match the keys above exactly.