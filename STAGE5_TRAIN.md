# Stage 5: Train tab (workout-day screen and live logger)

This zip **includes Stage 4B** (the Plan tab), so apply only this one: unzip into the
project root (the folder with bot.py) and replace files when asked.

## What's new
| Area | Files |
|---|---|
| Database | `migrations/versions/0006_set_rpe_warmup.py` (NEW): `set_logs.rpe`, `set_logs.warmup`. Notes and superset groups are stored in the workout's items. `database/models.py` updated |
| Logic (shared with the bot) | `services/workouts.py`: warm-up sets, RPE, edit/delete any set, notes, superset groups. `services/records.py`: warm-ups never count for PRs |
| Train API | `services/train.py`, `api/routes/train.py`, `api/schemas_train.py` (NEW), `api/main.py` (one line) |
| Tests | `tests/test_api_train.py` (NEW) |
| Mini App | `screens/TrainDay.tsx`, `screens/Logger.tsx`, `screens/train.css`, `lib/trainApi.ts`, `lib/trainText.ts`, `i18n/train.*.json` (NEW); router, tab bar, App, texts index updated |

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /api/train | workout in progress + every program day with last time's numbers |
| POST | /api/workouts | start a day (`{"day_index": 0}`; 409 `workout_active` unless `"force": true`) |
| GET | /api/workouts/{id} | live state |
| POST | /api/workouts/{id}/sets | log a set (`index, weight_kg, reps, rpe?, warmup?`); answers with PR info |
| PATCH / DELETE | /api/workouts/{id}/sets/{set_id} | fix / remove a set |
| PATCH | /api/workouts/{id}/items/{index} | `note`, superset `group` (A–D) → labels A1, A2... |
| POST | /api/workouts/{id}/items/{index}/substitute | swap before the first set |
| POST | /api/workouts/{id}/finish | summary: time, sets, volume, PRs, next-time suggestions |

## Test
    pytest
    cd miniapp && npm run build && cd ..
    python -m uvicorn api.main:app --port 8000 --reload     # + tunnel + bot as before

In Telegram (Gym24 → Train):
1. The next day is preselected, with last time's numbers. Tap **Start workout**.
2. The first set is pre-filled: tap ✓ (1 tap). The rest timer appears: try **+15 s**, **Pause**, **Skip**.
   When it ends the phone vibrates and a banner shows.
3. **+2.5 kg**, **Same as last time**, tap **RPE** to cycle 6–10, toggle **Warm-up** and log one:
   the energy bar doesn't move and it shows as "W".
4. Tap a logged set to fix it or delete it (tap twice).
5. Put two exercises in superset **A**: they show A1/A2 and you jump between them without rest.
6. Write a note, leave the field: it's saved. **Swap exercise** works before the first set.
7. Next workout of the same day: last time's sets show; beat them for a 🏆 PR banner.
8. **Finish** (tap twice): summary with PRs and "next time" suggestions. Back in Train, nothing is in progress.
9. The bot's /workout sees the same workout (start in the app, continue in the chat, or the other way round).

Known limits: the rest timer lives in the app (the bot's chat timer still works for chat
logging). A "rest over" chat message when the app is closed comes with reminders (Stage 9).

## Commit
    git add -A
    git commit -m "Stage 4B + 5: Plan tab and Train tab (live logger)"
    git push origin main
