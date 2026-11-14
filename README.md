# Muscle Gain Telegram Bot

A Telegram bot that helps people gain muscle: workout plans, logging,
progress tracking, calorie/protein targets and reminders.

**Status: Phase 1 (foundation and onboarding) is done.**

## Project structure

```
bot.py                 Entry point: wires everything together, starts polling
config.py              Settings from environment variables (.env)
database/
  base.py              Engine, sessions, SQLite foreign-key fix, table creation
  enums.py             Fixed choices (goal, sex, equipment, ...)
  models.py            Tables: users, profiles, exercises
services/              Business logic, no Telegram code (reusable by a Mini App or native app)
  nutrition.py         TDEE (Mifflin-St Jeor), surplus, protein, safety limits
  validation.py        Input parsing/validation (age, height, weight...)
  users.py             Create/read/update/delete users and profiles
handlers/              Telegram handlers
  common.py            /start, /help, /about, /cancel, disclaimer
  onboarding.py        10-step profile form (also used to edit one field)
  profile.py           /profile, /settings, editing, /deleteme
keyboards/profile.py   Inline keyboards and callback data
utils/
  texts.py             All user-facing texts (ready for multiple languages)
  formatting.py        Profile/targets → message text
  middlewares.py       DB session per update, rate limiting
  logging_setup.py     Console + rotating file logs (logs/bot.log)
data/                  Put core_exercises.json here (imported in Phase 2)
assets/exercises/      Exercise images ({id}-start.webp, {id}-peak.webp or {id}.webp)
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

The SQLite database (`gymbot.db`) is created automatically on first start.

## How to test

Automated tests (no Telegram connection needed):

```bash
pytest
```

They cover the calculator and its safety limits, input validation, the
database (including that `/deleteme` removes everything), and a full simulated
chat: onboarding, editing, `/deleteme`, stale buttons and HTML validity of every message.

Manual test in Telegram:

1. `/start` → accept the disclaimer → answer the 10 questions. Try invalid
   input (age `12`, height `500`, weight `abc`) and the **Back** button.
2. You should see your profile with daily calories and protein.
3. `/settings` → **Edit profile** → pick a field → change it. Targets update.
4. `/about` shows the credits line from `.env`.
5. `/deleteme` → confirm → `/profile` should say you have no profile.
6. Tap any button very quickly many times → you get a "Too fast" message.

## Notes

- **Moving to PostgreSQL:** `pip install asyncpg` and set
  `DATABASE_URL=postgresql+asyncpg://user:pass@host/db`. Before production we'll
  add Alembic migrations instead of auto-creating tables.
- **Half-finished onboarding** is kept in memory and lost on restart; switch to
  Redis storage for production.
- **Privacy:** only the profile answers are stored (no names or usernames).
  Every user table cascades from `users`, so `/deleteme` removes it all.
