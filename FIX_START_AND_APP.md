# Fix: /start opens onboarding in the Mini App, /app logs you in

Unzip into the project root (folder with bot.py) and restart the bot.

| File | What changed |
|---|---|
| handlers/common.py | /start (no profile yet): a short welcome with the health note and a **📱 Set up my profile** button that opens the Mini App onboarding. No more chat questions. The old chat questionnaire is only used if MINIAPP_URL isn't an https address |
| handlers/webapp.py | /app sends an **inline** "Open Gym24" button (signed login) instead of the old reply-keyboard button, and restores the normal menu |
| utils/texts.py | also loads locales/extra/<lang>.json |
| locales/extra/en.json, ru.json, uz.json | NEW. The new bot texts in all 3 languages |

## Why the app said "Open Gym24 from the bot"
The old /app put a button in the **reply keyboard** (at the bottom). Telegram does not
send the signed login data for those buttons, so the app could not verify you.
Inline buttons (under a message) and the Gym24 menu button do send it.

## Test
1. Restart the bot (`python bot.py`). MINIAPP_URL must be your current https tunnel address.
2. Send /deleteme (to test as a new user), then /start → choose a language → you get the
   welcome and **📱 Set up my profile**. Tap it: the app opens on question 1.
3. Finish onboarding in the app: the chat gets "Your Gym24 profile is set up" and the menu.
4. Send /app → tap **📱 Open Gym24** under the message: the app opens logged in, on the Train tab.
   The old "Open workout logger" button at the bottom is replaced by the normal menu.
5. `pytest`: chat-onboarding tests still pass because tests run without MINIAPP_URL.
