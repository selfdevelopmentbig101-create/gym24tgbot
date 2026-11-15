# Stage 4, part A: Plan backend (programs, split editor, calendar, energy)

Apply **gym24-stage3-fixes.zip first**, then unzip this file into the project root
(the folder with bot.py). NEW files are added, the others replace your version.

| File | What changed |
|---|---|
| database/models.py | `Program` table (NEW), `PlanDay.title` (day names from the editor) |
| migrations/versions/0005_programs.py | NEW. Creates `programs`, adds `plan_days.title` (runs by itself on start) |
| services/energy_config.py | NEW. All energy/volume limits in one place (6-8 exercises, 15-25 hard sets per session, 10-20 weekly sets per muscle) |
| services/energy.py | NEW. Energy bar, weekly volume per muscle, warnings (never blocks) |
| services/program_rules.py | NEW. Goals (strength / hypertrophy / endurance), built-in programs, limits, minutes estimate |
| services/programs.py | NEW. Programs, split editor, calendar, program card |
| services/plans.py | The plan is now the CURRENT program's days; regenerating keeps the program's goal and days |
| api/schemas_plan.py | NEW. Request bodies |
| api/routes/plan.py | NEW. The endpoints below |
| api/main.py | registers the new routes (one line) |
| tests/test_energy_rules.py, tests/test_api_plan.py | NEW tests |

## Why the design looks like this (no rewrite)

The bot, reminders and the workout logger all read `workout_plans` / `plan_days`.
So the **current program's days stay exactly there**. Other programs keep a copy of
their days in `programs.days_snapshot`; making a program current swaps them in.
Every existing user gets a "default" program around their current plan automatically.

Notes:
- The editor works on the current program. Saved programs can be viewed, renamed,
  reset, deleted, or made current (then edited).
- A changed profile (equipment, level, injuries) still rebuilds the plan, now for the
  current program's goal and number of days. A default program follows the profile's days.
- Day names you give in the editor show in the Mini App; the bot still shows the
  default names (I'll update the bot side in Stage 4B).
- "Created" tab = every saved program (yours, and ones you switched away from).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /api/plan | current program card (week x of y, % done, frequency, upcoming workout, details) + days with exercises and energy + weekly volume per muscle |
| POST | /api/plan/days | add a day (filled with default exercises) |
| PATCH / DELETE | /api/plan/days/{day_id} | rename / move, remove (not the last day) |
| POST | /api/plan/days/{day_id}/exercises | add from the library (409 already_in_day, too_many_exercises) |
| PATCH / DELETE | /api/plan/exercises/{entry_id} | sets, reps, rest, position / remove |
| POST | /api/plan/exercises/{entry_id}/substitute | swap (409 no_substitute) |
| GET | /api/programs?tab=current\|available\|created | program lists |
| POST | /api/programs | create (name, weeks 4-16, workouts/week 2-6, goal) |
| POST | /api/programs/templates/{key}/start | start a built-in program |
| GET / PATCH / DELETE | /api/programs/{id} | details, rename, delete (409 if current) |
| POST | /api/programs/{id}/activate, /reset | make current, back to default days |
| GET | /api/calendar?month=YYYY-MM | done / planned / missed / rest per day |
| GET | /api/energy?day={day_id} | session load + weekly volume with warnings |

Editor changes answer with the whole updated plan. Errors return a code in `detail`
(e.g. `last_day`, `bad_reps`) that the Mini App will translate in Stage 4B.

## Test

    pytest                       # all tests, including tests/test_api_plan.py

Then start the API and open http://localhost:8000/api/docs : the new "plan" section
lists every endpoint (calling them needs Telegram login, so use the tests or the
Mini App in Stage 4B). The bot keeps working as before: /plan shows your days.

## Commit

    git add -A
    git commit -m "Stage 4A: programs, split editor API, calendar, energy system"
    git push origin phase-1-5
