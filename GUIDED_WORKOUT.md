# Guided workout (countdown, exercise screen, rest, summary)

Opened by **Start workout** / **Continue workout** on the Train tab and by the Start / Continue
buttons on Home. Route: `/workout/go`. The detailed logger (`/workout/live`: warm-ups, RPE, notes,
supersets, editing sets) is unchanged and reachable from the **Details** button on the guided screen.

## Flow
1. **Countdown** 3, 2, 1, GO! (scale + fade, light haptic tap on each step).
2. **Exercise**: looping picture on top (start/peak frames crossfade; a single image is shown as a still;
   placeholder when missing; RepDB attribution from `GET /api/config` under the picture). Below: name,
   target muscle, "Set 2 of 4", target reps, big -/+ for reps (seconds for holds), weight (-/+ 2.5 kg).
   The big button saves the set (`POST /api/workouts/{id}/sets`); on the last set it reads
   "Finish exercise". "Finish exercise now" ends the exercise early after saving the current set.
3. **Exercise completed**: success animation, rest choices 1:00 / **1:30 (preselected)** / 2:00 / Skip rest.
4. **Rest**: big timer, +30 s, Start now. At 0 it vibrates (haptic + `navigator.vibrate`) and opens the
   next exercise by itself.
5. **Last exercise**: no rest. The workout is finished (`POST /api/workouts/{id}/finish`) and the
   summary shows total time, exercises done, total sets and reps (plus volume, XP and records).

The segmented progress bar (done = filled, current = highlighted, upcoming = muted, "Exercise 2 of 6",
previous/next names) stays on top in every phase except the countdown and the summary. It scrolls
sideways when there are many exercises.

## Resume, Back, wake lock
* Sets are saved on the server one by one, so a workout survives closing the Mini App. The screen state
  (current exercise, rest end time) is kept in `localStorage` (`gym24.guided.<telegram id>`); reopening
  continues there, or at the next exercise if the rest has already ended.
* Telegram Back / the arrow asks "End workout?". Confirming leaves the screen; logged sets stay saved and
  the workout can be continued from the Train tab.
* `navigator.wakeLock` keeps the screen on during the workout where supported.

## Backend
No database change and no new endpoint. Workout items now include `media`
(`{kind, start, peak, still}`) next to `image`, in `GET /api/train` and all `/api/workouts/...` responses.

## Texts
`miniapp/src/i18n/guided.{en,ru,uz}.json` (keys `gx_*`), merged in `i18n/index.ts`. Uzbek texts were
written by an assistant: please have a native speaker check them.
