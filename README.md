# WorldBuffTracker

A Discord bot that pulls world buff schedules from the whenbuff.com API and posts alerts and summaries for WoW Classic Hardcore realms.

## Features

- **Imminent alerts** — pings your channel when a buff is going out within a configurable window
- **Periodic summaries** — posts all of today's remaining buffs on a schedule
- **`/buffs` command** — on-demand timer lookup showing all upcoming buffs today
- **`/channel` commands** — manage multiple alert channels from Discord
- **`/config` commands** — change check and summary intervals without restarting the bot
- **Buff icon** — Onyxia icon thumbnail on every embed (served from `ICON_BASE_URL`)

## Requirements

- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourname/WorldBuffTracker.git
cd WorldBuffTracker
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
nano .env
```

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal |
| `CHANNEL_IDS` | Comma-separated channel IDs to post alerts in (or single `CHANNEL_ID`) |
| `REALM_NAME` | Realm name exactly as shown on whenbuff.com (e.g. `Doomhowl`) |
| `ICON_BASE_URL` | Base URL for icon images, e.g. `https://raw.githubusercontent.com/you/WorldBuffTracker/main` |
| `ALERT_MINUTES` | Minutes before a buff to send an alert (default: `15`) |
| `SUMMARY_INTERVAL` | How often to post a summary, in minutes (default: `30`) |

### 4. Invite the bot to your server

In the Developer Portal go to **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes, and enable the following permissions:

- **Send Messages**
- **Embed Links**

Open the generated URL to invite the bot, then make sure it has **Send Messages** and **Embed Links** in each target channel.

### 5. Test the scraper

```bash
python debug_scraper.py
```

This calls the API and prints the upcoming buffs for your realm. The raw API response is saved to `debug/api_response.json`.

### 6. Run the bot

```bash
python bot.py
```

## Slash Commands

| Command | Description |
|---|---|
| `/buffs` | Show all upcoming buff timers for today |
| `/channel add <#channel>` | Add a channel to receive alerts and summaries |
| `/channel remove <#channel>` | Remove a channel |
| `/channel list` | List all configured channels |
| `/config check <seconds>` | Set how often the bot checks for imminent buffs (min 30s) |
| `/config summary <minutes>` | Set how often the bot posts a summary (min 5 min) |
| `/config show` | Display current settings (only visible to you) |

All interval and channel settings are saved to `settings.json` and restored on restart.

## Icon

Every embed shows a static Onyxia icon as a thumbnail. To change it, update `_thumbnail_url()` in `bot.py` to point to a different filename. The icon is served from `ICON_BASE_URL` set in `.env`.

## Project Structure

```
WorldBuffTracker/
├── bot.py              # Discord bot, slash commands, background tasks
├── scraper.py          # whenbuff.com API client
├── config.py           # Environment variable loading
├── debug_scraper.py    # Standalone tool to test the API connection
├── requirements.txt
├── .env.example
└── *.png               # Buff icon images
```
