"""
Scraper for https://www.whenbuff.com/ using Playwright.

The site blocks plain HTTP requests, so we load it as a real browser.
Run debug_scraper.py first to capture a screenshot + page dump, which
lets you verify that realm selection and buff selectors are working.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page

WHENBUFF_URL = "https://www.whenbuff.com/"


@dataclass
class BuffTimer:
    name: str
    seconds_remaining: int  # 0 = active/just went out, >0 = countdown
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


def _parse_seconds(text: str) -> Optional[int]:
    """Convert a timer string to total seconds. Returns None if not parseable."""
    text = text.strip()

    # HH:MM:SS
    if m := re.fullmatch(r"(\d+):(\d{2}):(\d{2})", text):
        return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
    # MM:SS
    if m := re.fullmatch(r"(\d+):(\d{2})", text):
        return int(m[1]) * 60 + int(m[2])
    # Xh Ym Zs (any combination)
    total = 0
    found_any = False
    for pattern, mult in [
        (r"(\d+)\s*h", 3600),
        (r"(\d+)\s*m", 60),
        (r"(\d+)\s*s", 1),
    ]:
        if hit := re.search(pattern, text, re.IGNORECASE):
            total += int(hit[1]) * mult
            found_any = True
    return total if found_any else None


async def _select_realm(page: Page, realm_name: str) -> bool:
    """
    Attempt to select the realm on the page. Returns True if successful.

    whenbuff.com's exact realm selection UI isn't known in advance, so this
    tries several common patterns in order.
    """
    await page.wait_for_timeout(1500)  # let JS render

    # Pattern 1: clickable text matching the realm name
    try:
        await page.click(f"text={realm_name}", timeout=2500)
        await page.wait_for_timeout(2000)
        return True
    except Exception:
        pass

    # Pattern 2: <select> dropdown
    try:
        await page.select_option("select", label=realm_name, timeout=2000)
        await page.wait_for_timeout(1000)
        return True
    except Exception:
        pass

    # Pattern 3: search/filter input
    try:
        inp = await page.wait_for_selector(
            "input[type='text'], input[type='search'], input[placeholder]",
            timeout=2000,
        )
        await inp.fill(realm_name)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)
        return True
    except Exception:
        pass

    return False


_ABBREV: dict[str, str] = {
    "ZG": "Zul'Gurub",
    "ONY": "Onyxia",
    "REND": "Rend",
    "NEF": "Nefarian",
}


def _expand(name: str) -> str:
    return _ABBREV.get(name.strip().upper(), name.strip())


async def _extract_buffs(page: Page, realm_name: str) -> list[BuffTimer]:
    """
    Extract all upcoming buff timers for today from the calendar column.

    Strategy:
      1. Find today's day column in the DOM (by CSS class or orange border highlight).
      2. Parse "HH:MM - BuffName" entries from that column only.
      3. Fall back to the site's "Next buff is X in HH:MM:SS" headline if the
         calendar column can't be identified.
    """
    calendar_entries: list[dict] = await page.evaluate("""
        () => {
            const now = new Date();
            let todayContainer = null;

            // Attempt 1: common class names
            todayContainer = document.querySelector(
                '.today, .current, [class*="today"], [class*="current-day"], [class*="currentDay"]'
            );

            // Attempt 2: element with an orange/amber border (the highlighted day column)
            if (!todayContainer) {
                for (const el of document.querySelectorAll('div, td, li, section')) {
                    const style = window.getComputedStyle(el);
                    const bc = style.borderColor;
                    if (!bc || bc === 'transparent' || bc === 'rgba(0, 0, 0, 0)') continue;
                    const rgb = bc.match(/\\d+/g);
                    if (!rgb || rgb.length < 3) continue;
                    const [r, g, b] = [Number(rgb[0]), Number(rgb[1]), Number(rgb[2])];
                    // Orange/amber: high red, moderate green, low blue
                    if (r > 180 && g > 80 && g < 210 && b < 80) {
                        todayContainer = el;
                        break;
                    }
                }
            }

            if (!todayContainer) return [];

            const seen = new Set();
            const results = [];

            for (const line of todayContainer.innerText.split('\\n')) {
                const m = line.trim().match(/^(\\d{1,2}):(\\d{2})\\s*[-–]\\s*(.+)$/);
                if (!m) continue;

                const h = parseInt(m[1]);
                const min = parseInt(m[2]);
                const buffName = m[3].trim();
                const key = `${h}:${min}-${buffName}`;
                if (seen.has(key)) continue;
                seen.add(key);

                const buffDate = new Date(now);
                buffDate.setHours(h, min, 0, 0);
                const msUntil = buffDate.getTime() - now.getTime();
                if (msUntil <= 0) continue; // already passed today

                results.push({ buffName, secondsUntil: Math.floor(msUntil / 1000) });
            }

            return results.sort((a, b) => a.secondsUntil - b.secondsUntil);
        }
    """)

    buffs: list[BuffTimer] = []

    for entry in calendar_entries:
        buffs.append(BuffTimer(
            name=_expand(entry["buffName"]),
            seconds_remaining=entry["secondsUntil"],
            realm=realm_name,
        ))

    # Fallback: primary countdown headline
    if not buffs:
        text = await page.inner_text("body")
        match = re.search(
            r"Next buff is\s+(.+?)\s+in\s+(\d+:\d{2}:\d{2}|\d+:\d{2})",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            seconds = _parse_seconds(match.group(2).strip())
            if seconds is not None:
                buffs.append(BuffTimer(
                    name=match.group(1).strip(),
                    seconds_remaining=seconds,
                    realm=realm_name,
                ))

    return buffs


async def scrape_buffs(realm_name: str, debug_dir: Optional[Path] = None) -> list[BuffTimer]:
    """
    Load whenbuff.com, optionally select a realm, and return all buff timers.

    Args:
        realm_name:  The realm to filter to (e.g. "Skull Rock").
        debug_dir:   If provided, saves screenshot + HTML + text dumps here
                     so you can inspect the page structure.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        try:
            await page.goto(WHENBUFF_URL, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(4000)  # let JS timers render

            realm_found = await _select_realm(page, realm_name)

            if debug_dir:
                debug_dir.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(debug_dir / "screenshot.png"), full_page=True)
                html = await page.content()
                (debug_dir / "page.html").write_text(html, encoding="utf-8")
                text = await page.inner_text("body")
                (debug_dir / "text.txt").write_text(text, encoding="utf-8")
                print(f"[debug] realm '{realm_name}' found: {realm_found}")
                print(f"[debug] files saved to {debug_dir.resolve()}/")
                print(f"[debug] page text preview:\n{text[:800]}\n...")

            buffs = await _extract_buffs(page, realm_name)
        finally:
            await browser.close()

    return buffs
