# Data files

- `core_exercises.json`: the curated exercise list. Imported into the `exercises`
  table on bot startup or with `python import_exercises.py`. Every `substitute_id`
  is validated. Optional per-exercise field: `"form_tips"`.
- `injury_exclusions.json`: for each injury, the exercises to leave out of plans
  and substitutes. IDs are validated against `core_exercises.json`.
