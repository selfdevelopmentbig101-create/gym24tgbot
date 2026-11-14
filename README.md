# Muscle Gain Telegram Bot

A Telegram bot that helps people gain muscle: workout plans, logging,
progress tracking, calorie/protein targets and reminders.

**Status: Phase 1 (onboarding) and Phase 2 (exercise library and plan generator) are done.**

## Project structure

```
bot.py                 Entry point: imports exercises, wires everything together, starts polling
import_exercises.py    Validate/import data/core_exercises.json (also runs on bot startup)
config.py              Settings from environment variables (.env)
database/
  base.py              Engine, sessions, SQLite foreign-key fix, table creation
  enums.py             Fixed choices (goal, sex, equipment, ...)
  models.py            Tables: users, profiles, exercises, workout_plans, plan_days,
                       plan_exercises, media_cache
services/              Business logic, no Telegram code (reusable by a Mini App or native app)
  nutrition.py         TDEE (Mifflin-St Jeor), surplus, protein, safety limits
  validation.py        Input parsing/validation (age, height, weight...)
  users.py             Create/read/update/delete users and profiles
  exercise_import.py   JSON validation (incl. substitute_ids) and upsert into the DB
  exercise_media.py    Find start/peak/single images, build looping animations
  exercises.py         Equipment/level/injury rules, substitutes, library queries
  plan_generator.py    Split + day templates -> weekly plan (pure logic)
  plans.py             Save/load/regenerate plans, swap substitutes
handlers/              Telegram handlers
  common.py            /start, /help, /about, /cancel, disclaimer
  onboarding.py        10-step profile form (also used to edit one field)
  profile.py           /profile, /settings, editing, /deleteme
  plan.py              /plan overview, open a day, regenerate
  library.py           /exercises: browse by muscle group
  cards.py             Exercise cards: image/animation, details, Next/Substitute/Log set
keyboards/             Inline keyboards and callback data
utils/
  texts.py             All user-facing texts (ready for multiple languages)
  formatting.py        Profile/targets -> message text
  middlewares.py       DB session per update, rate limiting
  logging_setup.py     Console + rotating file logs (logs/bot.log)
data/
  core_exercises.json     The 87 curated exercises (plans use only these)
  injury_exclusions.json  Exercises skipped for each injury (edit freely)
assets/exercises/      Exercise images (see below)
tests/                 Unit, database and end-to-end tests
```

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env
```

1. In Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot`, and copy the token.
2. Put it in `.env` as `BOT_TOKEN=...`.
3. Set `EXERCISE_IMAGE_ATTRIBUTION` to the exact credits text RepDB requires.

Run the bot:

```bash
python bot.py
```

The SQLite database (`gymbot.db`) is created automatically, and the exercises
are imported from `data/core_exercises.json` on every start (safe to repeat).

> **Upgrading from Phase 1:** delete `gymbot.db` once. New tables and columns
> were added, and there are no database migrations yet (planned before launch).

### Exercise images

Put the RepDB images in `assets/exercises/`, named after the exercise `id`:

- `{id}-start.webp` + `{id}-peak.webp` -> shown as a looping animation
- `{id}.webp` (e.g. `plank-main.webp`) -> used when start/peak are missing

The bot builds a short looping GIF (hold start, crossfade to peak, hold, fade
back). Telegram turns it into a looping video, and the bot remembers Telegram's
file ID, so each animation is uploaded only once. Exercises without images
show a text card. To pre-build all animations and list missing images:

```bash
python import_exercises.py --check --build-media
```

### Form tips

Add a `"form_tips": "..."` field to any exercise in `core_exercises.json` and
restart the bot (or run `python import_exercises.py`). Exercises without the
field keep whatever tips are already in the database.

## How to test

Automated tests (no Telegram connection needed):

```bash
pytest
```

They cover the calculator, input validation, the JSON import and its error
messages, image fallback and animation building, the plan generator for every
combination of equipment, experience, injuries and training days, and full
simulated chats (onboarding, editing, plans, cards, substitutes, the library,
media caching, `/deleteme`).

Manual test in Telegram:

1. `/start` -> accept the disclaimer -> answer the 10 questions. The final
   message says your plan is ready.
2. `/plan` -> see the week. Tap a day -> exercise card with sets, reps and rest.
   **Next** moves through the day; **Substitute** swaps the exercise in your
   plan for one that fits your equipment and injuries.
3. `/exercises` -> pick a muscle group -> browse with **Next** / **Substitute**.
4. `/settings` -> **Edit profile** -> **Equipment** -> **Bodyweight only**.
   Your plan is rebuilt with bodyweight exercises.
5. `/deleteme` removes your profile and plan.

## How plans are built

- Split by training days: 2-3 full body, 4 upper/lower, 5 upper/lower + push/pull/legs,
  6 push/pull/legs twice.
- Equipment: full gym = everything; home with dumbbells = home-friendly dumbbell
  and bodyweight exercises; bodyweight only = home-friendly bodyweight exercises.
- Level: beginners get beginner exercises first (intermediate only if nothing
  else fits); advanced exercises only for advanced lifters.
- Injuries: exercises in `data/injury_exclusions.json` are never planned or
  offered as substitutes.
- Variety: same-template days (Upper A / Upper B) use different exercises, and
  near-duplicates (e.g. pull-ups + chin-ups) aren't put on the same day.
- Sets/reps: compounds 3x8-12 (beginners) or 3x6-10 (4 sets for advanced),
  isolation 3x10-15, plank 30-45 s.

## Notes

- **Moving to PostgreSQL:** `pip install asyncpg` and set
  `DATABASE_URL=postgresql+asyncpg://user:pass@host/db`. Before production we'll
  add Alembic migrations instead of auto-creating tables.
- **Half-finished onboarding** is kept in memory and lost on restart; switch to
  Redis storage for production.
- **Privacy:** only the profile answers and the generated plan are stored (no
  names or usernames). Every user table cascades from `users`, so `/deleteme`
  removes it all.
