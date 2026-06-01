"""
Standalone debug runner. Run this once before starting the bot to confirm
that the scraper can find and parse your realm's buff timers.

Usage:
    python debug_scraper.py

Outputs:
  debug/screenshot.png   - full-page screenshot after realm selection
  debug/page.html        - full rendered HTML
  debug/text.txt         - visible text content of the page
  stdout                 - list of buffs the scraper found
"""

import asyncio
from pathlib import Path

import config
from scraper import scrape_buffs


async def main() -> None:
    print(f"Scraping whenbuff.com for realm: {config.REALM_NAME!r}")
    buffs = await scrape_buffs(config.REALM_NAME, debug_dir=Path("debug"))

    print(f"\n{'='*50}")
    print(f"Found {len(buffs)} buff(s):")
    for buff in buffs:
        print(f"  {buff.name:<35} {buff.formatted_time}")
    print("="*50)

    if not buffs:
        print("\nNo buffs found. Check debug/screenshot.png and debug/text.txt")
        print("to see what the page looks like, then adjust the selectors in scraper.py.")


if __name__ == "__main__":
    asyncio.run(main())
