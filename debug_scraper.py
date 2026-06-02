"""
Standalone debug runner. Calls the whenbuff.com API directly and prints
the upcoming buffs for your configured realm.

Usage:
    python debug_scraper.py

Outputs:
  debug/api_response.json  - raw API response
  stdout                   - parsed buff list
"""

import asyncio
from pathlib import Path

import config
from scraper import scrape_buffs


async def main() -> None:
    print(f"Fetching buffs for realm: {config.REALM_NAME!r}")
    buffs = await scrape_buffs(config.REALM_NAME, debug_dir=Path("debug"))

    print(f"\n{'='*50}")
    print(f"Found {len(buffs)} upcoming buff(s):")
    for buff in buffs:
        print(f"  {buff.name:<35} {buff.formatted_time}")
    print("="*50)

    if not buffs:
        print("\nNo buffs found. Check debug/api_response.json for the raw API response.")


if __name__ == "__main__":
    asyncio.run(main())
