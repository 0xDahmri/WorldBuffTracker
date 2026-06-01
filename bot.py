"""
World Buff Tracker Discord bot.

Slash commands:
  /buffs                     Show current timer for the configured realm
  /channel add <#channel>    Add a channel to post alerts in
  /channel remove <#channel> Remove a channel
  /channel list              Show all configured channels
  /config check <seconds>    Set how often the bot checks for imminent buffs
  /config summary <minutes>  Set how often the bot posts a summary
  /config show               Show current settings
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
        # Migrate old single channel_id key if present
        if "channel_id" in data and "channel_ids" not in data:
            data["channel_ids"] = [data.pop("channel_id")]
        return data
    return {
        "check_interval": 60,
        "summary_interval": config.SUMMARY_INTERVAL,
        "channel_ids": config.CHANNEL_IDS,
    }


def _save_settings() -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


settings = _load_settings()

# ---------------------------------------------------------------------------
# Icon mapping  –  filenames served from ICON_BASE_URL in .env
# e.g. https://raw.githubusercontent.com/you/WorldBuffTracker/main
# ---------------------------------------------------------------------------
BUFF_ICONS: dict[str, str] = {
    "zul'gurub": "zulgurub.png",
    "onyxia":    "onyxia.png",
    "rend":      "rend.png",
    "alliance":  "alliance.png",
    "horde":     "horde.png",
}


def _icon_url(buff_name: str) -> Optional[str]:
    """Return the icon URL for a buff, or None if ICON_BASE_URL is not set."""
    if not config.ICON_BASE_URL:
        return None
    lower = buff_name.lower()
    for key, filename in BUFF_ICONS.items():
        if key in lower or lower in key:
            return f"{config.ICON_BASE_URL}/{filename}"
    return None

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
            raise  # bot is shutting down, stop immediately
        except Exception as exc:
            log.warning("Scrape attempt %d/3 failed: %s", attempt + 1, exc)
            if attempt < 2:
                await asyncio.sleep(15)
    log.error("All scrape attempts failed")
    return []


async def _broadcast(embed: discord.Embed, buff_name: str) -> None:
    """Send an embed to every configured channel."""
    for channel_id in settings["channel_ids"]:
        channel = bot.get_channel(channel_id)
        if channel is None:
            log.warning("Channel %s not found", channel_id)
            continue
        await channel.send(embed=embed)


def _summary_embed(buffs: list[BuffTimer], title: str) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=f"Realm: **{config.REALM_NAME}**",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )
    if not buffs:
        embed.add_field(name="No data", value="Could not retrieve timers.")
        return embed
    for buff in sorted(buffs, key=lambda b: b.seconds_remaining):
        label = "🟢 Active now" if buff.seconds_remaining <= 0 else f"⏳ {buff.formatted_time}"
        embed.add_field(name=buff.name, value=label, inline=True)
    url = _icon_url(buffs[0].name)
    if url:
        embed.set_thumbnail(url=url)
    return embed


def _alert_embed(buff: BuffTimer) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚠️ {buff.name} going out soon!",
        description=f"Realm: **{buff.realm}**\nTime remaining: **{buff.formatted_time}**",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    url = _icon_url(buff.name)
    if url:
        embed.set_thumbnail(url=url)
    return embed

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready() -> None:
    await tree.sync()
    log.info("Logged in as %s", bot.user)
    check_alerts.change_interval(seconds=settings["check_interval"])
    post_summary.change_interval(minutes=settings["summary_interval"])
    if not check_alerts.is_running():
        check_alerts.start()
    if not post_summary.is_running():
        post_summary.start()

# ---------------------------------------------------------------------------
# /buffs
# ---------------------------------------------------------------------------
@tree.command(name="buffs", description="Show current world buff timers")
async def cmd_buffs(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    buffs = await _fetch()
    await interaction.followup.send(embed=_summary_embed(buffs, "World Buff Timers"))

# ---------------------------------------------------------------------------
# /channel
# ---------------------------------------------------------------------------
channel_group = app_commands.Group(name="channel", description="Manage channels the bot posts to")
tree.add_command(channel_group)


@channel_group.command(name="add", description="Add a channel for buff alerts and summaries")
@app_commands.describe(channel="Channel to add")
async def cmd_channel_add(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    if channel.id in settings["channel_ids"]:
        await interaction.response.send_message(
            f"{channel.mention} is already configured.", ephemeral=True
        )
        return
    settings["channel_ids"].append(channel.id)
    _save_settings()
    await interaction.response.send_message(
        f"Added {channel.mention} to buff alert channels.", ephemeral=True
    )


@channel_group.command(name="remove", description="Remove a channel from buff alerts")
@app_commands.describe(channel="Channel to remove")
async def cmd_channel_remove(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    if channel.id not in settings["channel_ids"]:
        await interaction.response.send_message(
            f"{channel.mention} is not configured.", ephemeral=True
        )
        return
    settings["channel_ids"].remove(channel.id)
    _save_settings()
    await interaction.response.send_message(
        f"Removed {channel.mention} from buff alert channels.", ephemeral=True
    )


@channel_group.command(name="list", description="Show all configured buff alert channels")
async def cmd_channel_list(interaction: discord.Interaction) -> None:
    ids = settings["channel_ids"]
    if not ids:
        await interaction.response.send_message("No channels configured.", ephemeral=True)
        return
    lines = "\n".join(f"<#{cid}>" for cid in ids)
    await interaction.response.send_message(f"Posting to:\n{lines}", ephemeral=True)

# ---------------------------------------------------------------------------
# /config
# ---------------------------------------------------------------------------
config_group = app_commands.Group(name="config", description="Configure the buff tracker")
tree.add_command(config_group)


@config_group.command(name="check", description="Set how often the bot checks for imminent buffs")
@app_commands.describe(seconds="Check interval in seconds (minimum 30)")
async def cmd_config_check(interaction: discord.Interaction, seconds: int) -> None:
    if seconds < 30:
        await interaction.response.send_message("Minimum is 30 seconds.", ephemeral=True)
        return
    check_alerts.change_interval(seconds=seconds)
    if not check_alerts.is_running():
        check_alerts.start()
    settings["check_interval"] = seconds
    _save_settings()
    await interaction.response.send_message(
        f"Check interval set to **{seconds}s**.", ephemeral=True
    )


@config_group.command(name="summary", description="Set how often the bot posts a buff summary")
@app_commands.describe(minutes="Summary interval in minutes (minimum 5)")
async def cmd_config_summary(interaction: discord.Interaction, minutes: int) -> None:
    if minutes < 5:
        await interaction.response.send_message("Minimum is 5 minutes.", ephemeral=True)
        return
    post_summary.change_interval(minutes=minutes)
    if not post_summary.is_running():
        post_summary.start()
    settings["summary_interval"] = minutes
    _save_settings()
    await interaction.response.send_message(
        f"Summary interval set to **{minutes} minutes**.", ephemeral=True
    )


@config_group.command(name="show", description="Show current bot settings")
async def cmd_config_show(interaction: discord.Interaction) -> None:
    ids = settings["channel_ids"]
    channels_str = ", ".join(f"<#{cid}>" for cid in ids) if ids else "None"
    embed = discord.Embed(title="Bot Settings", color=discord.Color.blurple())
    embed.add_field(name="Realm",            value=config.REALM_NAME,                      inline=False)
    embed.add_field(name="Channels",         value=channels_str,                            inline=False)
    embed.add_field(name="Alert threshold",  value=f"{config.ALERT_MINUTES} min",          inline=True)
    embed.add_field(name="Check interval",   value=f"{settings['check_interval']}s",       inline=True)
    embed.add_field(name="Summary interval", value=f"{settings['summary_interval']} min",  inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------
@tasks.loop(seconds=60)
async def check_alerts() -> None:
    buffs = await _fetch()
    if not buffs:
        return
    for buff in buffs:
        prev = _last_seen_seconds.get(buff.name)
        if prev is not None and buff.seconds_remaining > prev + 300:
            _alerted.discard(buff.name)
        if buff.is_imminent(config.ALERT_MINUTES) and buff.name not in _alerted:
            _alerted.add(buff.name)
            log.info("Alert: %s imminent (%s)", buff.name, buff.formatted_time)
            await _broadcast(_alert_embed(buff), buff.name)  # _broadcast ignores buff_name now but kept for consistency
        _last_seen_seconds[buff.name] = buff.seconds_remaining


@check_alerts.before_loop
async def _before_alerts() -> None:
    await bot.wait_until_ready()


@tasks.loop(minutes=30)
async def post_summary() -> None:
    buffs = await _fetch()
    embed = _summary_embed(buffs, "World Buff Summary")
    buff_name = buffs[0].name if buffs else ""
    await _broadcast(embed, buff_name)
    log.info("Summary posted (%d buffs)", len(buffs))


@post_summary.before_loop
async def _before_summary() -> None:
    await bot.wait_until_ready()


if __name__ == "__main__":
    bot.run(config.DISCORD_TOKEN)
