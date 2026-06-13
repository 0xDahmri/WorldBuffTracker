import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]

# Accepts comma-separated CHANNEL_IDS or legacy single CHANNEL_ID
_raw = os.getenv("CHANNEL_IDS", os.getenv("CHANNEL_ID", ""))
CHANNEL_IDS: list[int] = [int(x.strip()) for x in _raw.split(",") if x.strip()]

REALM_NAME: str = os.environ["REALM_NAME"]
ALERT_MINUTES: int = int(os.getenv("ALERT_MINUTES", "30"))

# Base URL for buff icons, e.g. https://raw.githubusercontent.com/you/WorldBuffTracker/main
# Leave empty to disable icons.
ICON_BASE_URL: str = os.getenv("ICON_BASE_URL", "").rstrip("/")
