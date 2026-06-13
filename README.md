# WorldBuffTracker

A Discord bot that pulls world buff schedules from the whenbuff.com API and posts 30-minute alerts for WoW Classic Hardcore realms.

## Features

- **30-minute alerts** — pings your channel when a buff is going out soon
- **`/buffs` command** — on-demand timer lookup with US timezone clock times
- **`/channel` commands** — manage alert channels from Discord
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
| `ALERT_MINUTES` | Minutes before a buff to send an alert (default: `30`) |

### 4. Invite the bot to your server

In the Developer Portal go to **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes, and enable:

- **Send Messages**
- **Embed Links**

Open the generated URL to invite the bot, then make sure it has those permissions in each target channel.

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
| `/buffs` | Show all upcoming buff timers for the next 24 hours |
| `/channel add <#channel>` | Add a channel to receive alerts |
| `/channel remove <#channel>` | Remove a channel |
| `/channel list` | List all configured channels |

Channel settings are saved to `settings.json` and restored on restart.

## Icon

Every embed shows a static Onyxia icon as a thumbnail. It is served from `ICON_BASE_URL` set in `.env`.

## Project Structure

```
WorldBuffTracker/
├── bot.py              # Discord bot, slash commands, alert task
├── scraper.py          # whenbuff.com API client
├── config.py           # Environment variable loading
├── debug_scraper.py    # Standalone tool to test the API connection
├── requirements.txt
├── .env.example
└── *.png               # Buff icon images
```
