# Data files

- `core_exercises.json`: the curated exercise list. Imported into the `exercises`
  table on bot startup or with `python import_exercises.py`. Every `substitute_id`
  is validated. Optional per-exercise field: `"form_tips"`.
- `secondary_muscles.json`: for each exercise, the other muscle groups it works
  (the primary one is `muscle_group`). Used by the Mini App library. Validated at import.
- `injury_exclusions.json`: for each injury, the exercises to leave out of plans
  and substitutes. IDs are validated against `core_exercises.json`.
