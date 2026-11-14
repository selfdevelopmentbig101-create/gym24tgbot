# Muscle Gain Telegram Bot

A Telegram bot that helps people gain muscle: workout plans, logging,
progress tracking, calorie/protein targets and reminders.

**Status: Phases 1–5 are done, plus the first part of Phase 6 (streaks and achievements, auto-adjusting plans and calories, admin commands).**

## Project structure

```
bot.py                 Entry point: imports exercises, wires everything together, starts polling
import_exercises.py    Validate/import data/core_exercises.json (also runs on bot startup)
config.py              Settings from environment variables (.env)
database/
  base.py              Engine, sessions, SQLite foreign-key fix, table creation
  enums.py             Fixed choices (goal, sex, equipment, ...)
  models.py            Tables: users, profiles, exercises, workout_plans, plan_days,
                       plan_exercises, media_cache, workout_sessions, set_logs,
                       body_weight_logs, measurement_logs, reminder_settings, meal_logs,
                       achievements
services/              Business logic, no Telegram code (reusable by a Mini App or native app)
  nutrition.py         TDEE (Mifflin-St Jeor), surplus, protein, safety limits
  validation.py        Input parsing/validation (age, height, weight...)
  users.py             Create/read/update/delete users and profiles
  exercise_import.py   JSON validation (incl. substitute_ids) and upsert into the DB
  exercise_media.py    Find start/peak/single images, build looping animations
  exercises.py         Equipment/level/injury rules, substitutes, library queries
  plan_generator.py    Split + day templates -> weekly plan (pure logic)
  plans.py             Save/load/regenerate plans, swap substitutes
  workouts.py          Workout sessions: start, log/undo sets, swap, history, summary
  progression.py       Progressive overload suggestions (pure logic)
  rest_timer.py        Per-user rest timers (asyncio)
  records.py           PRs and estimated 1RM (Epley)
  body.py              Body weight (with weekly trend) and measurements
  charts.py            matplotlib charts -> PNG
  reminders.py         Reminder settings, time zones, "trained today?" checks
  scheduler.py         APScheduler jobs built from reminder settings
  foods.py             Quick-log food list (data/foods.json), diet filter
  meals.py             Meal logging, daily totals, weekly average
  achievements.py      Weekly and protein streaks, achievements
  adjust.py            Deload and calorie suggestions (with safety limits)
handlers/              Telegram handlers
  common.py            /start, /help, /about, /cancel, disclaimer
  onboarding.py        10-step profile form (also used to edit one field)
  profile.py           /profile, /settings, editing, /deleteme
  plan.py              /plan overview, open a day, regenerate
  library.py           /exercises: browse by muscle group
  cards.py             Exercise cards: image/animation, details, Next/Substitute/Log set
  workout.py           /workout: logger card, quick buttons, typed sets, rest timer, summary
  progress.py          /progress, /weight, /measure: summary, PRs, charts
  reminders.py         /reminders settings and the reminder/nudge messages
  food.py              /food: quick logging, manual entry, daily summary
  extras.py            /achievements and Accept/Not now for suggestions
  admin.py             /admin stats and /broadcast (ADMIN_IDS only)
keyboards/             Inline keyboards and callback data
utils/
  texts.py             All user-facing texts (ready for multiple languages)
  formatting.py        Profile/targets -> message text
  middlewares.py       DB session per update, rate limiting
  logging_setup.py     Console + rotating file logs (logs/bot.log)
data/
  core_exercises.json     The 87 curated exercises (plans use only these)
  injury_exclusions.json  Exercises skipped for each injury (edit freely)
  foods.json              Quick-log foods with kcal/protein per serving (edit freely)
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

### Windows: "DLL load failed ... blocked by Application Control policy"

Windows 11 **Smart App Control** can block the native DLLs of Pillow and
matplotlib. The bot still starts and works; it just shows exercise cards as text
and replies "charts unavailable". To get images and charts back, pick one:

- Run the bot in **WSL** (`wsl --install`, then follow the setup above inside
  Ubuntu), or on a Linux server/VPS. This is the recommended way to host a bot anyway.
- Or turn Smart App Control off: Windows Security -> App & browser control ->
  Smart App Control settings -> Off. Note that Windows can't turn it back on
  without a reset, so prefer WSL if you want to keep it.

> **Upgrading from an earlier phase:** delete `gymbot.db` once. New tables and
> columns were added, and there are no database migrations yet (planned before launch).

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
media caching, workout logging with rest timers, progress, charts, reminders and
missed-workout nudges, food logging, `/deleteme`), plus the overload, PR, trend,
scheduling and food-list rules.

Manual test in Telegram:

1. `/start` -> accept the disclaimer -> answer the 10 questions. The final
   message says your plan is ready.
2. `/plan` -> see the week. Tap a day -> exercise card with sets, reps and rest.
   **Next** moves through the day; **Substitute** swaps the exercise in your
   plan for one that fits your equipment and injuries.
3. `/exercises` -> pick a muscle group -> browse with **Next** / **Substitute**.
4. `/settings` -> **Edit profile** -> **Equipment** -> **Bodyweight only**.
   Your plan is rebuilt with bodyweight exercises.
5. `/workout` -> **Start workout**. The card shows the target, last time's
   numbers and a suggestion. Tap **✅ Log ...** (1 tap), or adjust with
   **+2.5 kg / +1 rep** first (2 taps), or type `60x10`. A rest timer starts and
   you get a message when it's over; tap its button to log the next set.
   Try **↩️ Undo**, **🔄 Swap** (machine taken), **⏭ Next** and **🏁 Finish**.
6. Next time you do that day, the card shows last time's sets, a
   **🔁 Same as last time** button, and the Log button is pre-filled with the
   suggested weight (e.g. +2.5 kg after hitting the top of the rep range).
7. `/weight` -> adjust with ±0.1/±0.5 and tap **Log** (or `/weight 75.4`).
   Your calorie targets follow your latest weight.
8. `/measure` -> pick a body part -> type the value (later: ±buttons from the last value).
9. `/progress` -> weight, weekly trend vs your goal, workouts, best lifts.
   Charts: weight, strength (estimated 1RM per exercise), volume and
   measurements, each with **Week / Month** buttons. **All PRs** lists records.
10. `/reminders` -> tap the button showing your current time (sets the time
    zone; or type e.g. `Europe/Berlin`). Defaults: workout reminders on your
    training days at 18:00, weekly weigh-in Monday 08:00, missed-workout nudge
    at 21:00. Everything is adjustable with buttons.
11. `/food` -> tap a category -> tap a food (logs 1 serving; adjust ×½–×2 after).
    Foods you logged recently appear at the top (2 taps). **✍️ Manual** or
    `/food 650 40` logs any meal by calories and protein. The summary shows
    calories and protein vs your targets, what's left, a 7-day average and
    protein ideas that fit your diet. **◀️ Previous day** browses the last week.
12. `/deleteme` removes your profile, plan, workouts, weigh-ins, measurements,
    meals and reminders.

## Logging and progression

- The draft (exercise, weight, reps) is stored with the workout, so it survives
  other menus and bot restarts. A workout left open for 12+ hours is closed
  automatically; a workout with no sets is discarded.
- Double progression: add reps until every planned set reaches the top of the
  range, then add 2.5 kg and restart at the bottom. Missing the bottom of the
  range two workouts in a row suggests dropping ~10%. Bodyweight exercises
  suggest adding load or a harder variation; timed ones add 5 s (max 120 s).
- Rest timers live in memory: a restart during a rest period loses that one notification.

## Progress and reminders

- **PRs:** a set is a PR when its estimated 1RM (Epley, sets of 1–12 reps)
  beats your previous best for that exercise. Your first-ever set of an
  exercise isn't counted, so new users don't get a PR on everything.
- **Weight trend:** average of the last 7 days minus the 7 days before,
  compared with your goal's healthy weekly gain. If you're off target, it
  suggests about ±150 kcal a day, and only after 2–3 weeks.
- **Reminders** are rebuilt from the database on every start, so a restart
  never loses them. They're skipped if you've already trained or weighed in
  that day.
- **Missed-workout nudge:** on a training day with no workout by the nudge
  time, it offers "tomorrow", "in 2 days" or "skip". After 3 misses in a row it
  also offers a lighter schedule (one fewer day per week), which updates your
  plan and reminders.
- **Time zones:** the 1-tap buttons set a fixed UTC offset, so re-pick it after
  daylight saving changes. Typing a name like `Europe/Berlin` adjusts automatically.

## Nutrition

- **Food list:** `data/foods.json` has about 45 common foods with per-serving calories
  and protein (approximate, rounded from USDA FoodData Central). Each food has
  a diet level (vegan / vegetarian / pescatarian / meat) and users only see
  foods that fit their diet preference. Add or edit foods freely; the file is
  checked on startup (e.g. protein can't exceed total calories).
- **Days** follow the user's time zone from `/reminders` (UTC until set).
  Entries store their own totals, so editing the food list never changes history.
- **Evening summary:** at 21:30 by default (change or turn off in `/reminders`),
  sent only on days you logged food. It shows what's left and a gentle tip
  (e.g. "a shake closes the gap"). It never suggests skipping meals, and when you go
  over, it points to the weekly average instead of a single day.

## Streaks, achievements and auto-adjust

- **Weekly streak:** weeks in a row (Monday to Sunday) with at least your
  planned number of workouts. Rest days never break it, and the current week
  doesn't break it until it's over. There's also a protein streak (days in a
  row at your protein target).
- **Achievements** (`/achievements`, 18 of them): workout counts, streaks, PRs,
  total weight lifted, protein streaks, weigh-ins. Each unlock is announced
  once, and earned achievements stay even if a streak later breaks.
- **Deload suggestion:** when 2+ exercises haven't improved their estimated
  1RM over the last 3 workouts, after the workout summary the bot offers a
  lighter week: about 60% of the sets at about 90% of the weight. Nothing
  changes unless you tap **Start deload week**, and the normal plan returns
  after 7 days. It isn't offered again for 3 weeks after a "Not now", or 4
  weeks after a deload.
- **Calorie suggestion:** if weight gain was too slow (or too fast) for your
  goal two weeks in a row, `/progress` and weigh-ins offer +150 (or -150)
  kcal a day. Total changes stay between -300 and +450 kcal, the "never below
  resting needs" floor still applies, there's a 2-week cooldown, and changing
  your goal resets them.
- **Admin:** put your Telegram user ID in `ADMIN_IDS` in `.env`. `/admin`
  shows users, new and active users, and workouts in the last 7 days.
  `/broadcast your text` shows a preview, then **Send to everyone** sends at
  about 20 messages per second and reports how many were sent and how many
  users blocked the bot. Non-admins get no reply to these commands.

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
