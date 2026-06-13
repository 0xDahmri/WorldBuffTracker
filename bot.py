"""
World Buff Tracker Discord bot.

Slash commands:
  /buffs                     Show upcoming buff timers on demand
  /channel add <#channel>    Add a channel to receive alerts
  /channel remove <#channel> Remove a channel
  /channel list              Show configured channels
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks

import config
from scraper import BuffTimer, scrape_buffs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Settings  (persisted to settings.json so they survive restarts)
# ---------------------------------------------------------------------------
SETTINGS_FILE = Path("settings.json")


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        data = json.loads(SETTINGS_FILE.read_text())
        if "channel_id" in data and "channel_ids" not in data:
            data["channel_ids"] = [data.pop("channel_id")]
        return {"channel_ids": data.get("channel_ids", config.CHANNEL_IDS)}
    return {"channel_ids": config.CHANNEL_IDS}


def _save_settings() -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


settings = _load_settings()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_US_TZS = [
    ZoneInfo("America/New_York"),
    ZoneInfo("America/Chicago"),
    ZoneInfo("America/Denver"),
    ZoneInfo("America/Los_Angeles"),
]


def _us_clock_times(buff: BuffTimer) -> str:
    parts = []
    for tz in _US_TZS:
        local = buff.buff_time_utc.astimezone(tz)
        h = local.hour % 12 or 12
        ampm = "AM" if local.hour < 12 else "PM"
        parts.append(f"{h}:{local.strftime('%M')} {ampm} {local.strftime('%Z')}")
    return " · ".join(parts)


def _thumbnail_url() -> Optional[str]:
    if not config.ICON_BASE_URL:
        return None
    return f"{config.ICON_BASE_URL}/onyxia.png"


def _buffs_embed(buffs: list[BuffTimer], title: str) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=f"Realm: **{config.REALM_NAME}**",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    if not buffs:
        embed.add_field(name="No upcoming buffs", value="Nothing in the next 24 hours.")
        return embed
    for buff in buffs:
        label = "🟢 Active now" if buff.seconds_remaining <= 0 else f"⏳ {buff.formatted_time}"
        clock = _us_clock_times(buff)
        embed.add_field(name=buff.name, value=f"{label}\n{clock}", inline=False)
    url = _thumbnail_url()
    if url:
        embed.set_thumbnail(url=url)
    return embed


def _alert_embed(buff: BuffTimer) -> discord.Embed:
    clock = _us_clock_times(buff)
    embed = discord.Embed(
        title=f"⚠️ {buff.name} in {buff.formatted_time}!",
        description=f"Realm: **{buff.realm}**\n{clock}",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    url = _thumbnail_url()
    if url:
        embed.set_thumbnail(url=url)
    return embed

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

_alerted: set[str] = set()
_last_seen_seconds: dict[str, int] = {}


async def _fetch() -> list[BuffTimer]:
    for attempt in range(3):
        try:
            buffs = await scrape_buffs(config.REALM_NAME)
            if buffs:
                return buffs
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Scrape attempt %d/3 failed: %s", attempt + 1, exc)
            if attempt < 2:
                await asyncio.sleep(15)
    log.error("All scrape attempts failed")
    return []


async def _broadcast(embed: discord.Embed) -> None:
    for channel_id in settings["channel_ids"]:
        channel = bot.get_channel(channel_id)
        if channel is None:
            log.warning("Channel %s not found", channel_id)
            continue
        await channel.send(embed=embed)

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready() -> None:
    await tree.sync()
    log.info("Logged in as %s", bot.user)
    if not check_alerts.is_running():
        check_alerts.start()

# ---------------------------------------------------------------------------
# /buffs
# ---------------------------------------------------------------------------
@tree.command(name="buffs", description="Show upcoming world buff timers")
async def cmd_buffs(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    buffs = await _fetch()
    await interaction.followup.send(embed=_buffs_embed(buffs, "World Buff Timers"))

# ---------------------------------------------------------------------------
# /channel
# ---------------------------------------------------------------------------
channel_group = app_commands.Group(name="channel", description="Manage alert channels")
tree.add_command(channel_group)


@channel_group.command(name="add", description="Add a channel for buff alerts")
@app_commands.describe(channel="Channel to add")
async def cmd_channel_add(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    if channel.id in settings["channel_ids"]:
        await interaction.response.send_message(f"{channel.mention} is already configured.", ephemeral=True)
        return
    settings["channel_ids"].append(channel.id)
    _save_settings()
    await interaction.response.send_message(f"Added {channel.mention}.", ephemeral=True)


@channel_group.command(name="remove", description="Remove a channel from buff alerts")
@app_commands.describe(channel="Channel to remove")
async def cmd_channel_remove(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    if channel.id not in settings["channel_ids"]:
        await interaction.response.send_message(f"{channel.mention} is not configured.", ephemeral=True)
        return
    settings["channel_ids"].remove(channel.id)
    _save_settings()
    await interaction.response.send_message(f"Removed {channel.mention}.", ephemeral=True)


@channel_group.command(name="list", description="List configured alert channels")
async def cmd_channel_list(interaction: discord.Interaction) -> None:
    ids = settings["channel_ids"]
    if not ids:
        await interaction.response.send_message("No channels configured.", ephemeral=True)
        return
    lines = "\n".join(f"<#{cid}>" for cid in ids)
    await interaction.response.send_message(f"Alert channels:\n{lines}", ephemeral=True)

# ---------------------------------------------------------------------------
# Background task — alert only
# ---------------------------------------------------------------------------
@tasks.loop(seconds=60)
async def check_alerts() -> None:
    buffs = await _fetch()
    for buff in buffs:
        prev = _last_seen_seconds.get(buff.name)
        if prev is not None and buff.seconds_remaining > prev + 300:
            _alerted.discard(buff.name)
        if buff.is_imminent(config.ALERT_MINUTES) and buff.name not in _alerted:
            _alerted.add(buff.name)
            log.info("Alert: %s in %s", buff.name, buff.formatted_time)
            await _broadcast(_alert_embed(buff))
        _last_seen_seconds[buff.name] = buff.seconds_remaining


@check_alerts.before_loop
async def _before_alerts() -> None:
    await bot.wait_until_ready()


if __name__ == "__main__":
    bot.run(config.DISCORD_TOKEN)
