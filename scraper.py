"""
Lightweight scraper using the whenbuff.com JSON API directly.
No browser required — a single httpx request with browser-like headers.

API: https://api.whenbuff.com/buffs?server=<realm>&from_date=DD/MM/YYYY&to_date=DD/MM/YYYY
Returns a list of objects: { buff_type, buff_faction, buff_date: "DD/MM/YYYY-HH:MM" }
Dates are in UTC.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx

API_URL = "https://api.whenbuff.com/buffs"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.whenbuff.com/",
    "Origin": "https://www.whenbuff.com",
    "Accept": "application/json, text/plain, */*",
}


@dataclass
class BuffTimer:
    name: str
    seconds_remaining: int
    realm: str

    @property
    def formatted_time(self) -> str:
        if self.seconds_remaining <= 0:
            return "Active now"
        h, rem = divmod(self.seconds_remaining, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m" if h else f"{m}m {s}s"

    def is_imminent(self, threshold_minutes: int) -> bool:
        return 0 < self.seconds_remaining <= threshold_minutes * 60


async def scrape_buffs(
    realm_name: str,
    debug_dir: Optional[Path] = None,
    window_hours: int = 24,
) -> list[BuffTimer]:
    """
    Return upcoming buff timers for the given realm within the next window_hours.
    Buff dates from the API are treated as UTC.
    """
    now = datetime.now(timezone.utc)
    params = {
        "server": realm_name,
        "from_date": now.strftime("%d/%m/%Y"),
        "to_date": (now + timedelta(days=2)).strftime("%d/%m/%Y"),
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
        response = await client.get(API_URL, params=params)
        response.raise_for_status()
        data: list[dict] = response.json()

    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "api_response.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        print(f"[debug] API returned {len(data)} entries")
        print(f"[debug] Saved to {debug_dir.resolve()}/api_response.json")

    cutoff = now + timedelta(hours=window_hours)
    buffs: list[BuffTimer] = []

    for entry in data:
        try:
            buff_dt = datetime.strptime(entry["buff_date"], "%d/%m/%Y-%H:%M").replace(
                tzinfo=timezone.utc
            )
        except (KeyError, ValueError):
            continue

        seconds = (buff_dt - now).total_seconds()
        if seconds <= 0 or buff_dt > cutoff:
            continue

        buffs.append(BuffTimer(
            name=entry.get("buff_type", "Unknown"),
            seconds_remaining=int(seconds),
            realm=realm_name,
        ))

    return sorted(buffs, key=lambda b: b.seconds_remaining)
