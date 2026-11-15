# Gym24 architecture

One backend, two entry points, one database:

```
             Telegram
     ┌──────────┴───────────┐
 chat updates          Mini App (WebView, HTTPS)
     │                       │  Authorization: tma <initData>
┌────▼─────┐          ┌──────▼───────┐
│  bot.py  │          │ api/main.py  │  FastAPI: JSON API + serves the
│ aiogram  │          │  (uvicorn)   │  built Mini App and exercise images
│APScheduler          └──────┬───────┘
└────┬─────┘                 │
     └──────► services/ ◄────┘   business logic (calculator, plans, logger, ...)
              database/          SQLAlchemy models + Alembic migrations
              locales/           bot texts (en/ru/uz)
                   │
             gymbot.db (SQLite, WAL)  →  PostgreSQL later (change DATABASE_URL)
```

- **bot.py**: chat side: language, reply keyboard menu, reminders (APScheduler),
  notifications, weekly summaries, admin commands.
- **api/**: everything the Mini App needs. Every `/api/*` route except
  `/api/health` verifies Telegram's signed `initData` (see `api/auth.py`).
- **services/**: shared by both; no Telegram or HTTP code in here.
- **miniapp/**: React + Vite + TypeScript. Built into `miniapp/dist/`, which
  the API serves, so the app and the API share one HTTPS address.

## Project structure

```
bot.py, config.py, import_exercises.py
alembic.ini, migrations/         database migrations (applied automatically on start)
api/
  main.py                        app factory, logging, static files
  auth.py                        initData signature check (HMAC-SHA256 with the bot token)
  deps.py                        session, verified identity, current user, rate limits
  schemas.py                     request/response shapes
  routes/                        one module per feature (system.py, me.py, ...)
  static.py                      cached exercise images + the built Mini App
database/  base.py models.py enums.py migrate.py
services/  (unchanged from Phases 1-6; reused by the API)
handlers/ keyboards/ utils/ locales/   bot side
miniapp/
  index.html                     loads telegram-web-app.js
  src/styles/tokens.css          design tokens (the only place for colours, sizes, fonts)
  src/styles/global.css          screen frame, outline, bottom glow
  src/lib/telegram.ts            typed SDK wrapper (ready, expand, haptics, BackButton)
  src/lib/api.ts                 fetch wrapper that sends initData
  src/i18n/en.json ru.json uz.json   Mini App texts (uz falls back to en for now)
docs/  ARCHITECTURE.md API.md LOCAL_HTTPS.md
```

## Security rules

1. The Mini App sends `Authorization: tma <initData>` with every request. The API
   recomputes the HMAC with the bot token and rejects anything that doesn't match,
   is older than `INIT_DATA_MAX_AGE` (24 h), or has no user.
2. The user ID always comes from verified initData. Request bodies and query
   strings never carry a user ID.
3. The bot token lives only in `.env` on the server. The frontend never sees it.
4. Telegram leaves initData **empty** for Mini Apps opened from a reply-keyboard
   button (confirmed in the Telegram docs), so Gym24 opens from **inline**
   buttons and the **menu button**, which both provide signed initData.
5. Rate limits: bot 8 actions / 5 s per user; API 120 requests / min per user
   and 20 failed logins / min per IP address.
6. `/deleteme` deletes the user row; every user-owned table has `ON DELETE CASCADE`
   (enforced by `tests/test_privacy.py`, so new tables can't forget it).

## Language (single source of truth)

`users.language` (`en`/`ru`/`uz`, or empty = never chosen). The bot's `/language`
and the Mini App's `PATCH /api/me/language` change the same field. Until a user
chooses, both follow the Telegram app language. `/start` asks for it once
(the question is shown in all three languages). Users who set up before the
picker existed are asked after their next message, once per bot run until they choose.

## Navigation map

```
BOT (chat)                                    ✅ = built (Stage 1)
/start ─ no language saved? ─► 🇬🇧 / 🇷🇺 / 🇺🇿 picker ─► health disclaimer ─► chat setup
   │                                                   ─► reply keyboard + [Open Gym24]
   └─ language saved ─► welcome back + reply keyboard + [Open Gym24]

Reply keyboard (main) ✅                      Settings submenu ✅
🏋️ Workout  | 📅 Plan                         🔔 Reminders     | 🌐 Language
📚 Exercises | 📊 Progress                    ✏️ Edit profile  | ℹ️ About (+ disclaimer)
🥗 Nutrition | 👤 Profile                     🗑 Delete my data | ⬅️ Back to menu
⚙️ Settings  | 🌐 Language
  Each button runs the matching chat feature (same as its /command). Once a Mini App
  tab exists, the button will show a short summary + inline [Open Gym24] for that tab.
  Labels match in every language, and a tap leaves any half-finished typed form.
[Open Gym24] inline button ✅ (only when MINIAPP_URL is an https:// address)
Chat menu button "Gym24" ✅ ─► Mini App (Home)

MINI APP
Profile incomplete ─► Onboarding (1 question per screen, n of N)
                       goal · age · sex · height · weight · experience · days/week
                       · equipment · injuries · diet · disclaimer ─► "Your plan is ready"
Tabs:  Home │ Plan │ Train │ Stats │ Profile        (unbuilt tabs hidden)
Home    greeting · character · next workout · weekly summary
Plan    calendar · current program · program details · all programs
        (Current / Available / Created) · create program · split editor
Train   workout day · live logger (rest timer, supersets, notes) · finish summary
        └─► Exercise Library (search, muscle chips, filters, A–Z) ─► exercise detail
Stats   consistency grid · weekly volume per muscle · PRs · weight and measurements
Profile character · level · achievements · edit profile · language · reminders
        · credits · delete my data
```

Tabs can be opened directly with a URL path (`/train`, `/plan`, ...): the API
serves the app for any path, so the bot's inline buttons can link to a tab.

## Database changes by stage

| Stage | Change |
|---|---|
| 0 ✅ | Alembic migrations; `users.language` (empty = not chosen); `users.language_code` removed; SQLite WAL mode |
| 2 | `profiles.target_weight_kg` (for the estimated goal date) |
| 3 | `exercises.secondary_muscles`, `exercises.visual_type` ("images") |
| 4 | `programs` (name, weeks, workouts/week, goal, status); plan days belong to a program |
| 5 | set fields: RPE, warm-up flag, superset group, note per exercise |
| 6 | XP events and level state |
| 9 | water/meal reminder settings |

Every change is an Alembic migration (`alembic revision --autogenerate -m "..."`),
so existing data is kept.
