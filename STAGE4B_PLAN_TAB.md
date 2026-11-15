# Stage 4, part B: Plan tab in the Mini App

Unzip into the project root (the folder with bot.py). NEW files are added, the
others replace your version. Needs Stage 4A (already on `main`).

| File | What changed |
|---|---|
| miniapp/src/screens/Plan.tsx | NEW. Program card (week x of y, % done, frequency, upcoming workout), month calendar, details, weekly volume |
| miniapp/src/screens/SplitEditor.tsx | NEW. Days as chips, rename / move / delete / add a day, energy bar + warning, sets/reps/rest sheet, reorder, substitute, remove, add from library search, reset to default |
| miniapp/src/screens/Programs.tsx | NEW. Tabs Current / Available / Created, start, make current, delete |
| miniapp/src/screens/ProgramNew.tsx | NEW. Name, weeks, workouts per week, goal (Strength / Hypertrophy / Endurance) |
| miniapp/src/screens/plan.css | NEW. Styles (tokens only) |
| miniapp/src/components/EnergyBar.tsx, VolumeList.tsx, MonthCalendar.tsx, Stepper.tsx, PlanIcons.tsx | NEW |
| miniapp/src/lib/planApi.ts, planText.ts | NEW. API calls and text helpers |
| miniapp/src/lib/router.ts | routes /plan, /plan/edit[/day], /plan/programs[/new] |
| miniapp/src/components/TabBar.tsx | Plan tab added (Home, Plan, Train) |
| miniapp/src/App.tsx | shows the new screens |
| miniapp/src/i18n/index.ts | merges plan.en.json / plan.ru.json |
| miniapp/src/i18n/plan.en.json, plan.ru.json | NEW. 129 texts each (Uzbek falls back to English for now) |
| handlers/plan.py | bot: shows day names from the editor, and an "Open Gym24" button to the Plan tab |

## Build and test

    cd miniapp
    npm run build        # type check + build; fix-ups go here if anything fails
    cd ..
    pytest               # backend unchanged since 4A, should still pass
    python -m uvicorn api.main:app --port 8000 --reload

Then open the bot (tunnel + MINIAPP_URL as before) and:

1. Tap 📅 Plan in the bot: the overview now ends with an **Open Gym24** button. It opens the Plan tab.
2. Plan tab: program card, calendar (today outlined, training days ringed in green), details, weekly volume.
3. **Edit split**: tap a day chip, rename it (pencil), move it (arrows), open an exercise to change
   sets/reps/rest, reorder with the up/down arrows, swap, remove (tap twice). Add 4+ exercises to a
   day: the energy bar turns orange/red and the warning appears. Nothing is blocked.
4. **Add exercise**: search "biceps": chin-ups appear too (secondary muscle).
5. **All programs**: Available → Start "Push / Pull / Legs 6×". The Plan tab shows it.
   Created → your old program is there; **Make current** brings it back with your edits.
6. Create a program (+): name, weeks, days, goal, Start it now.
7. Back in the bot, /plan shows your renamed days.

## Commit

    git add -A
    git commit -m "Stage 4B: Plan tab, split editor, programs, energy bar"
    git push origin main
