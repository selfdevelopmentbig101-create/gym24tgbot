# Stage 6: levels, XP, character, achievements and the Profile tab

This zip **includes Stages 4B and 5**. If you already applied them, just replace files.
Unzip into the project root (the folder with bot.py).

## How XP and levels work (all numbers in `services/xp_config.py`)
| Rule | Default |
|---|---|
| Levels | Rookie 0 · Beginner 600 · Regular 1800 · Advanced 4500 · Pro 9000 XP |
| Starting level (onboarding experience) | beginner → Rookie, intermediate → Regular, advanced → Advanced |
| Finished workout | +60 XP |
| New PR | +30 XP |
| Week with your planned number of workouts | +80 XP |
| Energy back to 100% | 24 h after a workout |
| Celebrating | 3 h after a workout (12 h if it had a PR) |
| Tired | energy under the LOW_ENERGY value in `energy_config.py` |

XP is calculated from what's already logged (workouts, PRs), so no new table and no migration.
Workouts logged in the chat count too.

## Files
| Area | Files |
|---|---|
| Rules + logic | `services/xp_config.py`, `services/levels.py` (NEW); `services/train.py` (XP in the finish summary) |
| API | `api/routes/level.py` (NEW): `GET /api/me/level`, `GET /api/achievements`, `DELETE /api/me` (body `{"confirm": "DELETE"}`); `api/main.py` |
| Tests | `tests/test_levels.py` (NEW) |
| Character | `components/Character.tsx` (SVG: build + outfit per level; rested / tired / celebrating), `Character.css` |
| Home | `components/CharacterCard.tsx`: level, XP bar, streak, energy; tap → Profile |
| Profile tab | `screens/Profile.tsx`, `screens/ProfileEdit.tsx`, `screens/profile.css`, `components/ProfileIcons.tsx` |
| Celebration | `components/Celebration.tsx`: confetti on a new level or achievement (once per device) |
| Texts | `i18n/profile.en.json`, `profile.ru.json` (NEW), `i18n/index.ts` |
| Wiring | router (`/profile`, `/profile/edit`), tab bar (Profile tab), App, Logger summary (+XP) |

## Test
    pytest
    cd miniapp && npm run build && cd ..
    python -m uvicorn api.main:app --port 8000 --reload     # + tunnel + bot as before

In Telegram (open Gym24):
1. **Home**: the character card at the top shows level, XP bar, "XP to next level", streak, energy. Tap it → Profile.
2. **Profile**: large character, the level steps, stats, how XP is earned, achievements (locked ones in grey with progress).
3. Do a workout in **Train** and finish: the summary shows **+60 XP** (more with PRs). Back on Home the character
   celebrates (arms up). During a hard workout, the energy drops and it looks tired.
4. When you reach a new level or unlock an achievement, confetti appears once.
5. **Edit profile**: change e.g. workouts per week → Save → "Your plan was rebuilt".
6. Language pills switch the whole app. Reminders: still set up in the chat (/reminders) until Stage 9.
7. **Delete my data** → confirm → the app restarts at onboarding (everything is gone, like /deleteme).
   Use a test account or be ready to onboard again.

## Commit
    git add -A
    git commit -m "Stage 6: levels, XP, character, achievements, Profile tab"
    git push origin main
