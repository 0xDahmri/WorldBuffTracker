import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
CHANNEL_ID: int = int(os.environ["CHANNEL_ID"])
REALM_NAME: str = os.environ["REALM_NAME"]
ALERT_MINUTES: int = int(os.getenv("ALERT_MINUTES", "15"))
SUMMARY_INTERVAL: int = int(os.getenv("SUMMARY_INTERVAL", "30"))
