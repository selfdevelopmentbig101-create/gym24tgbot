# Gym24 API

Base path: `/api`. JSON in and out. Interactive docs while the API runs:
`http://localhost:8000/api/docs`.

## Authentication

Every endpoint except `GET /api/health` requires Telegram's signed launch data:

```
Authorization: tma <Telegram.WebApp.initData>
```

| Status | Meaning |
|---|---|
| 401 `unauthorized` | header missing, signature wrong, no user, or initData older than 24 h |
| 429 `rate_limited` | more than 120 requests/min for this user (or 20 failed logins/min per IP); see `Retry-After` |
| 422 | request body failed validation |
| 500 `internal_error` | logged on the server with the full traceback |

The client never sends a user ID; the server takes it from verified initData.

## Endpoints

✅ = built. The rest is the plan for later stages (paths may still be adjusted).

### Stage 0: system and account
| Method | Path | Purpose |
|---|---|---|
| ✅ GET | `/api/health` | `{"status": "ok"}`, no login (uptime checks) |
| ✅ GET | `/api/config` | app name, image credits, languages |
| ✅ GET | `/api/me` | first name (from Telegram), saved language, effective language, disclaimer accepted, profile complete |
| ✅ PATCH | `/api/me/language` | `{"language": "en" \| "ru" \| "uz"}`: same field as the bot's /language |
| ✅ GET | `/static/exercises/{file}` | exercise images, `Cache-Control: max-age=604800` |

### Stage 2: onboarding and targets
| Method | Path | Purpose |
|---|---|---|
| ✅ GET | `/api/config` → `profile_rules` | allowed ranges and choices (same limits as the bot), so the app validates as it goes |
| ✅ POST | `/api/me/disclaimer` | accept the health disclaimer (204). Same field as the bot's "I understand" |
| ✅ PUT | `/api/profile` | save all onboarding answers (+ optional `target_weight_kg`). Needs the disclaimer (409 `disclaimer_required`). Builds the workout plan; the first save also sends the main menu to the chat |
| ✅ GET | `/api/profile` | the saved answers (404 `no_profile` before onboarding) |
| ✅ PATCH | `/api/profile` | change some answers; `target_weight_kg: null` removes the goal weight. The plan is rebuilt only when equipment, level, days or injuries change |
| ✅ GET | `/api/targets` | calories, protein, carbs, fat, maintenance, surplus, weekly gain range, estimated goal date (+ earliest/latest), advice keys |

Rejected answers return `422 {"detail": {"field": "age", "error": "err_age"}}`; the app
translates the error key and jumps back to that question. A goal weight must be above
the current weight and isn't used for recomposition (`err_target_weight`).

Calculator (`services/nutrition.py`, shared with the bot): Mifflin-St Jeor BMR × activity
factor, goal surplus within safety limits, protein 1.6–2.2 g/kg, fat 25% of calories
(at least 0.6 g/kg), carbs = the rest. Goal date = kg to gain ÷ the healthy weekly
gain rate (middle of the range; earliest/latest use its ends).

### Stage 3: exercises
| Method | Path | Purpose |
|---|---|---|
| ✅ GET | `/api/exercises?q=&muscle=&equipment=&difficulty=&home=&fits=` | A–Z list. `q` matches the name or a muscle in any language; `muscle` matches primary **or** secondary; `fits=true` keeps only what fits your equipment, level and injuries. Also returns the chip/filter values |
| ✅ GET | `/api/exercises/{id}` | detail: image URLs (start + peak = animated, or one still), muscles, form tips, why it isn’t in your plans (`equipment` / `level` / `injury`), substitutes (curated first, ones that fit first) |
| ✅ GET | `/api/exercises/media-report` | admins only (`ADMIN_IDS`, else 403): which exercises have both frames, one image, or none |

"Fits" uses the same rules as plan generation (`services/exercises.py`), so the library and
plans never disagree. Images are read from `assets/exercises/` (`{id}-start` + `{id}-peak`, or
`{id}`), the same files the bot uses; URLs carry a version, so replacing a file shows up at once.

### Stage 4: plans and programs
| GET | `/api/programs?tab=current\|available\|created` | program lists |
| POST | `/api/programs` | create (name, weeks, workouts/week, goal) |
| GET / PATCH / DELETE | `/api/programs/{id}` | details, rename, delete |
| POST | `/api/programs/{id}/activate`, `/reset` | make current, reset to default |
| POST / PATCH / DELETE | `/api/programs/{id}/days[/{day}]` | add, rename, reorder, remove days |
| POST / PATCH / DELETE | `/api/days/{day}/exercises[/{item}]` | add (from library), sets/reps, reorder, remove |
| POST | `/api/days/{day}/exercises/{item}/substitute` | swap using substitute_ids, equipment and injuries |
| GET | `/api/calendar?month=YYYY-MM` | done / rest / missed markers |
| GET | `/api/energy?day={day}` | session and weekly-volume load with warnings |

### Stage 5: training
| GET | `/api/workouts/today` | today's split day with previous numbers |
| POST | `/api/workouts` | start a workout |
| GET | `/api/workouts/{id}` | live state |
| POST / PATCH / DELETE | `/api/workouts/{id}/sets[/{set}]` | log, edit, undo a set (kg, reps, RPE, warm-up) |
| PATCH | `/api/workouts/{id}/items/{index}` | note, superset group |
| POST | `/api/workouts/{id}/finish` | summary, PRs, overload suggestions, XP |

### Later stages
| 6 | `GET /api/me/level`, `GET /api/achievements`, `DELETE /api/me` (delete all data, with confirmation) |
| 7 | `GET /api/home` |
| 8 | `GET /api/stats/{consistency,volume,prs,e1rm}`, `POST/GET /api/body/{weight,measurements}` |
| 9 | `GET/PATCH /api/reminders` |
| 10 | `GET /api/foods?q=`, `GET /api/nutrition/day`, `POST/PATCH/DELETE /api/meals` |
| 11 | `GET /api/suggestions`, `POST /api/suggestions/{id}/{accept,dismiss}`, `POST /api/coach/messages` |
