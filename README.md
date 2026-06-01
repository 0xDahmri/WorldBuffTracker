# WorldBuffTracker

A Discord bot that scrapes [whenbuff.com](https://www.whenbuff.com/) and posts world buff alerts and summaries for WoW Classic Hardcore realms.

## Features

- **Imminent alerts** — pings your channel when a buff is going out within a configurable window
- **Periodic summaries** — posts a full timer embed on a schedule
- **`/buffs` command** — on-demand timer lookup
- **`/config` commands** — change check and summary intervals from Discord without restarting the bot
- **Buff icons** — attaches the correct icon thumbnail to each embed

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
python -m playwright install chromium
```

On Debian based hosts, install the Chromium system libraries:

```bash
sudo apt-get install -y libasound2t64 fonts-unifont
```

### 3. Configure environment variables

```bash
cp .env.example .env
nano .env
```

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal |
| `CHANNEL_ID` | ID of the channel to post alerts in |
| `REALM_NAME` | Realm name exactly as shown on whenbuff.com (e.g. `Doomhowl`) |
| `ALERT_MINUTES` | Minutes before a buff to send an alert (default: `15`) |
| `SUMMARY_INTERVAL` | How often to post a summary, in minutes (default: `30`) |

### 4. Invite the bot to your server

In the Developer Portal go to **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes, and enable the **Send Messages** and **Embed Links** permissions. Open the generated URL to invite the bot.

Make sure the bot has **Send Messages** and **Embed Links** permissions in the target channel.

### 5. Test the scraper

```bash
python debug_scraper.py
```

This saves a screenshot and page dump to `debug/` so you can confirm realm selection is working before starting the bot.

### 6. Run the bot

```bash
python bot.py
```

## Slash Commands

| Command | Description |
|---|---|
| `/buffs` | Show the current buff timer for your realm |
| `/channel add <#channel>` | Add a channel to receive alerts and summaries |
| `/channel remove <#channel>` | Remove a channel |
| `/channel list` | List all configured channels |
| `/config check <seconds>` | Set how often the bot checks for imminent buffs (min 30s) |
| `/config summary <minutes>` | Set how often the bot posts a summary (min 5 min) |
| `/config show` | Display current settings including all channels (only visible to you) |

Interval settings are saved to `settings.json` and restored on restart.

## Icon Mapping

Icons are matched by buff name substring. To add or change an icon, edit the `BUFF_ICONS` dict near the top of `bot.py`:

```python
BUFF_ICONS: dict[str, str] = {
    "zul'gurub": "zulgurub.png",
    "onyxia":    "onyxia.png",
    "rend":      "rend.png",
    "alliance":  "alliance.png",
    "horde":     "horde.png",
}
```

Image files should be placed in the project root.

## Project Structure

```
WorldBuffTracker/
├── bot.py              # Discord bot, slash commands, background tasks
├── scraper.py          # Playwright-based scraper for whenbuff.com
├── config.py           # Environment variable loading
├── debug_scraper.py    # Standalone tool to test the scraper
├── requirements.txt
├── .env.example
└── *.png               # Buff icon images
```
