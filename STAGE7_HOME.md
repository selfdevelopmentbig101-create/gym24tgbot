# Stage 7: Home tab

This zip **includes Stages 4B, 5 and 6** (replace files when asked). Unzip into the
project root (the folder with bot.py). Stage 3 fixes and Stage 4A must already be applied.

## What's new
Home (the first tab) now shows, top to bottom:
1. **Greeting** by time of day in your time zone ("Good evening, Name") and today's date.
2. **Character card** (Stage 6): level, XP bar, streak, energy, mood. Tap → Profile.
3. **Next workout**: day name, exercises, minutes, muscles, first exercises, **Start workout**
   (starts it and opens the logger) and **See the day**. During a workout: progress + **Continue**.
4. **This week** (Mon–Sun): a dot per day (✓ = trained, ring = today), workouts vs your goal,
   "N more to hit your goal" or "Weekly goal met 🔥", sets, kg lifted, records, minutes.
5. **Today**: calories and protein vs your targets (food is still logged in the chat with /food
   until the nutrition stage), plus **Your targets** (the full calories/macros/goal-date screen).
6. **Body weight**: latest weigh-in (or the one from your profile).
7. **Shortcuts**: Exercises, Plan, Programs.

Right after onboarding you still see "Your plan is ready" once, with **Go to Home**.
The language picker moved to Profile → Settings. Numbers refresh when you come back to the app.

## Files
| Area | Files |
|---|---|
| API | `services/home.py`, `api/routes/home.py` (NEW): `GET /api/home`; `api/main.py` |
| Tests | `tests/test_home.py` (NEW) |
| Mini App | `screens/Home.tsx`, `screens/home.css`, `screens/Targets.tsx`, `lib/homeApi.ts`, `i18n/home.en.json`, `home.ru.json` (NEW); `App.tsx`, `lib/router.ts` (`/targets`), `i18n/index.ts`, `plan.css` / `profile.css` (card titles) |

No database changes.

## Test
    pytest
    cd miniapp && npm run build && cd ..
    python -m uvicorn api.main:app --port 8000 --reload
Close the Mini App completely and open it again, then:
1. Home shows the greeting, the character, the next workout and this week.
2. **Start workout** opens the logger. Go back to Home: the card says "Workout in progress" → **Continue**.
3. Finish the workout: today's dot gets a ✓, sets/kg/minutes go up, the character celebrates.
4. Log food in the chat (`/food 650 40`), come back to the app: the calories and protein bars move.
5. **Your targets** opens the macros screen; Back returns to Home.

## Commit
    git add -A
    git commit -m "Stage 7: Home tab (greeting, next workout, this week, today)"
    git push origin main
