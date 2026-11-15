# Testing the Mini App locally (HTTPS) and hosting it later

Telegram only opens Mini Apps over **HTTPS**. Locally we run everything on your
PC and use a free tunnel that gives your `localhost` a public HTTPS address.

## 0. One-time installs

| Tool | Windows | macOS / Linux |
|---|---|---|
| Python 3.11+ | python.org | already installed / package manager |
| Node.js 22 LTS (20.19+ works) | `winget install OpenJS.NodeJS.LTS` | nodejs.org or `brew install node` |
| cloudflared | `winget install --id Cloudflare.cloudflared` | `brew install cloudflared` |

Then, in the project folder:

```bash
pip install -r requirements.txt
cd miniapp
npm install
npm run build          # creates miniapp/dist, which the API serves
cd ..
```

## 1. Start the API

```bash
uvicorn api.main:app --port 8000 --reload
```

Check http://localhost:8000/api/health shows `{"status":"ok"}`. Opening
http://localhost:8000 in a normal browser shows "Open Gym24 from the bot":
correct, because a normal browser has no Telegram login.

## 2. Start the tunnel (new terminal)

```bash
cloudflared tunnel --url http://localhost:8000
```

It prints an address like `https://quiet-river-1234.trycloudflare.com`. Copy it.
This free "quick tunnel" needs no account, but **the address changes every time
you restart cloudflared**.

## 3. Tell the bot the address

In `.env`:

```
MINIAPP_URL=https://quiet-river-1234.trycloudflare.com
```

Start (or restart) the bot in a third terminal:

```bash
python bot.py
```

On start the bot sets its **menu button** (left of the message box) to open
Gym24 at `MINIAPP_URL`; the log says `Menu button opens the Mini App at ...`.
After a new tunnel address, change `MINIAPP_URL` and restart the bot. That's all.

## 4. Open it in Telegram

Open your bot and tap the **Gym24** menu button. You should see "Hi, <your
name>!" with green ticks. Tap Русский: the app switches to Russian, and
`/help` in the bot now answers in Russian too (same saved language).
If you see the menu button with an old address, close and reopen the chat.

## Alternative: set the menu button in BotFather

If you prefer not to let the bot do it (leave `MINIAPP_URL` empty then):
1. Open @BotFather → `/mybots` → your bot → **Bot Settings** → **Menu Button**.
2. **Configure menu button** → send the HTTPS address → send the title `Gym24`.

Optional, later: `/newapp` in BotFather creates a direct link
(`t.me/<your_bot>/<short_name>`) that also opens the Mini App with signed data.

## Developing with instant reload

Instead of `npm run build`, run the Vite dev server and point the tunnel at it:

```bash
cd miniapp && npm run dev                       # http://localhost:5173, forwards /api to :8000
cloudflared tunnel --url http://localhost:5173  # use THIS address as MINIAPP_URL
```

Changes to the React code appear immediately in Telegram after closing and
reopening the app.

## ngrok (alternative tunnel with a fixed address)

ngrok's free plan gives one permanent domain (no need to update `.env` every
day), but it shows a "You are about to visit…" warning page the first time.
Tap **Visit Site** once; it then stays hidden for about 7 days.

```bash
ngrok config add-authtoken <token from dashboard.ngrok.com>
ngrok http 8000 --url=<your-domain>.ngrok-free.app
```

## Debugging inside Telegram

- **Telegram Desktop**: Settings → Advanced → Experimental settings → *Enable
  webview inspecting*, then right-click inside the Mini App → Inspect.
- **Android**: enable USB debugging, open `chrome://inspect` on your computer.
- "Your login couldn't be verified": the bot and the API must use the **same**
  `BOT_TOKEN`; also check your phone's clock.

## Real hosting later

The simplest reliable setup is **one small Linux VPS** (Hetzner, DigitalOcean,
etc., about $4-6/month) with a domain name:

1. Run the bot and the API as two services (systemd or Docker Compose).
2. Put **Caddy** in front of the API: it gets free HTTPS certificates
   automatically. Caddyfile: `gym24.example.com { reverse_proxy localhost:8000 }`.
3. Switch `DATABASE_URL` to PostgreSQL (`postgresql+asyncpg://...`); migrations
   create the tables.
4. Set `MINIAPP_URL=https://gym24.example.com` and restart the bot.

Platform services (Render, Railway, Fly.io) also work, but the bot needs an
always-on worker (it uses long polling and the reminder scheduler), so free
tiers that sleep aren't suitable.
